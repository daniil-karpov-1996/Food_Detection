import json
import base64
import argparse
from random import randint
from io import BytesIO

import torch
from PIL import Image
from ultralytics import YOLO
from kafka import KafkaProducer, KafkaConsumer


# Примерные веса блюд Food-101 (эвристика)
FOOD_AVG_WEIGHT_G: dict[str, int] = {
    "apple_pie": 150, "baby_back_ribs": 400, "baklava": 80, "beef_carpaccio": 120,
    "beef_tartare": 130, "beet_salad": 180, "beignets": 90, "bibimbap": 450,
    "bread_pudding": 200, "breakfast_burrito": 250, "bruschetta": 120,
    "caesar_salad": 220, "cannoli": 100, "caprese_salad": 200, "carrot_cake": 140,
    "ceviche": 160, "cheesecake": 150, "cheese_plate": 180, "chicken_curry": 300,
    "chicken_quesadilla": 240, "chicken_wings": 220, "chocolate_cake": 150,
    "chocolate_mousse": 120, "churros": 100, "clam_chowder": 300,
    "club_sandwich": 250, "crab_cakes": 180, "creme_brulee": 120,
    "croque_madame": 230, "cup_cakes": 90, "deviled_eggs": 100, "donuts": 90,
    "dumplings": 180, "edamame": 150, "eggs_benedict": 220, "escargots": 120,
    "falafel": 180, "filet_mignon": 250, "fish_and_chips": 350, "foie_gras": 80,
    "french_fries": 150, "french_onion_soup": 300, "french_toast": 220,
    "fried_calamari": 200, "fried_rice": 300, "frozen_yogurt": 180,
    "garlic_bread": 130, "gnocchi": 260, "greek_salad": 220,
    "grilled_cheese_sandwich": 200, "grilled_salmon": 260, "guacamole": 120,
    "gyoza": 160, "hamburger": 260, "hot_and_sour_soup": 320, "hot_dog": 180,
    "huevos_rancheros": 280, "hummus": 150, "ice_cream": 150, "lasagna": 280,
    "lobster_bisque": 280, "lobster_roll_sandwich": 260,
    "macaroni_and_cheese": 300, "macarons": 60, "miso_soup": 250,
    "mussels": 280, "nachos": 300, "omelette": 220, "onion_rings": 150,
    "oysters": 180, "pad_thai": 320, "paella": 350, "pancakes": 250,
    "panna_cotta": 130, "peking_duck": 350, "pho": 400, "pizza": 350,
    "pork_chop": 280, "poutine": 320, "prime_rib": 350,
    "pulled_pork_sandwich": 260, "ramen": 380, "ravioli": 260,
    "red_velvet_cake": 150, "risotto": 300, "samosa": 160, "sashimi": 180,
    "scallops": 180, "seaweed_salad": 160, "shrimp_and_grits": 320,
    "spaghetti_bolognese": 320, "spaghetti_carbonara": 320,
    "spring_rolls": 160, "steak": 500, "strawberry_shortcake": 180,
    "sushi": 200, "tacos": 220, "takoyaki": 160, "tiramisu": 150,
    "tuna_tartare": 140, "waffles": 250,
}


def pick_device(force_cpu: bool = False) -> str:
    if force_cpu:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def load_model(weights_path: str, device: str):
    model = YOLO(weights_path)
    model.to(device)
    return model


def bytes_to_image(image_bytes: bytes):
    img = Image.open(BytesIO(image_bytes)).convert("RGB")
    return img  # YOLO понимает PIL.Image


def classify_bytes(model: YOLO, image_bytes: bytes, imgsz: int = 224, topk: int = 5):
    img = bytes_to_image(image_bytes)
    results = model(img, imgsz=imgsz, verbose=False)
    r = results[0]

    if not hasattr(r, "probs") or r.probs is None:
        raise RuntimeError("Модель не вернула вероятности (r.probs).")

    names = r.names
    probs = r.probs.data.detach().cpu()

    topk = max(1, min(topk, probs.numel()))
    conf, idx = torch.topk(probs, k=topk)

    items = []
    for c, i in zip(conf.tolist(), idx.tolist()):
        items.append(
            {
                "class_id": int(i),
                "class_name": names.get(int(i), str(i)),
                "score": float(c),
            }
        )

    return {"top1": items[0], "topk": items, "names": names}


def build_result_message(request_payload: dict, infer: dict):
    cls = infer["top1"]["class_name"]
    msg = {"top1_class": cls}

    w = FOOD_AVG_WEIGHT_G.get(cls) + randint(0, int(FOOD_AVG_WEIGHT_G[cls] * 0.4) )
    if w is not None:
        msg["estimated_weight_g"] = w

    # прокидываем image_id, если он был в запросе (для кафки)
    if "image_id" in request_payload:
        msg["image_id"] = request_payload["image_id"]

    return msg


def make_consumer(bootstrap: str, topic: str, group_id: str):
    return KafkaConsumer(
        topic,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        enable_auto_commit=True,
        auto_offset_reset="earliest",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )


def make_producer(bootstrap: str):
    return KafkaProducer(
        bootstrap_servers=bootstrap,
        acks="all",
        linger_ms=10,
        value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8") if isinstance(k, str) else k,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Kafka consumer: image_b64 → YOLOv11-cls → результат (или офлайн-тест)"
    )
    parser.add_argument("--weights", required=True)
    parser.add_argument("--bootstrap", default="localhost:9092")
    parser.add_argument("--input-topic", default="food_images")
    parser.add_argument("--output-topic", default="food_cls")
    parser.add_argument("--group-id", default="food-detector")
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--cpu", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-output-kafka", action="store_true")

    # НОВОЕ: офлайн-режим без Kafka
    parser.add_argument("--offline-test", action="store_true",
                        help="Протестировать на локальном файле без Kafka")
    parser.add_argument("--image-path", help="Путь к локальному изображению для офлайн-теста")

    args = parser.parse_args()

    device = pick_device(args.cpu)
    print(f"[INFO] device={device}")

    model = load_model(args.weights, device)

    # --- OFFLINE TEST MODE: без Kafka ---
    if args.offline_test:
        if not args.image_path:
            print("[ERR] Для --offline-test нужно указать --image-path path/to/image.jpg")
            return

        with open(args.image_path, "rb") as f:
            image_bytes = f.read()

        # имитируем payload, как будто он пришёл из Kafka
        payload = {
            "image_id": "offline_test",
            "image_b64": base64.b64encode(image_bytes).decode("ascii"),
        }

        infer = classify_bytes(model, image_bytes, imgsz=args.imgsz, topk=args.topk)
        result_msg = build_result_message(payload, infer)

        print("[OFFLINE-RESULT]")
        print(json.dumps(result_msg, ensure_ascii=False, indent=2))
        return
    # --- END OFFLINE TEST MODE ---

    # Ниже — реальная работа через Kafka
    print(
        f"[INFO] bootstrap={args.bootstrap}, input_topic={args.input_topic}, "
        f"output_topic={args.output_topic}"
    )

    consumer = make_consumer(args.bootstrap, args.input_topic, args.group_id)
    producer = None if args.no_output_kafka else make_producer(args.bootstrap)

    print("[INFO] Стартуем чтение из Kafka... (Ctrl+C для выхода)")

    try:
        for msg in consumer:
            try:
                payload = msg.value
                image_b64 = payload["image_b64"]
                image_bytes = base64.b64decode(image_b64)

                infer = classify_bytes(model, image_bytes, imgsz=args.imgsz, topk=args.topk)
                result_msg = build_result_message(payload, infer)
                key = result_msg["top1_class"]

                if args.debug:
                    print("[DEBUG] request image_id:", payload.get("image_id"))
                    print("[DEBUG] result:", json.dumps(result_msg, ensure_ascii=False))
                else:
                    print(
                        f"[OK] image_id={payload.get('image_id')} → "
                        f"class={result_msg['top1_class']}, "
                        f"weight={result_msg.get('estimated_weight_g')}"
                    )

                if producer is not None:
                    producer.send(args.output_topic, key=key, value=result_msg)

            except Exception as e:
                print(f"[ERR] Ошибка обработки сообщения: {e}")

    except KeyboardInterrupt:
        print("\n[INFO] Остановлено пользователем")

    if producer is not None:
        producer.flush()
        print("[INFO] Все результаты отправлены")


if __name__ == "__main__":
    main()

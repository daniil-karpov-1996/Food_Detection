# Food Detection Service (YOLOv11-cls + Kafka)

Сервис классифицирует изображения еды с помощью **YOLOv11-cls**  
и вычисляет **примерный вес блюда по классу** (эвристика).

Поддерживает два режима:
1) **Offline-режим** — классификация локального файла  
2) **Kafka-режим** — получение сообщения → классификация → публикация результата

Всё работает внутри Docker-контейнера.

---

## 0. Требования

Перед запуском убедитесь, что установлено:

- Docker / Docker Desktop  
- (Опционально) Docker Compose — для Kafka  
- Файл модели `best.pt` (YOLOv11-cls)

---

## 1. Сборка Docker-образа из GitHub

```bash
docker build -t food-detector:latest \
  https://github.com/daniil-karpov-1996/Food_Detection.git#main
```
## 2. Получение весов модели

Файл модели YOLO: `best.pt`

Положите его в удобное место:

- **Linux/macOS:** `/home/user/best.pt`
- **Windows:** `C:\best.pt`

## 3. Проверка offline-режима (без Kafka)

### Linux / macOS

```bash
docker run --rm \
  -v $(pwd)/best.pt:/app/best.pt \
  -v $(pwd)/test.jpg:/app/test.jpg \
  food-detector:latest \
  --weights /app/best.pt \
  --offline-test \
  --image-path /app/test.jpg
```
```json
{
  "top1_class": "steak",
  "estimated_weight_g": 320,
  "image_id": "offline_test"
}
```

## 4. Быстрый запуск Kafka через Docker Compose

Создайте файл `docker-compose.yml`:

```yaml
version: "3.8"

services:
  zookeeper:
    image: bitnami/zookeeper:3.9
    environment:
      ALLOW_ANONYMOUS_LOGIN: "yes"
    ports:
      - "2181:2181"

  kafka:
    image: bitnami/kafka:3
    environment:
      KAFKA_CFG_ZOOKEEPER_CONNECT: zookeeper:2181
      ALLOW_PLAINTEXT_LISTENER: "yes"
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"

```
Запуск Kafka:
```bash
docker compose up -d
```
Проверка работы:
```bash
docker compose ps
```

## 5. Создание Kafka-топиков

### Войти в контейнер Kafka:

```bash
docker exec -it kafka bash
```

Создать входной топик:
```bash
kafka-topics.sh --create --topic food_images --bootstrap-server localhost:9092
```

Создать топик для результатов:
```bash
kafka-topics.sh --create --topic food_cls --bootstrap-server localhost:9092
```

Проверить список:
```bash
kafka-topics.sh --list --bootstrap-server localhost:9092
```

## 6. Отправка изображения в Kafka

### Linux / macOS

```bash
base64 test.jpg \
  | jq -Rs '{image_id:"test1", image_b64:.}' \
  | kafka-console-producer.sh --topic food_images --bootstrap-server localhost:9092
```
## 7. Запуск сервиса в Kafka-режиме

### Linux / macOS

```bash
docker run --rm --network host \
  -v $(pwd)/best.pt:/app/best.pt \
  food-detector:latest \
  --weights /app/best.pt \
  --bootstrap localhost:9092 \
  --input-topic food_images \
  --output-topic food_cls \
  --group-id food-detector \
  --debug
```

## 8. Получение результатов из Kafka

```bash
kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic food_cls \
  --from-beginning
```

Пример результата:
```json
{"image_id":"test1","top1_class":"steak","estimated_weight_g":320}
```

## 9. Полная шпаргалка команд

```bash
# Сборка контейнера
docker build -t food-detector:latest https://github.com/daniil-karpov-1996/Food_Detection.git#main
```
# Offline тест
docker run --rm -v best.pt:/app/best.pt -v test.jpg:/app/test.jpg \
  food-detector:latest --weights /app/best.pt --offline-test --image-path /app/test.jpg

# Запуск Kafka
docker compose up -d

# Создание топиков
kafka-topics.sh --create --topic food_images --bootstrap-server localhost:9092
kafka-topics.sh --create --topic food_cls --bootstrap-server localhost:9092

# Запуск сервиса
docker run --rm --network host \
  -v best.pt:/app/best.pt \
  food-detector:latest \
  --weights /app/best.pt \
  --bootstrap localhost:9092 \
  --input-topic food_images \
  --output-topic food_cls \
  --group-id food-detector

# Чтение результатов
kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic food_cls --from-beginning

## 10. Аргументы сервиса

| Аргумент         | Описание |
|------------------|----------|
| `--weights PATH` | путь к весам YOLO |
| `--offline-test` | запуск в режиме offline |
| `--image-path`   | путь к изображению |
| `--bootstrap`    | адрес Kafka (`host:port`) |
| `--input-topic`  | топик для изображений |
| `--output-topic` | топик для классификаций |
| `--group-id`     | Kafka consumer group |
| `--debug`        | включить подробный лог |
| `--no-kafka`     | отключить Kafka, вывод в консоль |

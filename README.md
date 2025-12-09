# Food Detector (YOLOv11-cls + Kafka)

Сервис выполняет классификацию изображений еды с помощью YOLOv11-cls, определяет:

- `top1_class` — класс блюда из датасета Food-101;
- `estimated_weight_g` — примерный вес порции для этого класса.

Работает в двух режимах:

1. **Offline Test Mode** — проверка на локальном файле, без Kafka.  
2. **Kafka Consumer Mode** — чтение изображений из Kafka (в base64), инференс и отправка результата в другой топик.

---

## 1. Предварительные требования

На машине должны быть установлены:

- Docker (Docker Engine / Docker Desktop);
- (Опционально) Kafka — только если планируется использовать Kafka-режим.

Файл весов модели `best.pt` в образ не вшивается — он подключается как внешний файл.

---

## 2. Сборка образа из GitHub-репозитория

Docker умеет сам клонировать репозиторий и собирать образ из удалённого GitHub-URL.  
Для этого запустите:

```bash
docker build -t food-detector:latest \
  https://github.com/daniil-karpov-1996/Food_Detection.git#main

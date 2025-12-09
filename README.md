Food Detection Service (YOLOv11-cls + Kafka)

Этот сервис классифицирует изображения еды с помощью модели YOLOv11-cls и оценивает примерный вес блюда по классу.
Работает в Docker, поддерживает два режима:

Offline: локальная классификация файла

Kafka: прием изображений (base64, файл), классификация и отправка результата в топик Kafka

Python и внешние библиотеки на хосте не нужны — всё работает в контейнере!

0. Требования

Docker
 или совместимая среда

(Опционально) Docker Compose
 — для быстрого запуска Kafka

Скачанный вес модели best.pt (размести рядом с изображениями)

1. Сборка Docker-образа с GitHub
docker build -t food-detector:latest \
  https://github.com/daniil-karpov-1996/Food_Detection.git#main

2. Получи модель и тестовый файл

Скачай веса best.pt и положи их в папку с запуском

Помести туда тестовую картинку, например test.jpg

3. Проверь offline-режим (без Kafka)
docker run --rm -v best.pt:/app/best.pt -v test.jpg:/app/test.jpg \
  food-detector:latest --weights /app/best.pt --offline-test --image-path /app/test.jpg


Результат: в консоли выведется top1_class и estimated_weight_g для изображения.

4. Быстрый запуск Kafka (если нужно)

Если у тебя нет работающего Kafka, подними его в Docker:

git clone https://github.com/conduktor/kafka-stack-docker-compose
cd kafka-stack-docker-compose
docker compose up -d


По умолчанию Kafka будет доступна на localhost:9092.

5. Создай топики

Выполни в отдельном терминале (можно из контейнера Kafka):

# Для передачи изображений в сервис
docker exec -it <kafka_container_id> \
  kafka-topics --create --topic food_images --bootstrap-server localhost:9092

# Для получения результатов
docker exec -it <kafka_container_id> \
  kafka-topics --create --topic food_cls --bootstrap-server localhost:9092

6. Запусти сервис в режиме Kafka
docker run --rm --network host \
  -v best.pt:/app/best.pt food-detector:latest \
  --weights /app/best.pt \
  --bootstrap localhost:9092 \
  --input-topic food_images \
  --output-topic food_cls \
  --group-id food-detector

Параметры запуска
Параметр	Описание
--weights	Путь до весов YOLOv11-cls (/app/best.pt)
--bootstrap	Адрес Kafka bootstrap (например, localhost:9092)
--input-topic	Топик Kafka для входящих изображений
--output-topic	Топик Kafka, куда отправляется результат
--group-id	(опционально) ID consumer group
--debug	(опционально) Выводит подробный лог отправляемых сообщений
--no-kafka	(опционально) Только консольный вывод, не использует Kafka
7. Отправь изображение в сервис

Формат: base64 изображения или бинарный файл (в зависимости от настроек и клиента).

Пример отправки с помощью kafka-console-producer (см. документацию Kafka Tools
):

cat test.jpg | base64 | \
  kafka-console-producer --topic food_images --bootstrap-server localhost:9092

8. Получи результат из output topic
kafka-console-consumer --topic food_cls --from-beginning --bootstrap-server localhost:9092


Ответ:
JSON с двумя ключами — top1_class (класс блюда) и estimated_weight_g (примерный вес).

9. Пример типового сценария использования

Собрать образ Docker с помощью команды выше.

Скачать best.pt, поместить в папку с запуском.

Проверить работу на локальном файле:

docker run --rm -v best.pt:/app/best.pt -v test.jpg:/app/test.jpg \
  food-detector:latest --weights /app/best.pt --offline-test --image-path /app/test.jpg


Поднять Kafka:

docker compose up -d


Создать нужные топики (см. выше).

Запустить сервис в Kafka-режиме:

docker run --rm --network host -v best.pt:/app/best.pt food-detector:latest \
  --weights /app/best.pt --bootstrap localhost:9092 \
  --input-topic food_images --output-topic food_cls --group-id food-detector


Отправить изображение через Kafka-продьюсер (см. пример выше).

Принять результат через Kafka-консьюмер.

10. Полезные параметры и расширения

--debug — включает расширенный лог вывода.

--no-kafka — отключает Kafka, результат только в консоль (удобно для теста).

Можно менять имена топиков и параметры bootstrap под свою инфраструктуру.

Для передачи файла напрямую смотри параметры/формат в документации Kafka-продьюсера.
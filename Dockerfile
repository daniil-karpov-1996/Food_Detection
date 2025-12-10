FROM python:3.11-slim

# Необязательно, но полезно для сборки некоторых пакетов
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libgl1 \
    libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала зависимости, чтобы слои кэша не инвалидировать лишний раз
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Кладём сам код
COPY food_detect.py .

# По умолчанию ENTRYPOINT вызывает наш скрипт,
# а все аргументы из `docker run` будут добавляться после него
ENTRYPOINT ["python", "food_detect.py"]

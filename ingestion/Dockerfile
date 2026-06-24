FROM python:3.11-slim

WORKDIR /app

# Системные зависимости минимальны: asyncpg/aiohttp ставятся как wheels.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Воркер: бэкофилл при старте → затем стрим. Перезапуск разруливает compose.
CMD ["python", "-u", "main.py"]

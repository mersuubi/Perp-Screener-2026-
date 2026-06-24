# Локальная разработка

## Через Docker (рекомендуется)

```bash
cp .env.example .env
docker compose up -d --build
docker compose logs -f ingestion   # видно прогресс бэкофилла
```

- API + Swagger: http://localhost:8000/docs
- Frontend: http://localhost:5173
- БД: `localhost:5432` (creds из `.env`)

Первый старт: TimescaleDB выполнит `db/*.sql` (extensions → schema → hypertables →
continuous aggregates → views → functions), затем ingestion начнёт бэкофилл.

> ⚠️ SQL из `db/` выполняется только при **первой** инициализации тома `pgdata`.
> Чтобы пере-применить схему с нуля: `docker compose down -v` (удалит данные).

## Без Docker

Нужны локальные PostgreSQL+TimescaleDB и Redis.

```bash
# 1. БД: применить SQL по порядку
psql "$DATABASE_URL" -f db/01_extensions.sql
psql "$DATABASE_URL" -f db/02_schema.sql
psql "$DATABASE_URL" -f db/03_hypertables.sql
psql "$DATABASE_URL" -f db/04_continuous_aggregates.sql
psql "$DATABASE_URL" -f db/05_analytics_views.sql
psql "$DATABASE_URL" -f db/06_functions.sql

# 2. Ингест
cd ingestion && pip install -r requirements.txt && python main.py

# 3. API
cd api && pip install -r requirements.txt && uvicorn main:app --reload

# 4. Фронт
cd frontend && npm install && npm run dev
```

Переопределите хосты в `.env` на `localhost`, если сервисы вне Docker
(`POSTGRES_HOST=localhost`, `REDIS_HOST=localhost` и соответствующий `DATABASE_URL`).

## Полезные SQL-проверки

```sql
-- сколько свечей по символам
SELECT symbol, count(*), min(bucket), max(bucket) FROM ohlcv GROUP BY symbol;

-- витрина скринера
SELECT symbol, ret_1h, volume_zscore, vol_percentile FROM metric_snapshot
ORDER BY vol_percentile DESC LIMIT 20;

-- ручной прогон скринера
SELECT * FROM run_screener('[{"field":"volume_zscore","op":">","value":2}]'::jsonb, 'manual');
```

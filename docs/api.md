# API

FastAPI генерирует OpenAPI автоматически. Живые артефакты при запущенном API:

- Swagger UI: **http://localhost:8000/docs**
- ReDoc: **http://localhost:8000/redoc**
- OpenAPI JSON: **http://localhost:8000/openapi.json**

## Эндпоинты

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/health` | Liveness + проверка коннекта к БД |
| GET | `/instruments` | Список активных инструментов |
| GET | `/metrics?sort=&desc=&limit=` | Витрина скринера (VIEW `metric_snapshot`) |
| GET | `/ohlcv/{symbol}?timeframe=1m\|5m\|1h&limit=` | История свечей |
| POST | `/screener/run` | Прогнать скринер по фильтрам (сохраняет прогон) |
| GET | `/screener/runs?limit=` | История прогонов |
| GET | `/screener/runs/{run_id}` | Результаты конкретного прогона |
| WS | `/ws/live` | Live-тики (kline + mark price) из Redis |

## Пример: запуск скринера

```bash
curl -X POST http://localhost:8000/screener/run \
  -H "Content-Type: application/json" \
  -d '{
        "preset": "volume_spike",
        "filters": [
          {"field": "volume_zscore", "op": ">", "value": 3},
          {"field": "ret_1h",        "op": ">", "value": 0.03}
        ]
      }'
```

Ответ:

```json
{
  "run_id": 12,
  "ran_at": "2025-01-01T12:00:00Z",
  "count": 4,
  "hits": [
    {"symbol": "SOLUSDT", "metrics": { "...": "снимок метрик" }}
  ]
}
```

Прогон сохраняется в `screener_run` / `screener_hit` — его можно поднять позже через
`GET /screener/runs/{run_id}`. Это и есть воспроизводимость скрининга.

## Допустимые поля фильтров

`ret_5m`, `ret_1h`, `ret_24h`, `vol_24h`, `range_pct_24h`, `volatility`,
`volume_zscore`, `funding_rate`, `funding_zscore`, `oi_change_1h`, `oi_change_24h`,
`vol_percentile`, `volatility_rank`, `funding_extremity_rank`.

Операторы: `>`, `>=`, `<`, `<=`, `=`, `<>`. Поля и операторы валидируются по белому
списку и на стороне API (Pydantic), и в серверной функции `run_screener` — защита от
SQL-инъекций.

# Architecture Decision Records

Короткие записи о принятых архитектурных решениях: контекст → решение → почему →
альтернативы → последствия. ADR показывают, что решения приняты осознанно.

| # | Решение |
|---|---|
| [0001](0001-timescaledb.md) | TimescaleDB вместо голого PostgreSQL |
| [0002](0002-continuous-aggregates.md) | Continuous aggregates для даунсемплинга |
| [0003](0003-redis-pubsub.md) | Redis pub/sub между ингестом и API |
| [0004](0004-separate-ingestion-process.md) | Отдельный ингест-процесс |
| [0005](0005-no-realtime-orderbook.md) | Отказ от real-time реконструкции стакана |

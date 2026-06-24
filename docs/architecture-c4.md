# Архитектура — C4

C4-модель: уровни Context → Container → (Component опционально).

## Level 1 — System Context

Кто пользуется системой и с какими внешними системами она взаимодействует.

```mermaid
flowchart TB
    user([Трейдер / Аналитик])
    subgraph sys[Perp Screener]
      core[Скринер перпов]
    end
    binance[(Binance Futures API<br/>внешняя система)]

    user -->|смотрит метрики, запускает скрининг| core
    core -->|REST + WebSocket: OHLCV, funding, OI| binance
```

## Level 2 — Container

Из каких развёртываемых единиц состоит система и как они общаются.

```mermaid
flowchart LR
    user([Пользователь])

    subgraph compose[Docker Compose]
      ing[Ingestion service<br/>Python asyncio<br/>backfill + WS stream]
      api[API<br/>FastAPI]
      fe[Frontend<br/>vanilla TS + lightweight-charts]
      ts[(TimescaleDB<br/>PostgreSQL 16)]
      rd[(Redis<br/>pub/sub)]
    end

    binance[(Binance Futures API)]

    ing -->|REST backfill / WS stream| binance
    ing -->|upsert OHLCV/funding/OI| ts
    ing -->|publish live ticks| rd
    api -->|SQL: история, метрики, скринер| ts
    rd -.->|live ticks| api
    fe -->|REST: история, метрики| api
    fe <-.->|WebSocket: live| api
    user --> fe
```

**Почему именно так** (детали — в `adr/`):
- **Отдельный ingestion-процесс** — держит WS-коннекты и пишет в БД независимо от API
  (ADR-0004). API можно перезапустить, не теряя стрим.
- **Redis между ингестом и API** — развязка: ингест публикует тики, API подписан и
  фанаутит клиентам. Ни один не блокирует другой (ADR-0003).
- **TimescaleDB** — гипертаблицы + continuous aggregates под тайм-серии (ADR-0001).
- **Тонкий фронт** — только рендер, вся аналитика в БД.

## Level 3 — Component (API, опционально)

Внутреннее устройство контейнера API.

```mermaid
flowchart TB
    subgraph api[API · FastAPI]
      r_instr[router: instruments<br/>/instruments, /metrics]
      r_ohlcv[router: ohlcv<br/>/ohlcv/:symbol]
      r_scr[router: screener<br/>/screener/run, /runs]
      r_ws[router: ws<br/>/ws/live]
      dbpool[asyncpg pool]
    end
    ts[(TimescaleDB)]
    rd[(Redis)]

    r_instr --> dbpool --> ts
    r_ohlcv --> dbpool
    r_scr --> dbpool
    r_scr -->|run_screener jsonb| ts
    r_ws -->|subscribe| rd
```

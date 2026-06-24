-- ============================================================================
-- 02_schema.sql — базовые таблицы
-- ER-диаграмма: docs/er-diagram.md
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Справочник инструментов (перпов). Малая таблица, обычный heap.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instrument (
    symbol        TEXT PRIMARY KEY,                 -- напр. 'BTCUSDT'
    exchange      TEXT NOT NULL DEFAULT 'binance',
    base          TEXT NOT NULL,                    -- 'BTC'
    quote         TEXT NOT NULL,                    -- 'USDT'
    contract_type TEXT NOT NULL DEFAULT 'perpetual',
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    added_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE instrument IS 'Справочник торгуемых перпетуалов';

-- ----------------------------------------------------------------------------
-- OHLCV — сырые 1m-свечи. Станет ГИПЕРТАБЛИЦЕЙ в 03_hypertables.sql.
-- Составной PK (symbol, bucket) обеспечивает идемпотентность ингеста:
--   INSERT ... ON CONFLICT (symbol, bucket) DO UPDATE — реконнект WS не плодит дубли.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ohlcv (
    symbol TEXT        NOT NULL REFERENCES instrument(symbol),
    bucket TIMESTAMPTZ NOT NULL,                    -- начало свечи, всегда UTC
    open   NUMERIC(20, 8) NOT NULL,
    high   NUMERIC(20, 8) NOT NULL,
    low    NUMERIC(20, 8) NOT NULL,
    close  NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(30, 8) NOT NULL,                 -- базовый объём
    -- закрыта ли свеча: WS присылает «формирующуюся» свечу несколько раз
    is_closed BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (symbol, bucket)
);

COMMENT ON TABLE ohlcv IS '1m OHLCV, гипертаблица; (symbol, bucket) — идемпотентный ключ';

-- ----------------------------------------------------------------------------
-- Funding rate — ставка финансирования (раз в ~8ч у Binance).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS funding (
    symbol       TEXT        NOT NULL REFERENCES instrument(symbol),
    ts           TIMESTAMPTZ NOT NULL,
    funding_rate NUMERIC(12, 8) NOT NULL,           -- доля, напр. 0.0001 = 0.01%
    PRIMARY KEY (symbol, ts)
);

COMMENT ON TABLE funding IS 'Ставка финансирования перпов';

-- ----------------------------------------------------------------------------
-- Open interest — открытый интерес (снимок каждые N минут).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS open_interest (
    symbol TEXT        NOT NULL REFERENCES instrument(symbol),
    ts     TIMESTAMPTZ NOT NULL,
    oi     NUMERIC(30, 8) NOT NULL,                 -- в контрактах/базовой валюте
    PRIMARY KEY (symbol, ts)
);

COMMENT ON TABLE open_interest IS 'Снимки открытого интереса';

-- ----------------------------------------------------------------------------
-- Прогоны скринера: сохраняем НАБОР ФИЛЬТРОВ и его результат.
-- Это превращает «фильтр в моменте» в воспроизводимый артефакт.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS screener_run (
    id      BIGSERIAL PRIMARY KEY,
    ran_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    preset  TEXT,                                   -- имя пресета, если есть
    filters JSONB NOT NULL                          -- условия скрининга
);

COMMENT ON TABLE screener_run IS 'История прогонов скринера (фильтры + время)';

CREATE TABLE IF NOT EXISTS screener_hit (
    run_id  BIGINT NOT NULL REFERENCES screener_run(id) ON DELETE CASCADE,
    symbol  TEXT   NOT NULL REFERENCES instrument(symbol),
    metrics JSONB  NOT NULL,                        -- снимок метрик на момент прогона
    PRIMARY KEY (run_id, symbol)
);

COMMENT ON TABLE screener_hit IS 'Инструменты, прошедшие фильтр в конкретном прогоне';

-- Индекс под выборку прогонов по времени.
CREATE INDEX IF NOT EXISTS idx_screener_run_ran_at ON screener_run (ran_at DESC);

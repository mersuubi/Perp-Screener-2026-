-- ============================================================================
-- 04_continuous_aggregates.sql — даунсемплинг 1m → 5m → 1h
-- Continuous aggregate = материализованное представление, которое TimescaleDB
-- ИНКРЕМЕНТАЛЬНО пересчитывает по мере прихода новых данных. Фронт читает 5m/1h,
-- а не миллион 1m-строк. ADR-0002.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 5-минутные свечи из 1m.
-- OHLC агрегируется корректно: open = первое, close = последнее, high/low — экстремумы.
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_5m
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket(INTERVAL '5 minutes', bucket) AS bucket,
    first(open,  bucket) AS open,
    max(high)            AS high,
    min(low)             AS low,
    last(close,  bucket) AS close,
    sum(volume)          AS volume
FROM ohlcv
GROUP BY symbol, time_bucket(INTERVAL '5 minutes', bucket)
WITH NO DATA;

-- ----------------------------------------------------------------------------
-- Часовые свечи. Берём из 1m (continuous aggregate поверх hypertable).
-- ----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1h
WITH (timescaledb.continuous) AS
SELECT
    symbol,
    time_bucket(INTERVAL '1 hour', bucket) AS bucket,
    first(open,  bucket) AS open,
    max(high)            AS high,
    min(low)             AS low,
    last(close,  bucket) AS close,
    sum(volume)          AS volume
FROM ohlcv
GROUP BY symbol, time_bucket(INTERVAL '1 hour', bucket)
WITH NO DATA;

-- ----------------------------------------------------------------------------
-- Политики автообновления: пересчитывать «хвост» с запаздыванием.
--   start_offset — насколько назад смотреть, end_offset — отступ от now()
--   (свежие, ещё формирующиеся бакеты не трогаем).
-- ----------------------------------------------------------------------------
SELECT add_continuous_aggregate_policy('ohlcv_5m',
    start_offset      => INTERVAL '3 hours',
    end_offset        => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists     => TRUE);

SELECT add_continuous_aggregate_policy('ohlcv_1h',
    start_offset      => INTERVAL '3 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists     => TRUE);

-- Индексы под выборки по символу/времени на агрегатах.
CREATE INDEX IF NOT EXISTS idx_ohlcv_5m_symbol_bucket
    ON ohlcv_5m (symbol, bucket DESC);
CREATE INDEX IF NOT EXISTS idx_ohlcv_1h_symbol_bucket
    ON ohlcv_1h (symbol, bucket DESC);

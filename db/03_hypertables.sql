-- ============================================================================
-- 03_hypertables.sql — превращаем тайм-серийные таблицы в гипертаблицы
-- Гипертаблица = автоматическое партиционирование по времени (chunks).
-- Это даёт: быстрые выборки по диапазону, дешёвое удаление старого,
-- параллельное сжатие. ADR-0001.
-- ============================================================================

-- chunk_time_interval подобран под нагрузку:
--  - ohlcv 1m: 1 день на чанк (≈ 1440 строк * N символов) — компромисс
--    между числом чанков и их размером.
SELECT create_hypertable(
    'ohlcv', 'bucket',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

SELECT create_hypertable(
    'funding', 'ts',
    chunk_time_interval => INTERVAL '30 days',
    if_not_exists => TRUE
);

SELECT create_hypertable(
    'open_interest', 'ts',
    chunk_time_interval => INTERVAL '7 days',
    if_not_exists => TRUE
);

-- ----------------------------------------------------------------------------
-- Индексы. У гипертаблиц PK (symbol, bucket) уже создан; добавляем индекс
-- под «последние свечи по символу» (частый паттерн дашборда).
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_bucket_desc
    ON ohlcv (symbol, bucket DESC);

CREATE INDEX IF NOT EXISTS idx_funding_symbol_ts_desc
    ON funding (symbol, ts DESC);

CREATE INDEX IF NOT EXISTS idx_oi_symbol_ts_desc
    ON open_interest (symbol, ts DESC);

-- ----------------------------------------------------------------------------
-- Сжатие старых чанков ohlcv (колоночное) — экономит место на истории.
-- Сегментируем по symbol, упорядочиваем по времени.
-- ----------------------------------------------------------------------------
ALTER TABLE ohlcv SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol',
    timescaledb.compress_orderby = 'bucket DESC'
);

-- Сжимать чанки старше 7 дней (политика фонового джоба).
SELECT add_compression_policy('ohlcv', INTERVAL '7 days', if_not_exists => TRUE);

-- Опционально: хранить не больше 90 дней сырых 1m-свечей
-- (агрегаты 5m/1h остаются — у них своя политика).
SELECT add_retention_policy('ohlcv', INTERVAL '90 days', if_not_exists => TRUE);

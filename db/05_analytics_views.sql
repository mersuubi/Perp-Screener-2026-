-- ============================================================================
-- 05_analytics_views.sql — аналитический слой (главный SQL-флекс)
-- Все метрики считаются в БД. API только параметризует и отдаёт результат.
-- Используются: оконные функции (PARTITION BY / frame clause / FIRST_VALUE),
-- перцентили (percent_rank), агрегаты по диапазону времени.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- VIEW ohlcv_5m_enriched — скользящие метрики поверх 5m-свечей.
--   vol_20        — скользящая волатильность (stddev close за 20 баров = 100 мин)
--   volume_zscore — насколько объём аномален относительно своего окна
--   ret_window    — доходность за окно (close / первый close в окне − 1)
-- Окно именованное (WINDOW w AS ...), фрейм ROWS BETWEEN 19 PRECEDING.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW ohlcv_5m_enriched AS
SELECT
    symbol,
    bucket,
    open, high, low, close, volume,
    stddev(close) OVER w                                              AS vol_20,
    (volume - avg(volume) OVER w) / nullif(stddev(volume) OVER w, 0)  AS volume_zscore,
    close / nullif(first_value(close) OVER w, 0) - 1                  AS ret_window,
    close / nullif(lag(close) OVER (PARTITION BY symbol ORDER BY bucket), 0) - 1
                                                                      AS ret_5m
FROM ohlcv_5m
WINDOW w AS (
    PARTITION BY symbol
    ORDER BY bucket
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
);

COMMENT ON VIEW ohlcv_5m_enriched IS
    'Скользящие метрики на 5m: волатильность, z-score объёма, доходность за окно';

-- ----------------------------------------------------------------------------
-- VIEW latest_price — последняя цена и время по каждому символу.
-- DISTINCT ON — идиоматичный Postgres-способ взять «последнюю строку в группе».
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW latest_price AS
SELECT DISTINCT ON (symbol)
    symbol,
    bucket AS ts,
    close  AS price
FROM ohlcv
ORDER BY symbol, bucket DESC;

COMMENT ON VIEW latest_price IS 'Последняя известная цена по символу';

-- ----------------------------------------------------------------------------
-- VIEW funding_latest — текущий funding + его z-score в собственной истории
-- (насколько ставка экстремальна для этого инструмента за 30 дней).
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW funding_latest AS
WITH stats AS (
    SELECT symbol,
           avg(funding_rate)    AS avg_fr,
           stddev(funding_rate) AS std_fr
    FROM funding
    WHERE ts >= now() - INTERVAL '30 days'
    GROUP BY symbol
),
last_fr AS (
    SELECT DISTINCT ON (symbol) symbol, ts, funding_rate
    FROM funding
    ORDER BY symbol, ts DESC
)
SELECT
    l.symbol,
    l.ts,
    l.funding_rate,
    (l.funding_rate - s.avg_fr) / nullif(s.std_fr, 0) AS funding_zscore
FROM last_fr l
LEFT JOIN stats s USING (symbol);

COMMENT ON VIEW funding_latest IS 'Текущий funding rate и его z-score за 30 дней';

-- ----------------------------------------------------------------------------
-- VIEW oi_change — изменение open interest за 1ч и 24ч (приток/отток позиций).
-- Используем оконный lag по упорядоченной по времени серии снимков.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW oi_change AS
WITH latest AS (
    SELECT DISTINCT ON (symbol) symbol, ts, oi
    FROM open_interest
    ORDER BY symbol, ts DESC
),
hist AS (
    SELECT symbol,
           -- ближайший снимок к точке «час/сутки назад»
           (SELECT oi FROM open_interest o2
             WHERE o2.symbol = l.symbol AND o2.ts <= now() - INTERVAL '1 hour'
             ORDER BY o2.ts DESC LIMIT 1)  AS oi_1h_ago,
           (SELECT oi FROM open_interest o2
             WHERE o2.symbol = l.symbol AND o2.ts <= now() - INTERVAL '24 hours'
             ORDER BY o2.ts DESC LIMIT 1)  AS oi_24h_ago
    FROM latest l
)
SELECT
    l.symbol,
    l.oi,
    l.oi / nullif(h.oi_1h_ago, 0)  - 1 AS oi_change_1h,
    l.oi / nullif(h.oi_24h_ago, 0) - 1 AS oi_change_24h
FROM latest l
LEFT JOIN hist h USING (symbol);

COMMENT ON VIEW oi_change IS 'Изменение open interest за 1ч и 24ч';

-- ----------------------------------------------------------------------------
-- VIEW window_returns — доходность за 5м / 1ч / 24ч на основе 5m-свечей.
-- Коррелированные подзапросы берут ближайшую закрытую свечу к нужному лагу.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW window_returns AS
WITH last_close AS (
    SELECT DISTINCT ON (symbol) symbol, bucket, close
    FROM ohlcv_5m
    ORDER BY symbol, bucket DESC
)
SELECT
    lc.symbol,
    lc.close AS price,
    lc.close / nullif((SELECT close FROM ohlcv_5m c
        WHERE c.symbol = lc.symbol AND c.bucket <= now() - INTERVAL '5 minutes'
        ORDER BY c.bucket DESC LIMIT 1), 0) - 1 AS ret_5m,
    lc.close / nullif((SELECT close FROM ohlcv_5m c
        WHERE c.symbol = lc.symbol AND c.bucket <= now() - INTERVAL '1 hour'
        ORDER BY c.bucket DESC LIMIT 1), 0) - 1 AS ret_1h,
    lc.close / nullif((SELECT close FROM ohlcv_5m c
        WHERE c.symbol = lc.symbol AND c.bucket <= now() - INTERVAL '24 hours'
        ORDER BY c.bucket DESC LIMIT 1), 0) - 1 AS ret_24h
FROM last_close lc;

COMMENT ON VIEW window_returns IS 'Доходность за 5м/1ч/24ч по символу';

-- ----------------------------------------------------------------------------
-- VIEW metric_snapshot — ВИТРИНА СКРИНЕРА.
-- Одна строка на инструмент со всеми метриками + рыночные ранги/перцентили.
-- Это объект, который API отдаёт в таблицу и по которому фильтрует скринер.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW metric_snapshot AS
WITH vol24 AS (                       -- объём и диапазон за сутки
    SELECT symbol,
           sum(volume)             AS vol_24h,
           max(high) - min(low)    AS range_24h,
           (max(high) - min(low)) / nullif(min(low), 0) AS range_pct_24h
    FROM ohlcv_5m
    WHERE bucket >= now() - INTERVAL '24 hours'
    GROUP BY symbol
),
roll AS (                             -- последняя строка enriched-метрик
    SELECT DISTINCT ON (symbol) symbol, vol_20, volume_zscore
    FROM ohlcv_5m_enriched
    ORDER BY symbol, bucket DESC
)
SELECT
    i.symbol,
    i.base,
    i.quote,
    wr.price,
    wr.ret_5m,
    wr.ret_1h,
    wr.ret_24h,
    v.vol_24h,
    v.range_pct_24h,
    r.vol_20            AS volatility,
    r.volume_zscore,
    fl.funding_rate,
    fl.funding_zscore,
    oc.oi,
    oc.oi_change_1h,
    oc.oi_change_24h,
    -- РЫНОЧНЫЕ РАНГИ (перцентили по всем инструментам):
    percent_rank() OVER (ORDER BY v.vol_24h)            AS vol_percentile,
    rank()         OVER (ORDER BY v.range_pct_24h DESC) AS volatility_rank,
    rank()         OVER (ORDER BY abs(fl.funding_rate) DESC NULLS LAST) AS funding_extremity_rank
FROM instrument i
LEFT JOIN window_returns wr ON wr.symbol = i.symbol
LEFT JOIN vol24          v  ON v.symbol  = i.symbol
LEFT JOIN roll           r  ON r.symbol  = i.symbol
LEFT JOIN funding_latest fl ON fl.symbol = i.symbol
LEFT JOIN oi_change      oc ON oc.symbol = i.symbol
WHERE i.is_active;

COMMENT ON VIEW metric_snapshot IS
    'Витрина скринера: метрики + рыночные перцентили/ранги, 1 строка на инструмент';

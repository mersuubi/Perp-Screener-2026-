-- ============================================================================
-- screener_ranking.sql — ранжирование кандидатов скринера за последние 24ч
-- Демонстрирует: CTE, агрегаты по диапазону времени, percent_rank(), rank().
-- Идея: найти инструменты с одновременно высоким объёмом (ликвидность)
--        и большим диапазоном (волатильность) — кандидаты на движение.
-- ============================================================================
WITH last_24h AS (
    SELECT symbol,
           sum(volume)             AS vol_24h,
           max(close) - min(close) AS range_24h
    FROM ohlcv_5m
    WHERE bucket >= now() - INTERVAL '24 hours'
    GROUP BY symbol
)
SELECT
    symbol,
    vol_24h,
    range_24h,
    -- перцентиль по объёму: 0.0 = самый тихий, 1.0 = самый объёмный
    percent_rank() OVER (ORDER BY vol_24h)            AS vol_percentile,
    -- ранг по диапазону: 1 = самый волатильный
    rank()         OVER (ORDER BY range_24h DESC)     AS volatility_rank
FROM last_24h
ORDER BY vol_percentile DESC;

-- ============================================================================
-- funding_extremes.sql — экстремумы ставки финансирования
-- Высокий положительный funding = лонги перегреты (платят шортам),
-- сильный отрицательный = шорты перегреты. Считаем z-score внутри истории
-- каждого инструмента, чтобы сравнивать «перегрев» между разными перпами.
-- Демонстрирует: оконные агрегаты как «среднее/стд по партиции», QUALIFY-аналог
-- через подзапрос.
-- ============================================================================
WITH scored AS (
    SELECT
        symbol,
        ts,
        funding_rate,
        avg(funding_rate)    OVER (PARTITION BY symbol) AS avg_fr,
        stddev(funding_rate) OVER (PARTITION BY symbol) AS std_fr,
        row_number()         OVER (PARTITION BY symbol ORDER BY ts DESC) AS rn
    FROM funding
    WHERE ts >= now() - INTERVAL '30 days'
)
SELECT
    symbol,
    ts,
    funding_rate,
    (funding_rate - avg_fr) / nullif(std_fr, 0) AS funding_zscore
FROM scored
WHERE rn = 1                                   -- только последняя ставка по символу
ORDER BY abs((funding_rate - avg_fr) / nullif(std_fr, 0)) DESC NULLS LAST;

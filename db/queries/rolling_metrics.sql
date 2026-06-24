-- ============================================================================
-- rolling_metrics.sql — скользящая волатильность + z-score объёма + доходность
-- Демонстрирует: PARTITION BY, frame clause (ROWS BETWEEN), FIRST_VALUE,
--                именованное окно WINDOW w AS.
-- Окно = 20 баров по 5 минут = 100 минут истории на каждую точку.
-- ============================================================================
SELECT
    symbol,
    bucket,
    close,
    -- скользящая волатильность: разброс close за окно
    stddev(close) OVER w                                              AS vol_20,
    -- z-score объёма: (текущий − среднее) / стд по окну → «насколько аномален объём»
    (volume - avg(volume) OVER w) / nullif(stddev(volume) OVER w, 0)  AS volume_zscore,
    -- доходность за окно: цена сейчас относительно цены в начале окна
    close / first_value(close) OVER w - 1                            AS ret_window
FROM ohlcv_5m
WINDOW w AS (
    PARTITION BY symbol
    ORDER BY bucket
    ROWS BETWEEN 19 PRECEDING AND CURRENT ROW
)
ORDER BY symbol, bucket;

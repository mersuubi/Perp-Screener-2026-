-- ============================================================================
-- 06_functions.sql — серверная логика скринера
-- run_screener(filters) применяет набор условий к metric_snapshot,
-- сохраняет прогон (screener_run) и попадания (screener_hit) и возвращает их.
-- Динамический SQL строится из БЕЛОГО СПИСКА полей/операторов — без инъекций.
-- ============================================================================

-- Допустимые поля скрининга и операторы. Защита от SQL-инъекций:
-- значения из jsonb приходят как параметры, имена полей/операторов
-- сверяются с этим списком.
CREATE OR REPLACE FUNCTION _screener_is_valid_field(field TEXT)
RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
    SELECT field = ANY (ARRAY[
        'ret_5m','ret_1h','ret_24h','vol_24h','range_pct_24h','volatility',
        'volume_zscore','funding_rate','funding_zscore','oi_change_1h',
        'oi_change_24h','vol_percentile','volatility_rank','funding_extremity_rank'
    ]);
$$;

CREATE OR REPLACE FUNCTION _screener_is_valid_op(op TEXT)
RETURNS BOOLEAN LANGUAGE sql IMMUTABLE AS $$
    SELECT op = ANY (ARRAY['>','>=','<','<=','=','<>']);
$$;

-- ----------------------------------------------------------------------------
-- run_screener(filters jsonb, preset text)
--   filters := [{"field":"volume_zscore","op":">","value":3},
--               {"field":"ret_1h","op":">","value":0.05}]
-- Возвращает строки metric_snapshot, прошедшие ВСЕ условия (AND).
-- Побочный эффект: пишет в screener_run / screener_hit.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION run_screener(filters JSONB, preset TEXT DEFAULT NULL)
RETURNS TABLE (symbol TEXT, metrics JSONB)
LANGUAGE plpgsql AS $$
DECLARE
    cond      JSONB;
    field     TEXT;
    op        TEXT;
    val       NUMERIC;
    where_sql TEXT := 'TRUE';
    new_run_id BIGINT;
    dyn_sql   TEXT;
BEGIN
    -- Собираем WHERE из условий. Имена полей валидируем по белому списку,
    -- а числовые значения подставляем безопасно через %L, так как val гарантированно NUMERIC.
    FOR cond IN SELECT * FROM jsonb_array_elements(COALESCE(filters, '[]'::jsonb))
    LOOP
        field := cond->>'field';
        op    := cond->>'op';
        val   := (cond->>'value')::NUMERIC;

        IF NOT _screener_is_valid_field(field) THEN
            RAISE EXCEPTION 'Недопустимое поле скрининга: %', field;
        END IF;
        IF NOT _screener_is_valid_op(op) THEN
            RAISE EXCEPTION 'Недопустимый оператор: %', op;
        END IF;

        where_sql := where_sql || format(' AND %I %s %L::NUMERIC', field, op, val);
    END LOOP;

    -- Фиксируем прогон.
    INSERT INTO screener_run (preset, filters)
    VALUES (preset, COALESCE(filters, '[]'::jsonb))
    RETURNING id INTO new_run_id;

    -- Выполняем фильтрацию и сохраняем попадания одним запросом.
    dyn_sql := format($f$
        WITH matched AS (
            SELECT * FROM metric_snapshot WHERE %s
        ),
        ins AS (
            INSERT INTO screener_hit (run_id, symbol, metrics)
            SELECT %s, m.symbol, to_jsonb(m) FROM matched m
            RETURNING symbol, metrics
        )
        SELECT symbol, metrics FROM ins ORDER BY symbol
    $f$, where_sql, new_run_id);

    RETURN QUERY EXECUTE dyn_sql;
END;
$$;

COMMENT ON FUNCTION run_screener(JSONB, TEXT) IS
    'Применяет jsonb-фильтры к metric_snapshot, сохраняет прогон и возвращает попадания';

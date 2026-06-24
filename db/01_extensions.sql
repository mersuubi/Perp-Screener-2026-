-- ============================================================================
-- 01_extensions.sql — расширения PostgreSQL
-- Выполняется первым при инициализации кластера (docker-entrypoint-initdb.d).
-- ============================================================================

-- TimescaleDB: гипертаблицы (автопартиционирование по времени) + continuous aggregates.
-- ADR-0001: почему TimescaleDB, а не голый Postgres — docs/adr/0001-timescaledb.md
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- timescaledb_toolkit — опционально (есть в образе timescaledb-ha, нет в обычном
-- timescaledb). Проект его НЕ требует: percent_rank/stddev/first/last — это
-- ядро Postgres/TimescaleDB. Поэтому ставим best-effort и НЕ падаем, если нет.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'timescaledb_toolkit недоступен — пропускаем (проект его не использует)';
END $$;

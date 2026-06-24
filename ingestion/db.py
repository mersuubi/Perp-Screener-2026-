"""Доступ к БД для ингеста. Все апсерты идемпотентны (ON CONFLICT)."""
from __future__ import annotations

import asyncpg

import config


async def make_pool() -> asyncpg.Pool:
    return await asyncpg.create_pool(config.DATABASE_URL, min_size=2, max_size=8)


async def upsert_instruments(pool: asyncpg.Pool, instruments: list[dict]) -> None:
    """Регистрируем инструменты. Повторный вызов не плодит дубли."""
    await pool.executemany(
        """
        INSERT INTO instrument (symbol, exchange, base, quote, contract_type)
        VALUES ($1, 'binance', $2, $3, 'perpetual')
        ON CONFLICT (symbol) DO UPDATE SET is_active = TRUE
        """,
        [(i["symbol"], i["base"], i["quote"]) for i in instruments],
    )


async def upsert_ohlcv(pool: asyncpg.Pool, rows: list[tuple]) -> None:
    """
    rows: (symbol, bucket, open, high, low, close, volume, is_closed)
    Идемпотентность: ON CONFLICT (symbol, bucket) DO UPDATE — реконнект WS и
    повторный бэкофилл не создают дублей, а обновляют формирующуюся свечу.
    """
    if not rows:
        return
    await pool.executemany(
        """
        INSERT INTO ohlcv (symbol, bucket, open, high, low, close, volume, is_closed)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (symbol, bucket) DO UPDATE SET
            open = EXCLUDED.open, high = EXCLUDED.high, low = EXCLUDED.low,
            close = EXCLUDED.close, volume = EXCLUDED.volume,
            is_closed = EXCLUDED.is_closed
        """,
        rows,
    )


async def upsert_funding(pool: asyncpg.Pool, rows: list[tuple]) -> None:
    """rows: (symbol, ts, funding_rate)"""
    if not rows:
        return
    await pool.executemany(
        """
        INSERT INTO funding (symbol, ts, funding_rate)
        VALUES ($1, $2, $3)
        ON CONFLICT (symbol, ts) DO UPDATE SET funding_rate = EXCLUDED.funding_rate
        """,
        rows,
    )


async def upsert_open_interest(pool: asyncpg.Pool, rows: list[tuple]) -> None:
    """rows: (symbol, ts, oi)"""
    if not rows:
        return
    await pool.executemany(
        """
        INSERT INTO open_interest (symbol, ts, oi)
        VALUES ($1, $2, $3)
        ON CONFLICT (symbol, ts) DO UPDATE SET oi = EXCLUDED.oi
        """,
        rows,
    )


async def last_bucket(pool: asyncpg.Pool, symbol: str):
    """Последний загруженный бакет по символу — для докачки пропущенного при реконнекте."""
    return await pool.fetchval(
        "SELECT max(bucket) FROM ohlcv WHERE symbol = $1", symbol
    )

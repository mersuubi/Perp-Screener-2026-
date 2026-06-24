"""Пул соединений с БД для API (read-mostly)."""
from __future__ import annotations

import asyncpg

import config

_pool: asyncpg.Pool | None = None


async def connect() -> None:
    global _pool
    _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=2, max_size=10)


async def disconnect() -> None:
    if _pool is not None:
        await _pool.close()


def pool() -> asyncpg.Pool:
    assert _pool is not None, "пул не инициализирован"
    return _pool

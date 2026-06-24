"""Бэкофилл истории через REST.

Грабли §10: rate limits. Поэтому — пачки по 1500 свечей с паузами между
запросами, последовательно по символам. ccxt не используем намеренно: raw REST
прозрачнее показывает работу с пагинацией и лимитами (это вопрос на собесе).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import aiohttp

import binance
import config
import db

log = logging.getLogger("backfill")

# Пауза между REST-запросами, чтобы не словить временный бан IP.
_REQUEST_PAUSE = 0.25


async def backfill_symbol(
    session: aiohttp.ClientSession, pool, symbol: str, days: int
) -> int:
    """Качаем 1m-свечи за `days` дней пачками. Возвращает число строк."""
    interval = config.BASE_TIMEFRAME
    step = binance.tf_ms(interval) * 1500           # ширина одной пачки в мс
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = now_ms - days * 24 * 60 * 60 * 1000

    total = 0
    cursor = start_ms
    while cursor < now_ms:
        end = min(cursor + step, now_ms)
        rows = await binance.fetch_klines(session, symbol, interval, cursor, end)
        if rows:
            await db.upsert_ohlcv(pool, rows)
            total += len(rows)
            # двигаем курсор за последнюю полученную свечу
            last_open_ms = int(rows[-1][1].timestamp() * 1000)
            cursor = last_open_ms + binance.tf_ms(interval)
        else:
            cursor = end
        await asyncio.sleep(_REQUEST_PAUSE)

    # Заодно подтянем funding-историю.
    funding = await binance.fetch_funding(session, symbol, limit=200)
    await db.upsert_funding(pool, funding)
    await asyncio.sleep(_REQUEST_PAUSE)

    log.info("backfill %s: %d свечей", symbol, total)
    return total


async def backfill_all(session, pool, symbols: list[str]) -> None:
    log.info("Старт бэкофилла %d символов на %d дней", len(symbols), config.BACKFILL_DAYS)
    for sym in symbols:
        try:
            await backfill_symbol(session, pool, sym, config.BACKFILL_DAYS)
        except Exception as e:  # одна ошибка не должна валить весь бэкофилл
            log.warning("backfill %s упал: %s", sym, e)
    log.info("Бэкофилл завершён")

"""Точка входа ингест-сервиса.

Последовательность:
  1. определить вселенную символов (вайтлист или топ-N по обороту);
  2. зарегистрировать инструменты;
  3. одноразовый бэкофилл истории (REST);
  4. параллельно: WS-стрим live-свечей + опрос open interest.
"""
from __future__ import annotations

import asyncio
import logging

import aiohttp

import backfill
import binance
import config
import db
import stream

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("ingestion")


async def resolve_symbols(session) -> list[dict]:
    if config.SYMBOLS_WHITELIST:
        # Достаём метаданные только по вайтлисту.
        all_perps = await binance.fetch_top_perps(session, limit=1000)
        wl = set(config.SYMBOLS_WHITELIST)
        chosen = [p for p in all_perps if p["symbol"] in wl]
        if chosen:
            return chosen
        log.warning("Вайтлист не дал совпадений, падаю на топ-N")
    return await binance.fetch_top_perps(session, config.SYMBOL_LIMIT)


async def main() -> None:
    pool = await db.make_pool()
    async with aiohttp.ClientSession() as session:
        instruments = await resolve_symbols(session)
        symbols = [i["symbol"] for i in instruments]
        log.info("Вселенная: %d символов: %s", len(symbols), ", ".join(symbols[:10]) + " ...")
        await db.upsert_instruments(pool, instruments)
        await backfill.backfill_all(session, pool, symbols)

    # Live: стрим + опрос OI как параллельные задачи. Падение одной не глушит другую
    # (gather с return_exceptions + перезапуск контейнера как страховка).
    await asyncio.gather(
        stream.run_stream(pool, symbols),
        stream.poll_open_interest(pool, symbols),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Остановлено")

"""WebSocket-стрим Binance: live-свечи + mark price (funding).

Грабли §10:
- WS отваливается → авто-реконнект с экспоненциальной паузой.
- При переподключении докачиваем пропущенный интервал через REST (gap backfill).
- Идемпотентный ON CONFLICT гасит дубли на стыке REST/WS.
Свежие тики публикуются в Redis для live-фанаута в API (развязка ингеста и API).
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import aiohttp
import redis.asyncio as aioredis
import websockets

import binance
import config
import db

log = logging.getLogger("stream")


def _build_stream_url(symbols: list[str]) -> str:
    """Combined stream: kline_1m + markPrice по каждому символу."""
    streams = []
    for s in symbols:
        low = s.lower()
        streams.append(f"{low}@kline_1m")
        streams.append(f"{low}@markPrice@1s")
    return f"{config.BINANCE_WS}?streams={'/'.join(streams)}"


async def _gap_backfill(session, pool, symbols: list[str]) -> None:
    """Докачать свечи, пропущенные пока WS был отключён."""
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    for sym in symbols:
        last = await db.last_bucket(pool, sym)
        if last is None:
            continue
        start_ms = int(last.timestamp() * 1000) + binance.tf_ms(config.BASE_TIMEFRAME)
        if start_ms >= now_ms:
            continue
        rows = await binance.fetch_klines(
            session, sym, config.BASE_TIMEFRAME, start_ms, now_ms
        )
        await db.upsert_ohlcv(pool, rows)
        if rows:
            log.info("gap backfill %s: +%d свечей", sym, len(rows))
        await asyncio.sleep(0.1)


async def run_stream(pool, symbols: list[str]) -> None:
    redis = aioredis.from_url(config.REDIS_URL)
    url = _build_stream_url(symbols)
    backoff = 1

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                # Перед (ре)коннектом — закрываем дыру в данных.
                await _gap_backfill(session, pool, symbols)

                async with websockets.connect(url, ping_interval=20, max_queue=2048) as ws:
                    log.info("WS подключён, %d стримов", len(symbols) * 2)
                    backoff = 1  # успешный коннект — сбрасываем паузу
                    async for raw in ws:
                        await _handle_message(pool, redis, raw)
            except Exception as e:
                log.warning("WS оборвался: %s; реконнект через %ds", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)  # экспоненциальный backoff до 60с


async def _handle_message(pool, redis, raw: str) -> None:
    msg = json.loads(raw)
    data = msg.get("data", {})
    etype = data.get("e")

    if etype == "kline":
        k = data["k"]
        bucket = datetime.fromtimestamp(k["t"] / 1000, tz=timezone.utc)
        row = (
            data["s"],
            bucket,
            float(k["o"]),
            float(k["h"]),
            float(k["l"]),
            float(k["c"]),
            float(k["v"]),
            bool(k["x"]),         # x = свеча закрыта
        )
        await db.upsert_ohlcv(pool, [row])
        # публикуем в Redis для live-обновления последней свечи на фронте
        await redis.publish(
            config.REDIS_CHANNEL_KLINE,
            json.dumps(
                {
                    "symbol": data["s"],
                    "bucket": bucket.isoformat(),
                    "open": float(k["o"]),
                    "high": float(k["h"]),
                    "low": float(k["l"]),
                    "close": float(k["c"]),
                    "volume": float(k["v"]),
                    "closed": bool(k["x"]),
                }
            ),
        )

    elif etype == "markPriceUpdate":
        # markPrice несёт текущую оценочную ставку финансирования (r).
        ts = datetime.fromtimestamp(data["E"] / 1000, tz=timezone.utc)
        if "r" in data and data["r"] not in (None, ""):
            await db.upsert_funding(pool, [(data["s"], ts, float(data["r"]))])
        await redis.publish(
            config.REDIS_CHANNEL_MARK,
            json.dumps(
                {
                    "symbol": data["s"],
                    "mark_price": float(data.get("p", 0)),
                    "funding_rate": float(data.get("r") or 0),
                    "ts": ts.isoformat(),
                }
            ),
        )


async def poll_open_interest(pool, symbols: list[str]) -> None:
    """У Binance нет WS для OI — опрашиваем REST раз в OI_POLL_SECONDS."""
    async with aiohttp.ClientSession() as session:
        while True:
            rows = []
            for sym in symbols:
                try:
                    snap = await binance.fetch_open_interest(session, sym)
                    if snap:
                        rows.append(snap)
                except Exception as e:
                    log.debug("OI %s: %s", sym, e)
                await asyncio.sleep(0.05)
            await db.upsert_open_interest(pool, rows)
            await asyncio.sleep(config.OI_POLL_SECONDS)

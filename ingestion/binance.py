"""Тонкий async-клиент к публичному USDⓈ-M futures API Binance.

Только публичные эндпоинты — ключи не нужны. Уважаем rate limits:
пагинация бэкофилла идёт пачками с паузами (см. backfill.py).
"""
from __future__ import annotations

from datetime import datetime, timezone

import aiohttp

import config

# Таймфрейм → миллисекунды (для пагинации klines).
_TF_MS = {"1m": 60_000, "5m": 300_000, "1h": 3_600_000}


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


async def fetch_top_perps(session: aiohttp.ClientSession, limit: int) -> list[dict]:
    """Топ-N перпов на USDT по 24ч обороту (quoteVolume)."""
    # exchangeInfo — список контрактов; ticker/24hr — обороты.
    async with session.get(f"{config.BINANCE_REST}/fapi/v1/exchangeInfo") as r:
        info = await r.json()
    perps = {
        s["symbol"]: s
        for s in info["symbols"]
        if s.get("contractType") == "PERPETUAL"
        and s.get("status") == "TRADING"
        and s.get("quoteAsset") == "USDT"
    }
    async with session.get(f"{config.BINANCE_REST}/fapi/v1/ticker/24hr") as r:
        tickers = await r.json()

    ranked = sorted(
        (t for t in tickers if t["symbol"] in perps),
        key=lambda t: float(t["quoteVolume"]),
        reverse=True,
    )[:limit]

    out = []
    for t in ranked:
        s = perps[t["symbol"]]
        out.append(
            {"symbol": s["symbol"], "base": s["baseAsset"], "quote": s["quoteAsset"]}
        )
    return out


async def fetch_klines(
    session: aiohttp.ClientSession,
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    limit: int = 1500,
) -> list[tuple]:
    """Страница свечей. Возвращает строки под upsert_ohlcv (is_closed=True)."""
    params = {
        "symbol": symbol,
        "interval": interval,
        "startTime": start_ms,
        "endTime": end_ms,
        "limit": limit,
    }
    async with session.get(f"{config.BINANCE_REST}/fapi/v1/klines", params=params) as r:
        data = await r.json()
    rows = []
    for k in data:
        rows.append(
            (
                symbol,
                _dt(k[0]),               # open time
                float(k[1]),             # open
                float(k[2]),             # high
                float(k[3]),             # low
                float(k[4]),             # close
                float(k[5]),             # volume (base)
                True,                    # бэкофилл = закрытые свечи
            )
        )
    return rows


async def fetch_funding(
    session: aiohttp.ClientSession, symbol: str, limit: int = 100
) -> list[tuple]:
    """История funding rate (последние N начислений)."""
    params = {"symbol": symbol, "limit": limit}
    async with session.get(
        f"{config.BINANCE_REST}/fapi/v1/fundingRate", params=params
    ) as r:
        data = await r.json()
    return [(d["symbol"], _dt(d["fundingTime"]), float(d["fundingRate"])) for d in data]


async def fetch_open_interest(
    session: aiohttp.ClientSession, symbol: str
) -> tuple | None:
    """Текущий снимок открытого интереса."""
    params = {"symbol": symbol}
    async with session.get(
        f"{config.BINANCE_REST}/fapi/v1/openInterest", params=params
    ) as r:
        if r.status != 200:
            return None
        d = await r.json()
    return (d["symbol"], datetime.now(timezone.utc), float(d["openInterest"]))


def tf_ms(interval: str) -> int:
    return _TF_MS.get(interval, 60_000)

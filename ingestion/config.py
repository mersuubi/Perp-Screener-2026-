"""Конфигурация ингест-сервиса. Всё из окружения (12-factor)."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://screener:screener_pwd@timescaledb:5432/screener"
)
REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")

BINANCE_REST: str = os.getenv("BINANCE_FUTURES_REST", "https://fapi.binance.com")
BINANCE_WS: str = os.getenv("BINANCE_FUTURES_WS", "wss://fstream.binance.com/stream")

# Сколько топовых перпов по обороту отслеживать, если вайтлист не задан.
SYMBOL_LIMIT: int = _int("SCREENER_SYMBOL_LIMIT", 40)
# Явный вайтлист символов через запятую (приоритетнее лимита).
SYMBOLS_RAW: str = os.getenv("SCREENER_SYMBOLS", "").strip()
SYMBOLS_WHITELIST: list[str] = (
    [s.strip().upper() for s in SYMBOLS_RAW.split(",") if s.strip()]
    if SYMBOLS_RAW
    else []
)

# Глубина бэкофилла истории (дней 1m-свечей).
BACKFILL_DAYS: int = _int("BACKFILL_DAYS", 7)
BASE_TIMEFRAME: str = os.getenv("BASE_TIMEFRAME", "1m")

# Каналы Redis для live-фанаута.
REDIS_CHANNEL_KLINE = "ticks:kline"      # свежие/закрытые свечи
REDIS_CHANNEL_MARK = "ticks:mark"        # mark price / funding обновления

# Период опроса open interest (секунды) — у Binance нет WS для OI.
OI_POLL_SECONDS: int = _int("OI_POLL_SECONDS", 60)

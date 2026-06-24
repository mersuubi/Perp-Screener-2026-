"""Конфигурация API из окружения."""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://screener:screener_pwd@timescaledb:5432/screener"
)
REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

REDIS_CHANNEL_KLINE = "ticks:kline"
REDIS_CHANNEL_MARK = "ticks:mark"

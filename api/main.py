"""FastAPI-приложение скринера.

Отдаёт историю/метрики из БД и проксирует live из Redis в WebSocket.
OpenAPI генерится автоматически — /docs, /openapi.json.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from routers import instruments, ohlcv, screener, ws


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.disconnect()


app = FastAPI(
    title="Perp Screener API",
    version="1.0.0",
    description=(
        "Скринер крипто-перпетуалов. История и метрики считаются в TimescaleDB "
        "(оконные функции, continuous aggregates), live идёт через Redis pub/sub."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_ORIGIN, "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(instruments.router)
app.include_router(ohlcv.router)
app.include_router(screener.router)
app.include_router(ws.router)


@app.get("/health", tags=["meta"])
async def health():
    """Liveness + быстрая проверка коннекта к БД."""
    val = await db.pool().fetchval("SELECT 1")
    return {"status": "ok", "db": val == 1}

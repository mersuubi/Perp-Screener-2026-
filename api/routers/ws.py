"""WebSocket-фанаут: проксируем live-тики из Redis pub/sub клиентам.

API не лезет на биржу за live — он подписан на каналы Redis, куда пишет
ингест-сервис. Это и есть развязка ингеста и API (ADR-0003).
"""
from __future__ import annotations

import asyncio

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

import config

router = APIRouter(tags=["live"])


@router.websocket("/ws/live")
async def live(ws: WebSocket):
    """Стрим live-свечей и mark price всем подключённым клиентам."""
    await ws.accept()
    redis = aioredis.from_url(config.REDIS_URL)
    pubsub = redis.pubsub()
    await pubsub.subscribe(config.REDIS_CHANNEL_KLINE, config.REDIS_CHANNEL_MARK)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            channel = (
                message["channel"].decode()
                if isinstance(message["channel"], bytes)
                else message["channel"]
            )
            data = (
                message["data"].decode()
                if isinstance(message["data"], bytes)
                else message["data"]
            )
            kind = "kline" if channel == config.REDIS_CHANNEL_KLINE else "mark"
            await ws.send_json({"type": kind, "data": data})
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.aclose()
        await redis.aclose()

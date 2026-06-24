"""Эндпоинты истории свечей. Таймфрейм выбирает таблицу/агрегат."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

import db
from models import Candle

router = APIRouter(tags=["ohlcv"])

# Таймфрейм → источник. 1m из гипертаблицы, 5m/1h из continuous aggregates.
_SOURCE = {"1m": "ohlcv", "5m": "ohlcv_5m", "1h": "ohlcv_1h"}


@router.get("/ohlcv/{symbol}", response_model=list[Candle])
async def ohlcv(
    symbol: str,
    timeframe: str = Query("5m", pattern="^(1m|5m|1h)$"),
    limit: int = Query(500, le=2000),
):
    """История свечей по символу. Фронт берёт это на отрисовку графика."""
    source = _SOURCE.get(timeframe)
    if source is None:
        raise HTTPException(400, "неизвестный таймфрейм")
    # symbol параметризован; source выбран из белого списка _SOURCE.
    rows = await db.pool().fetch(
        f"""
        SELECT bucket, open, high, low, close, volume
        FROM {source}
        WHERE symbol = $1
        ORDER BY bucket DESC
        LIMIT $2
        """,
        symbol.upper(),
        limit,
    )
    # Возвращаем по возрастанию времени (так удобнее графику).
    return [dict(r) for r in reversed(rows)]

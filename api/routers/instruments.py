"""Эндпоинты по инструментам и витрине метрик."""
from __future__ import annotations

from fastapi import APIRouter, Query

import db
from models import Instrument, MetricRow

router = APIRouter(tags=["instruments"])


@router.get("/instruments", response_model=list[Instrument])
async def list_instruments():
    """Список активных инструментов."""
    rows = await db.pool().fetch(
        """
        SELECT symbol, base, quote, contract_type, is_active
        FROM instrument WHERE is_active ORDER BY symbol
        """
    )
    return [dict(r) for r in rows]


@router.get("/metrics", response_model=list[MetricRow])
async def metrics(
    sort: str = Query("vol_percentile", description="колонка сортировки"),
    desc: bool = Query(True),
    limit: int = Query(100, le=500),
):
    """
    Витрина скринера: одна строка на инструмент со всеми метриками.
    Читает VIEW metric_snapshot — вся аналитика посчитана в БД.
    """
    # Белый список колонок сортировки (защита от инъекции в ORDER BY).
    allowed = {
        "symbol", "price", "ret_5m", "ret_1h", "ret_24h", "vol_24h",
        "range_pct_24h", "volatility", "volume_zscore", "funding_rate",
        "funding_zscore", "oi_change_1h", "oi_change_24h", "vol_percentile",
        "volatility_rank", "funding_extremity_rank",
    }
    col = sort if sort in allowed else "vol_percentile"
    direction = "DESC" if desc else "ASC"
    rows = await db.pool().fetch(
        f"SELECT * FROM metric_snapshot ORDER BY {col} {direction} NULLS LAST LIMIT $1",
        limit,
    )
    return [dict(r) for r in rows]

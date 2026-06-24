"""Pydantic-схемы — контракты API (идут в автоген OpenAPI)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Instrument(BaseModel):
    symbol: str
    base: str
    quote: str
    contract_type: str
    is_active: bool


class Candle(BaseModel):
    bucket: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class MetricRow(BaseModel):
    """Строка витрины скринера (из VIEW metric_snapshot)."""
    symbol: str
    base: str | None = None
    quote: str | None = None
    price: float | None = None
    ret_5m: float | None = None
    ret_1h: float | None = None
    ret_24h: float | None = None
    vol_24h: float | None = None
    range_pct_24h: float | None = None
    volatility: float | None = None
    volume_zscore: float | None = None
    funding_rate: float | None = None
    funding_zscore: float | None = None
    oi: float | None = None
    oi_change_1h: float | None = None
    oi_change_24h: float | None = None
    vol_percentile: float | None = None
    volatility_rank: int | None = None
    funding_extremity_rank: int | None = None


class ScreenerFilter(BaseModel):
    """Одно условие скрининга: field op value."""
    field: Literal[
        "ret_5m", "ret_1h", "ret_24h", "vol_24h", "range_pct_24h", "volatility",
        "volume_zscore", "funding_rate", "funding_zscore", "oi_change_1h",
        "oi_change_24h", "vol_percentile", "volatility_rank", "funding_extremity_rank",
    ]
    op: Literal[">", ">=", "<", "<=", "=", "<>"]
    value: float


class ScreenerRequest(BaseModel):
    preset: str | None = None
    filters: list[ScreenerFilter] = Field(default_factory=list)


class ScreenerHit(BaseModel):
    symbol: str
    metrics: dict


class ScreenerResponse(BaseModel):
    run_id: int | None = None
    ran_at: datetime | None = None
    count: int
    hits: list[ScreenerHit]

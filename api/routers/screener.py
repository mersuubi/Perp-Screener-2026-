"""Эндпоинты скринера: запуск прогона и просмотр истории прогонов."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

import db
from models import ScreenerHit, ScreenerRequest, ScreenerResponse

router = APIRouter(tags=["screener"])


@router.post("/screener/run", response_model=ScreenerResponse)
async def run_screener(req: ScreenerRequest):
    """
    Прогнать скринер по набору фильтров.
    Вся логика — в серверной функции run_screener(jsonb): она применяет условия
    к VIEW metric_snapshot, СОХРАНЯЕТ прогон (screener_run/hit) и возвращает попадания.
    """
    filters_json = json.dumps([f.model_dump() for f in req.filters])
    async with db.pool().acquire() as con:
        try:
            rows = await con.fetch(
                "SELECT symbol, metrics FROM run_screener($1::jsonb, $2)",
                filters_json,
                req.preset,
            )
        except Exception as e:
            raise HTTPException(400, f"ошибка скрининга: {e}")
        # достаём id и время только что записанного прогона
        run = await con.fetchrow(
            "SELECT id, ran_at FROM screener_run ORDER BY id DESC LIMIT 1"
        )
    hits = [ScreenerHit(symbol=r["symbol"], metrics=json.loads(r["metrics"])) for r in rows]
    return ScreenerResponse(
        run_id=run["id"] if run else None,
        ran_at=run["ran_at"] if run else None,
        count=len(hits),
        hits=hits,
    )


@router.get("/screener/runs")
async def list_runs(limit: int = 20):
    """История прогонов скринера (воспроизводимость)."""
    rows = await db.pool().fetch(
        """
        SELECT r.id, r.ran_at, r.preset, r.filters,
               count(h.symbol) AS hit_count
        FROM screener_run r
        LEFT JOIN screener_hit h ON h.run_id = r.id
        GROUP BY r.id
        ORDER BY r.ran_at DESC
        LIMIT $1
        """,
        limit,
    )
    return [
        {
            "id": r["id"],
            "ran_at": r["ran_at"],
            "preset": r["preset"],
            "filters": json.loads(r["filters"]),
            "hit_count": r["hit_count"],
        }
        for r in rows
    ]


@router.get("/screener/runs/{run_id}")
async def get_run(run_id: int):
    """Результаты конкретного прогона."""
    rows = await db.pool().fetch(
        "SELECT symbol, metrics FROM screener_hit WHERE run_id = $1 ORDER BY symbol",
        run_id,
    )
    if not rows:
        raise HTTPException(404, "прогон не найден или пустой")
    return [{"symbol": r["symbol"], "metrics": json.loads(r["metrics"])} for r in rows]

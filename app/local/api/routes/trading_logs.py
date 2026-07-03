from __future__ import annotations

from fastapi import APIRouter
from app.local.api.deps import trade_store

router = APIRouter(prefix="/api/trading", tags=["trading"])

@router.get("/logs")
async def trading_logs(limit: int = 100) -> dict:
    return {"items": trade_store.list_logs(min(max(limit, 1), 500))}

@router.get("/open-trades")
async def open_trades() -> dict:
    return {"items": trade_store.list_open_trades()}

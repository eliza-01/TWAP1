from __future__ import annotations

from fastapi import APIRouter

from app.local.api.deps import selected_exchange

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])


@router.get("/{exchange}/status")
async def exchange_status(exchange: str) -> dict:
    adapter = selected_exchange(exchange)
    status = await adapter.status()
    return {"exchange": exchange, "status": status.status, "message": status.message}

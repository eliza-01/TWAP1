from __future__ import annotations

from fastapi import APIRouter
from app.exchanges.registry import available_exchanges
from app.local.api.deps import settings_store

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])

@router.get("")
async def list_exchanges() -> dict:
    settings = settings_store.load()
    return {"selected": settings.selected_exchange, "items": available_exchanges()}

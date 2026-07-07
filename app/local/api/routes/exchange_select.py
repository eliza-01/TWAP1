from __future__ import annotations

from fastapi import APIRouter, Body
from app.local.api.deps import settings_store

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])

@router.post("/select")
async def select_exchange(payload: dict = Body(...)) -> dict:
    name = str(payload.get("name") or "").strip()
    if not name:
        return {"success": False, "message": "Не указана биржа"}
    settings = settings_store.update({"selected_exchange": name})
    return {"success": True, "selected": settings.selected_exchange}

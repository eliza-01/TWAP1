from __future__ import annotations

from fastapi import APIRouter

from app.local.api.deps import signal_store

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/recent")
async def recent_signals(limit: int = 50) -> dict:
    return {"items": signal_store.list_recent(limit)}

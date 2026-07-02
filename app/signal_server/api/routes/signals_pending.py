from __future__ import annotations

from fastapi import APIRouter

from app.signal_server.api.deps import signal_repository

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/pending")
async def pending_signals(after_id: int = 0, limit: int = 100, include_rejected: bool = False) -> dict:
    return {"items": signal_repository.list_pending(after_id=after_id, limit=min(max(limit, 1), 500), include_rejected=include_rejected)}

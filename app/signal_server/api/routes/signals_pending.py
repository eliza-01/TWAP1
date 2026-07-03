from __future__ import annotations

from fastapi import APIRouter, Request

from app.signal_server.api.deps import signal_repository
from app.signal_server.auth import check_http_request

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/pending")
async def pending_signals(request: Request, after_id: int = 0, limit: int = 50, include_rejected: bool = False) -> dict:
    check_http_request(request, "pending")
    safe_after_id = max(int(after_id or 0), 0)
    safe_limit = min(max(int(limit or 50), 1), 100)
    return {
        "items": signal_repository.list_pending(
            after_id=safe_after_id,
            limit=safe_limit,
            include_rejected=include_rejected,
        )
    }

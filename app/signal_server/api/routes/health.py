from __future__ import annotations

from fastapi import APIRouter, Request

from app.signal_server.auth import check_http_request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict:
    check_http_request(request, "health")
    return {"status": "ok"}

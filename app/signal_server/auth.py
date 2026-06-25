from __future__ import annotations

import os

from fastapi import HTTPException, Request, WebSocket


def required_token() -> str:
    return (os.getenv("SIGNAL_SERVER_DEVICE_TOKEN") or "").strip()


def check_http_request(request: Request) -> None:
    token = required_token()
    if not token:
        return
    if _bearer(request.headers.get("authorization")) != token:
        raise HTTPException(status_code=401, detail="Invalid device token")


async def check_websocket(websocket: WebSocket) -> bool:
    token = required_token()
    if not token:
        return True
    if _bearer(websocket.headers.get("authorization")) == token:
        return True
    await websocket.close(code=1008)
    return False


def _bearer(value: str | None) -> str:
    if not value:
        return ""
    prefix = "Bearer "
    return value[len(prefix) :].strip() if value.startswith(prefix) else value.strip()

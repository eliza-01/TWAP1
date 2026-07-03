from __future__ import annotations

import os
import secrets
from typing import Literal

from fastapi import HTTPException, Request, WebSocket

from app.signal_server.security.rate_limit import (
    env_float,
    env_int,
    http_identity,
    rate_limiter,
    websocket_identity,
)

HttpScope = Literal["global", "health", "pending"]


def required_access_key() -> str:
    return (os.getenv("SIGNAL_SERVER_ACCESS_KEY") or "").strip()


def check_http_request(request: Request, scope: HttpScope = "global") -> None:
    _check_http_rate(request, scope)
    key = required_access_key()
    if not key:
        return
    if not _safe_equal(_request_key(request), key):
        raise HTTPException(status_code=401, detail="Invalid signal server access key")


async def check_websocket(websocket: WebSocket) -> bool:
    if not _check_ws_rate(websocket):
        await websocket.close(code=1013)
        return False

    key = required_access_key()
    if key and not _safe_equal(_websocket_key(websocket), key):
        await websocket.close(code=1008)
        return False
    return True


def _check_http_rate(request: Request, scope: HttpScope) -> None:
    identity = http_identity(request)
    if scope == "health":
        max_calls = env_int("SIGNAL_SERVER_HEALTH_MAX_PER_MINUTE", 30)
        min_interval = env_float("SIGNAL_SERVER_HEALTH_MIN_INTERVAL_SECONDS", 2.0)
    elif scope == "pending":
        max_calls = env_int("SIGNAL_SERVER_PENDING_MAX_PER_MINUTE", 12)
        min_interval = env_float("SIGNAL_SERVER_PENDING_MIN_INTERVAL_SECONDS", 5.0)
    else:
        max_calls = env_int("SIGNAL_SERVER_HTTP_MAX_PER_MINUTE", 300)
        min_interval = 0.0

    result = rate_limiter.check(
        key=f"http:{scope}:{identity}",
        max_calls=max_calls,
        window_seconds=60.0,
        min_interval_seconds=min_interval,
    )
    if not result.allowed:
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Retry after {max(1, int(result.retry_after_seconds))}s",
            headers={"Retry-After": str(max(1, int(result.retry_after_seconds)))},
        )


def _check_ws_rate(websocket: WebSocket) -> bool:
    result = rate_limiter.check(
        key=f"ws:connect:{websocket_identity(websocket)}",
        max_calls=env_int("SIGNAL_SERVER_WS_MAX_CONNECTS_PER_MINUTE", 30),
        window_seconds=60.0,
        min_interval_seconds=env_float("SIGNAL_SERVER_WS_MIN_CONNECT_INTERVAL_SECONDS", 1.0),
    )
    return result.allowed


def _request_key(request: Request) -> str:
    header = (request.headers.get("x-signal-access-key") or "").strip()
    if header:
        return header
    return _bearer(request.headers.get("authorization"))


def _websocket_key(websocket: WebSocket) -> str:
    header = (websocket.headers.get("x-signal-access-key") or "").strip()
    if header:
        return header
    return _bearer(websocket.headers.get("authorization"))


def _bearer(value: str | None) -> str:
    if not value:
        return ""
    prefix = "Bearer "
    return value[len(prefix) :].strip() if value.startswith(prefix) else value.strip()


def _safe_equal(left: str, right: str) -> bool:
    return secrets.compare_digest(left.encode(), right.encode())


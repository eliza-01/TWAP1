from __future__ import annotations

import os
import secrets
from typing import Any, Literal

from fastapi import HTTPException, Request, WebSocket

from app.platform.accounts.repository import AccountRepository
from app.signal_server.security.rate_limit import (
    env_float,
    env_int,
    http_identity,
    rate_limiter,
    websocket_identity,
)

HttpScope = Literal["global", "health", "pending"]


def required_access_key() -> str:
    # Legacy server-to-server key. User clients should use account sessions.
    return (os.getenv("SIGNAL_SERVER_ACCESS_KEY") or "").strip()


def check_http_request(request: Request, scope: HttpScope = "global") -> None:
    _check_http_rate(request, scope)
    # Health/global rate limit is public. Protected API routes call require_http_session().
    if scope in {"global", "health"}:
        return

    key = required_access_key()
    if key and _safe_equal(_request_key(request), key):
        return

    # Otherwise pending routes require a personal session token.
    require_http_session(request)


def require_http_session(request: Request, require_active_access: bool = True) -> dict[str, Any]:
    _check_http_rate(request, "pending")
    token = bearer_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Не указан токен сессии")
    session = AccountRepository().validate_session_token(token, require_active_access=require_active_access)
    if not session:
        raise HTTPException(status_code=401, detail="Сессия недействительна, истекла или аккаунт не активирован")
    return session


async def check_websocket(websocket: WebSocket) -> dict[str, Any] | None:
    if not _check_ws_rate(websocket):
        await websocket.close(code=1013)
        return None

    # Legacy shared key still works for internal stage/debug clients, but does not
    # create a user identity and should not be shipped to customers.
    key = required_access_key()
    if key and _safe_equal(_websocket_key(websocket), key):
        return {"legacy": True, "session_id": 0, "user_id": 0, "user": {"login": "legacy"}}

    token = websocket_token(websocket)
    if not token:
        await websocket.close(code=1008)
        return None

    session = AccountRepository().validate_session_token(token, require_active_access=True)
    if not session:
        await websocket.close(code=1008)
        return None
    return session


def bearer_token_from_request(request: Request) -> str:
    token = _bearer(request.headers.get("authorization"))
    if token:
        return token
    return (request.headers.get("x-client-session-token") or "").strip()


def websocket_token(websocket: WebSocket) -> str:
    token = _bearer(websocket.headers.get("authorization"))
    if token:
        return token
    token = (websocket.headers.get("x-client-session-token") or "").strip()
    if token:
        return token
    return str(websocket.query_params.get("token") or "").strip()


def _check_http_rate(request: Request, scope: HttpScope) -> None:
    identity = http_identity(request)
    if scope == "health":
        max_calls = env_int("SIGNAL_SERVER_HEALTH_MAX_PER_MINUTE", 30)
        min_interval = env_float("SIGNAL_SERVER_HEALTH_MIN_INTERVAL_SECONDS", 2.0)
    elif scope == "pending":
        max_calls = env_int("SIGNAL_SERVER_PENDING_MAX_PER_MINUTE", 60)
        min_interval = env_float("SIGNAL_SERVER_PENDING_MIN_INTERVAL_SECONDS", 1.0)
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


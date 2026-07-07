from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Request

from app.platform.accounts.repository import AccountError
from app.signal_server.api.deps import account_repository
from app.signal_server.auth import bearer_token_from_request, require_http_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register")
async def register(payload: dict[str, Any] = Body(...)) -> dict:
    try:
        user = account_repository.create_user_with_registration_code(
            login=str(payload.get("login") or ""),
            password=str(payload.get("password") or ""),
            code=str(payload.get("code") or ""),
        )
        return {"success": True, "user": user}
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/login")
async def login(payload: dict[str, Any] = Body(...)) -> dict:
    try:
        result = account_repository.login_with_code(
            login=str(payload.get("login") or ""),
            password=str(payload.get("password") or ""),
            code=str(payload.get("code") or ""),
            device_id=str(payload.get("device_id") or "web-cabinet"),
            device_name=str(payload.get("device_name") or "web-cabinet"),
        )
        return {"success": True, **result}
    except AccountError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout")
async def logout(request: Request) -> dict:
    session = require_http_session(request, require_active_access=False)
    token = bearer_token_from_request(request)
    account_repository.close_session_by_token(token)
    return {"success": True, "closed": True, "user": session.get("user")}


@router.get("/me")
async def me(request: Request) -> dict:
    session = require_http_session(request, require_active_access=False)
    return {"success": True, "session": _public_session(session), "user": session.get("user")}


@router.post("/activate")
async def activate(request: Request, payload: dict[str, Any] = Body(...)) -> dict:
    session = require_http_session(request, require_active_access=False)
    try:
        user = account_repository.redeem_activation_key(
            int(session.get("user_id") or 0),
            str(payload.get("key") or ""),
        )
        return {"success": True, "user": user}
    except AccountError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/activation-keys")
async def create_activation_key(request: Request, payload: dict[str, Any] = Body(...), x_admin_key: str | None = Header(default=None)) -> dict:
    admin_key = (os.getenv("SIGNAL_SERVER_ADMIN_KEY") or "").strip()
    if not admin_key or (x_admin_key or "").strip() != admin_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")

    duration_seconds = int(payload.get("duration_seconds") or 0)
    days = payload.get("days")
    if duration_seconds <= 0 and days:
        duration_seconds = int(float(days) * 24 * 60 * 60)
    if duration_seconds <= 0:
        raise HTTPException(status_code=400, detail="duration_seconds or days is required")

    expires_at = None
    if payload.get("expires_days"):
        expires_at = datetime.now(timezone.utc) + timedelta(days=float(payload["expires_days"]))

    key = account_repository.create_activation_key(
        duration_seconds=duration_seconds,
        expires_at=expires_at,
        note=str(payload.get("note") or ""),
    )
    return {"success": True, "activation_key": key}


def _public_session(session: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": session.get("session_id"),
        "user_id": session.get("user_id"),
        "device_id": session.get("device_id"),
        "device_name": session.get("device_name"),
        "started_at": _iso(session.get("started_at")),
        "last_seen_at": _iso(session.get("last_seen_at")),
    }


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)

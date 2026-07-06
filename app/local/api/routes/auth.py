from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Body

from app.local.api.deps import settings_store

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
async def auth_status() -> dict:
    settings = settings_store.load()
    token = settings.account.session_token
    account = settings.account
    if not token:
        return {"authenticated": False, "account": account.to_dict() if hasattr(account, "to_dict") else _account_public(settings)}

    http_url = settings.signals.server_http_url.rstrip("/")
    if not http_url:
        return {"authenticated": False, "message": "LOCAL_SIGNAL_HTTP_URL не задан", "account": _account_public(settings)}

    try:
        async with httpx.AsyncClient(timeout=7.0) as client:
            response = await client.get(f"{http_url}/api/auth/me", headers=_session_headers(token))
            response.raise_for_status()
            data = response.json()
        user = data.get("user") or {}
        settings_store.update(
            {
                "account": {
                    "login": user.get("login") or settings.account.login,
                    "user_id": user.get("id") or settings.account.user_id,
                    "access_until": user.get("access_until") or settings.account.access_until,
                }
            }
        )
        return {"authenticated": True, **data}
    except Exception as exc:
        return {"authenticated": False, "message": str(exc), "account": _account_public(settings)}


@router.post("/login")
async def login(payload: dict[str, Any] = Body(...)) -> dict:
    settings = settings_store.load()
    http_url = settings.signals.server_http_url.rstrip("/")
    if not http_url:
        return {"success": False, "message": "LOCAL_SIGNAL_HTTP_URL не задан"}

    request_payload = {
        "login": str(payload.get("login") or ""),
        "password": str(payload.get("password") or ""),
        "code": str(payload.get("code") or ""),
        "device_id": settings.account.device_id,
        "device_name": str(payload.get("device_name") or settings.account.device_name or "local-client"),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(f"{http_url}/api/auth/login", json=request_payload)
        data = response.json()
        if response.status_code >= 400:
            return {"success": False, "message": data.get("detail") or data.get("message") or response.text[:500]}

    user = data.get("user") or {}
    settings_store.update(
        {
            "account": {
                "login": user.get("login") or request_payload["login"],
                "session_token": data.get("token") or "",
                "user_id": user.get("id") or 0,
                "access_until": user.get("access_until") or "",
                "device_id": settings.account.device_id,
                "device_name": settings.account.device_name,
            },
            "signals": {"last_signal_id": 0},
        }
    )
    return {"success": True, "user": user, "session_id": data.get("session_id")}


@router.post("/logout")
async def logout() -> dict:
    settings = settings_store.load()
    token = settings.account.session_token
    http_url = settings.signals.server_http_url.rstrip("/")
    if token and http_url:
        try:
            async with httpx.AsyncClient(timeout=7.0) as client:
                await client.post(f"{http_url}/api/auth/logout", headers=_session_headers(token))
        except Exception:
            pass

    settings_store.update(
        {
            "account": {
                "session_token": "",
                "user_id": 0,
                "access_until": "",
            }
        }
    )
    return {"success": True}


def _session_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _account_public(settings) -> dict[str, Any]:
    return {
        "login": settings.account.login,
        "user_id": settings.account.user_id,
        "access_until": settings.account.access_until,
        "device_id": settings.account.device_id,
        "device_name": request_payload["device_name"],
        "has_session_token": bool(settings.account.session_token),
    }


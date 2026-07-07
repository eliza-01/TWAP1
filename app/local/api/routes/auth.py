from __future__ import annotations

import json
from typing import Any

import httpx
from fastapi import APIRouter, Body

from app.local.api.deps import settings_store

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
async def auth_status() -> dict:
    settings = settings_store.load()
    token = settings.account.session_token
    if not token:
        return {
            "authenticated": False,
            "message": "Локальная сессия не активна. Войдите по Telegram-коду.",
            "account": _account_public(settings),
        }

    http_url = settings.signals.server_http_url.rstrip("/")
    if not http_url:
        return {
            "authenticated": False,
            "message": "LOCAL_SIGNAL_HTTP_URL не задан",
            "account": _account_public(settings),
        }

    try:
        async with httpx.AsyncClient(timeout=7.0) as client:
            response = await client.get(f"{http_url}/api/auth/me", headers=_session_headers(token))
    except httpx.RequestError as exc:
        return {
            "authenticated": False,
            "message": f"Сервер авторизации недоступен: {exc}",
            "account": _account_public(settings),
        }

    if response.status_code >= 400:
        if response.status_code in {401, 403}:
            settings_store.update(
                {
                    "account": {
                        "session_token": "",
                        "user_id": 0,
                        "access_until": "",
                    }
                }
            )
        return {
            "authenticated": False,
            "message": _response_error_message(response, "Сессия недействительна или истекла"),
            "account": _account_public(settings_store.load()),
        }

    data, error = _safe_response_json(response)
    if error:
        return {
            "authenticated": False,
            "message": error,
            "account": _account_public(settings),
        }

    user = data.get("user") if isinstance(data.get("user"), dict) else {}
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

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{http_url}/api/auth/login", json=request_payload)
    except httpx.RequestError as exc:
        return {"success": False, "message": f"Сервер авторизации недоступен: {exc}"}

    data, error = _safe_response_json(response)
    if response.status_code >= 400:
        return {"success": False, "message": _response_error_message(response, "Не удалось войти")}
    if error:
        return {"success": False, "message": error}

    user = data.get("user") if isinstance(data.get("user"), dict) else {}
    settings_store.update(
        {
            "account": {
                "login": user.get("login") or request_payload["login"],
                "session_token": data.get("token") or "",
                "user_id": user.get("id") or 0,
                "access_until": user.get("access_until") or "",
                "device_id": settings.account.device_id,
                "device_name": request_payload["device_name"],
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


def _safe_response_json(response: httpx.Response) -> tuple[dict[str, Any], str | None]:
    raw = response.text.strip()
    if not raw:
        return {}, f"Сервер авторизации вернул пустой ответ. HTTP {response.status_code}."
    try:
        data = response.json()
    except json.JSONDecodeError:
        return {}, _technical_response_message(response)
    if not isinstance(data, dict):
        return {}, f"Сервер авторизации вернул неожиданный формат ответа. HTTP {response.status_code}."
    return data, None


def _response_error_message(response: httpx.Response, fallback: str) -> str:
    data, error = _safe_response_json(response)
    if not error:
        detail = data.get("detail")
        if isinstance(detail, dict):
            return _clean_error_text(detail.get("message") or detail.get("detail") or fallback, response.status_code, fallback)
        if detail:
            return _clean_error_text(detail, response.status_code, fallback)
        return _clean_error_text(data.get("message") or fallback, response.status_code, fallback)
    return _clean_error_text(f"{fallback}. {error}", response.status_code, fallback)


def _technical_response_message(response: httpx.Response) -> str:
    status = response.status_code
    raw = response.text.strip()
    content_type = response.headers.get("content-type", "").lower()
    if _looks_like_html(raw, content_type):
        return f"Сервер авторизации вернул техническую страницу вместо JSON. {_status_hint(status)}"
    return f"Сервер авторизации вернул не JSON. {_status_hint(status)}"


def _status_hint(status: int) -> str:
    if status in {502, 503, 504}:
        return f"Сервер временно недоступен (HTTP {status})."
    if status == 429:
        return "Слишком много запросов. Попробуйте позже (HTTP 429)."
    if status == 404:
        return "Адрес авторизации не найден (HTTP 404)."
    if status >= 500:
        return f"Ошибка сервера (HTTP {status})."
    return f"HTTP {status}."


def _looks_like_html(raw: str, content_type: str = "") -> bool:
    low = raw[:500].lower()
    return "text/html" in content_type or "<!doctype html" in low or "<html" in low


def _clean_error_text(value: Any, status: int, fallback: str) -> str:
    text = str(value or fallback).strip()
    if not text:
        text = fallback
    if _looks_like_html(text):
        prefix = text.split("<", 1)[0].strip(" :-")
        prefix = prefix or fallback
        return f"{prefix}. {_status_hint(status)}"
    return text if len(text) <= 500 else text[:497].rstrip() + "..."


def _session_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _account_public(settings) -> dict[str, Any]:
    return {
        "login": settings.account.login,
        "user_id": settings.account.user_id,
        "access_until": settings.account.access_until,
        "device_id": settings.account.device_id,
        "device_name": settings.account.device_name,
        "has_session_token": bool(settings.account.session_token),
    }

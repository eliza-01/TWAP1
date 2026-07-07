from __future__ import annotations

from fastapi import APIRouter
import httpx

from app.local.api.deps import fallback_report_store, settings_store, trade_store

router = APIRouter(prefix="/api/trading", tags=["trading"])


@router.get("/logs")
async def trading_logs(limit: int = 100) -> dict:
    return {"items": trade_store.list_logs(min(max(limit, 1), 500))}


@router.get("/open-trades")
async def open_trades() -> dict:
    return {"items": trade_store.list_open_trades()}


@router.get("/fallback-reports")
async def fallback_reports(limit: int = 100) -> dict:
    return {"items": fallback_report_store.list_recent(min(max(limit, 1), 500))}


@router.get("/skip-reports")
async def skip_reports(limit: int = 100) -> dict:
    settings = settings_store.load()
    http_url = settings.signals.server_http_url.rstrip("/")
    token = settings.account.session_token.strip()
    if not http_url or not token:
        return {"items": [], "message": "Нет HTTP-адреса сервера или токена аккаунта"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{http_url}/api/trading/skip-reports",
                params={"limit": min(max(limit, 1), 500)},
                headers={"Authorization": f"Bearer {token}"},
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        return {"items": [], "message": f"Не удалось получить отчеты пропусков с сервера: {exc}"}

    return data if isinstance(data, dict) else {"items": []}

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter

from app.local.api.deps import auto_trader, settings_store, signal_store

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.post("/sync")
async def sync_signals(limit: int = 100) -> dict[str, Any]:
    settings = settings_store.load()
    http_url = settings.signals.server_http_url.rstrip("/")
    if not http_url:
        return {
            "success": False,
            "message": "Не указан HTTP URL сервера сигналов",
            "items": [],
        }

    after_id = int(settings.signals.last_signal_id or 0)
    headers = {}
    if settings.signals.device_token:
        headers["Authorization"] = f"Bearer {settings.signals.device_token}"

    url = f"{http_url}/api/signals/pending"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                params={
                    "after_id": after_id,
                    "limit": max(1, min(int(limit), 500)),
                    "include_rejected": settings.trading.disable_signal_filters or settings.trading.ignore_min_usd_by_market_share,
                },
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:500] if exc.response is not None else ""
        return {
            "success": False,
            "message": f"Signal Server HTTP {exc.response.status_code}: {body}",
            "items": [],
        }
    except Exception as exc:
        return {
            "success": False,
            "message": f"Signal Server недоступен: {exc}",
            "items": [],
        }

    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []

    saved = 0
    last_signal_id = after_id
    for item in items:
        if not isinstance(item, dict):
            continue
        signal_store.add(item)
        await auto_trader.handle_signal(item)
        saved += 1
        last_signal_id = max(last_signal_id, int(item.get("signal_id") or item.get("id") or 0))

    if last_signal_id != after_id:
        settings_store.update({"signals": {"last_signal_id": last_signal_id}})

    return {
        "success": True,
        "message": f"Синхронизировано сигналов: {saved}",
        "count": saved,
        "last_signal_id": last_signal_id,
        "items": items,
    }


@router.get("/status")
async def signal_status() -> dict[str, Any]:
    settings = settings_store.load()
    return {
        "enabled": settings.signals.enabled,
        "mode": "websocket_only",
        "server_ws_url": settings.signals.server_ws_url,
        "server_http_url": settings.signals.server_http_url,
        "has_device_token": bool(settings.signals.device_token),
        "last_signal_id": settings.signals.last_signal_id,
        "local_recent_count": len(signal_store.list_recent(500)),
        "auto_trading_enabled": settings.trading.auto_trading_enabled,
        "auto_trading_enabled_at": settings.trading.auto_trading_enabled_at,
        "use_min_volume": settings.trading.use_min_volume,
        "default_leverage": settings.trading.default_leverage,
        "auto_order_usdt": settings.trading.auto_order_usdt,
        "disable_signal_filters": settings.trading.disable_signal_filters,
        "ignore_min_usd_by_market_share": settings.trading.ignore_min_usd_by_market_share,
        "min_usd_override_twap_share_percent": settings.trading.min_usd_override_twap_share_percent,
    }

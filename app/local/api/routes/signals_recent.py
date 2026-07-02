from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.local.api.deps import signal_client, signal_store, settings_store

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("/recent")
async def recent_signals(limit: int = 50) -> dict:
    return {"items": signal_store.list_recent(limit)}


@router.get("/status")
async def signal_status() -> dict[str, Any]:
    settings = settings_store.load()
    return {
        **signal_client.status(),
        "auto_trading_enabled": settings.trading.auto_trading_enabled,
        "auto_trading_enabled_at": settings.trading.auto_trading_enabled_at,
        "use_min_volume": settings.trading.use_min_volume,
        "default_leverage": settings.trading.default_leverage,
        "auto_order_usdt": settings.trading.auto_order_usdt,
        "disable_signal_filters": settings.trading.disable_signal_filters,
        "ignore_min_usd_by_market_share": settings.trading.ignore_min_usd_by_market_share,
        "min_usd_override_twap_share_percent": settings.trading.min_usd_override_twap_share_percent,
    }


@router.post("/check")
async def check_signal_connection() -> dict[str, Any]:
    settings = settings_store.load()
    return {
        **await signal_client.check_connection(),
        "auto_trading_enabled": settings.trading.auto_trading_enabled,
        "local_recent_count": len(signal_store.list_recent(500)),
    }

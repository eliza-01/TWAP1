from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body

from app.local.api.deps import settings_store

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.put("")
async def save_settings(patch: dict[str, Any] = Body(...)) -> dict:
    current = settings_store.load()
    trading_patch = patch.get("trading") if isinstance(patch.get("trading"), dict) else None

    if trading_patch is not None:
        enabled = trading_patch.get("auto_trading_enabled")
        if _to_bool(enabled) and not current.trading.auto_trading_enabled:
            trading_patch["auto_trading_enabled_at"] = datetime.now(timezone.utc).isoformat()
        if _to_bool(trading_patch.get("use_min_volume")):
            trading_patch["default_leverage"] = 1

    settings = settings_store.update(patch)
    return settings.to_dict(hide_secrets=True)


def _to_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)

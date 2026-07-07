from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.local.api.deps import settings_store
from app.local.settings.model import normalize_futures_symbol

router = APIRouter(prefix="/api/trading/asset-blacklist", tags=["trading"])


@router.get("")
async def get_asset_blacklist() -> dict:
    settings = settings_store.load()
    return {"items": sorted(settings.trading.blacklisted_symbols)}


@router.post("")
async def add_to_asset_blacklist(payload: dict[str, Any] = Body(...)) -> dict:
    symbol = normalize_futures_symbol(payload.get("symbol") or payload.get("asset"))
    if not symbol:
        raise HTTPException(status_code=400, detail="Не указан futures-символ")

    settings = settings_store.load()
    symbols = list(settings.trading.blacklisted_symbols)
    if symbol not in symbols:
        symbols.append(symbol)
        settings_store.update({"trading": {"blacklisted_symbols": sorted(symbols)}})

    return {
        "success": True,
        "symbol": symbol,
        "blacklisted": True,
        "items": sorted(settings_store.load().trading.blacklisted_symbols),
    }


@router.delete("")
async def remove_from_asset_blacklist(payload: dict[str, Any] = Body(...)) -> dict:
    symbol = normalize_futures_symbol(payload.get("symbol") or payload.get("asset"))
    if not symbol:
        raise HTTPException(status_code=400, detail="Не указан futures-символ")

    settings = settings_store.load()
    symbols = [item for item in settings.trading.blacklisted_symbols if item != symbol]
    settings_store.update({"trading": {"blacklisted_symbols": symbols}})

    return {
        "success": True,
        "symbol": symbol,
        "blacklisted": False,
        "items": sorted(settings_store.load().trading.blacklisted_symbols),
    }

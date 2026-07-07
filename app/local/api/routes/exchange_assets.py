from __future__ import annotations

from fastapi import APIRouter
from app.local.api.deps import selected_exchange, settings_store
from app.local.settings.model import normalize_futures_symbol

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])

@router.get("/{exchange}/futures/assets")
async def exchange_assets(exchange: str) -> dict:
    adapter = selected_exchange(exchange)
    assets = await adapter.futures_assets()
    settings = settings_store.load()
    blacklisted = set(settings.trading.blacklisted_symbols)
    return {
        "blacklisted_symbols": sorted(blacklisted),
        "items": [
            {
                "symbol": item.symbol,
                "display_name": item.display_name,
                "base_coin": item.base_coin,
                "quote_coin": item.quote_coin,
                "min_vol": item.min_vol,
                "max_vol": item.max_vol,
                "vol_unit": item.vol_unit,
                "contract_size": item.contract_size,
                "min_leverage": item.min_leverage,
                "max_leverage": item.max_leverage,
                "blacklisted": normalize_futures_symbol(item.symbol) in blacklisted,
            }
            for item in assets
        ]
    }

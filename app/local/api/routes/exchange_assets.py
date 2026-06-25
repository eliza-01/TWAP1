from __future__ import annotations

from fastapi import APIRouter

from app.local.api.deps import selected_exchange

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])


@router.get("/{exchange}/futures/assets")
async def exchange_assets(exchange: str) -> dict:
    adapter = selected_exchange(exchange)
    assets = await adapter.futures_assets()
    return {
        "items": [
            {
                "symbol": item.symbol,
                "display_name": item.display_name,
                "base_coin": item.base_coin,
                "quote_coin": item.quote_coin,
                "min_vol": item.min_vol,
                "max_vol": item.max_vol,
                "min_leverage": item.min_leverage,
                "max_leverage": item.max_leverage,
            }
            for item in assets
        ]
    }

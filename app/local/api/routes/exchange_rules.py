from __future__ import annotations

from fastapi import APIRouter
from app.local.api.deps import selected_exchange

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])

@router.get("/{exchange}/futures/rules")
async def exchange_rules(exchange: str, symbol: str) -> dict:
    adapter = selected_exchange(exchange)
    rules = await adapter.trading_rules(symbol)
    return {
        "symbol": rules.symbol,
        "min_volume": rules.min_volume,
        "max_volume": rules.max_volume,
        "volume_step": rules.volume_step,
        "contract_size": rules.contract_size,
        "min_leverage": rules.min_leverage,
        "max_leverage": rules.max_leverage,
        "price": rules.price,
        "min_notional_usdt": rules.min_notional_usdt,
    }

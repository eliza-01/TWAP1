from __future__ import annotations

from fastapi import APIRouter

from app.local.api.deps import selected_exchange

router = APIRouter(prefix="/api/exchanges", tags=["exchanges"])


@router.get("/{exchange}/balance")
async def exchange_balance(exchange: str, currency: str = "USDT") -> dict:
    adapter = selected_exchange(exchange)
    balance = await adapter.balance(currency)
    return {
        "currency": balance.currency,
        "available": balance.available,
        "equity": balance.equity,
    }

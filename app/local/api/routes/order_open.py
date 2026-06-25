from __future__ import annotations

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from app.exchanges.core.errors import ExchangeError
from app.exchanges.core.types import OpenOrderRequest
from app.local.api.deps import selected_exchange

router = APIRouter(prefix="/api/exchanges", tags=["orders"])


@router.post("/{exchange}/orders/open", response_model=None)
async def open_order(exchange: str, payload: dict = Body(...)):
    try:
        adapter = selected_exchange(exchange)
        request = OpenOrderRequest(
            symbol=str(payload.get("symbol") or "").upper(),
            direction="short" if payload.get("direction") == "short" else "long",
            volume=float(payload.get("volume") or 0),
            leverage=int(payload.get("leverage") or 1),
            open_type=int(payload.get("open_type") or 1),
        )
        result = await adapter.open_position(request)
        return {"success": result.success, "message": result.message, "order_id": result.order_id, "raw": result.raw}
    except (ExchangeError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})

from __future__ import annotations

from fastapi import APIRouter, Body
from fastapi.responses import JSONResponse

from app.exchanges.core.errors import ExchangeError
from app.exchanges.core.types import CloseOrderRequest
from app.local.api.deps import selected_exchange

router = APIRouter(prefix="/api/exchanges", tags=["orders"])


@router.post("/{exchange}/orders/close", response_model=None)
async def close_order(exchange: str, payload: dict = Body(...)):
    try:
        adapter = selected_exchange(exchange)
        volume = payload.get("volume")
        position_id = payload.get("position_id")
        request = CloseOrderRequest(
            symbol=str(payload.get("symbol") or "").upper(),
            direction="short" if payload.get("direction") == "short" else "long",
            volume=float(volume) if volume not in {None, ""} else None,
            position_id=int(position_id) if position_id not in {None, ""} else None,
            open_type=int(payload.get("open_type") or 1),
        )
        result = await adapter.close_position(request)
        return {"success": result.success, "message": result.message, "order_id": result.order_id, "raw": result.raw}
    except (ExchangeError, ValueError) as exc:
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})

from __future__ import annotations

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.local.api.deps import signal_client
from app.local.api.routes import (
    exchange_assets,
    exchange_balance,
    exchange_positions,
    exchange_rules,
    exchange_select,
    exchange_status,
    exchanges_list,
    order_close,
    order_open,
    settings_get,
    settings_save,
    signals_recent,
    trading_logs,
    ui,)

logger = logging.getLogger(__name__)

def create_local_app() -> FastAPI:
    app = FastAPI(title="TWAP Local Client")
    @app.on_event("startup")
    async def _startup() -> None:
        signal_client.start()
    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await signal_client.stop()
    @app.exception_handler(Exception)
    async def _handle_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Local API error: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=400, content={"success": False, "message": str(exc)})
    for router in [
        ui.router,
        settings_get.router,
        settings_save.router,
        exchanges_list.router,
        exchange_select.router,
        exchange_status.router,

        exchange_balance.router,

        exchange_assets.router,

        exchange_rules.router,

        exchange_positions.router,

        order_open.router,

        order_close.router,

        signals_recent.router,

        trading_logs.router,

    ]:

        app.include_router(router)

    return app

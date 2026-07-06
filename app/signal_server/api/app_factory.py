from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.signal_server.api.deps import signal_hub, telegram_account_bot
from app.signal_server.api.routes import auth, health, signals_pending, site, ws_signals
from app.signal_server.auth import check_http_request


def create_signal_server_app() -> FastAPI:
    app = FastAPI(
        title="TWAP Signal Server",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.middleware("http")
    async def _global_rate_limit(request: Request, call_next):
        try:
            check_http_request(request, "global")
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"success": False, "message": str(exc.detail)},
                headers=exc.headers,
            )
        return await call_next(request)

    @app.on_event("startup")
    async def _startup() -> None:
        signal_hub.start()
        telegram_account_bot.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await signal_hub.stop()
        await telegram_account_bot.stop()

    for router in [health.router, auth.router, signals_pending.router, ws_signals.router, site.router]:
        app.include_router(router)
    return app


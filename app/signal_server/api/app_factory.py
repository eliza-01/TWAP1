from __future__ import annotations

from fastapi import FastAPI

from app.signal_server.api.deps import signal_hub
from app.signal_server.api.routes import health, signals_pending, ws_signals


def create_signal_server_app() -> FastAPI:
    app = FastAPI(title="TWAP Signal Server")

    @app.on_event("startup")
    async def _startup() -> None:
        signal_hub.start()

    @app.on_event("shutdown")
    async def _shutdown() -> None:
        await signal_hub.stop()

    for router in [health.router, signals_pending.router, ws_signals.router]:
        app.include_router(router)
    return app

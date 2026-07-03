from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.signal_server.api.deps import signal_hub
from app.signal_server.auth import check_websocket

router = APIRouter(tags=["signals"])


@router.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket) -> None:
    if await check_websocket(websocket):
        await signal_hub.connect(websocket)


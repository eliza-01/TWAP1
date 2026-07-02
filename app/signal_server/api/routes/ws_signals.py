from __future__ import annotations

from fastapi import APIRouter, WebSocket

from app.signal_server.api.deps import signal_hub

router = APIRouter(tags=["signals"])


@router.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket) -> None:
    await signal_hub.connect(websocket)

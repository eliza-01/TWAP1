from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.signal_server.repositories.signals import SignalRepository

logger = logging.getLogger(__name__)


class SignalHub:
    def __init__(self, repository: SignalRepository, poll_interval: float = 1.0) -> None:
        self.repository = repository
        self.poll_interval = poll_interval
        self.clients: set[WebSocket] = set()
        self.last_signal_id = 0
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._broadcast_loop())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients.add(websocket)
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=2)
            data = json.loads(raw)
            if isinstance(data, dict):
                last_signal_id = int(data.get("last_signal_id") or 0)
                await self._send_pending(websocket, last_signal_id)
        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError):
            pass
        except WebSocketDisconnect:
            self.clients.discard(websocket)
            return

        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            self.clients.discard(websocket)

    async def _broadcast_loop(self) -> None:
        while not self._stop.is_set():
            try:
                signals = await asyncio.to_thread(self.repository.list_pending, self.last_signal_id, 100)
                for signal in signals:
                    self.last_signal_id = max(self.last_signal_id, int(signal.get("signal_id") or 0))
                    await self._broadcast({"type": "signal.created", "signal": signal})
            except Exception:
                logger.exception("Signal hub broadcast loop failed")
            await asyncio.sleep(self.poll_interval)

    async def _send_pending(self, websocket: WebSocket, after_id: int) -> None:
        signals = await asyncio.to_thread(self.repository.list_pending, after_id, 100)
        for signal in signals:
            await websocket.send_json({"type": "signal.created", "signal": signal})

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self.clients):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.clients.discard(websocket)

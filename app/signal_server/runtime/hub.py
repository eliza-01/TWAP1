from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from app.signal_server.repositories.signals import SignalRepository

logger = logging.getLogger(__name__)


@dataclass
class ClientState:
    message_count: int = 0
    window_started_at: float = 0.0


class SignalHub:
    def __init__(self, repository: SignalRepository, poll_interval: float | None = None) -> None:
        self.repository = repository
        self.poll_interval = _poll_interval(poll_interval)
        self.max_clients = _env_int("SIGNAL_SERVER_MAX_WS_CLIENTS", 120)
        self.ws_pending_limit = _env_int("SIGNAL_SERVER_WS_PENDING_LIMIT", 100)
        self.clients: set[WebSocket] = set()
        self.last_signal_id = 0
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop = asyncio.Event()
            self._task = asyncio.create_task(self._broadcast_loop())
            logger.info(
                "Signal hub started, db_check_interval=%ss max_ws_clients=%s",
                self.poll_interval,
                self.max_clients,
            )

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def connect(self, websocket: WebSocket) -> None:
        if len(self.clients) >= self.max_clients:
            await websocket.close(code=1013)
            logger.warning("Signal WS rejected: max clients reached (%s)", self.max_clients)
            return

        await websocket.accept()
        self.clients.add(websocket)
        state = ClientState(window_started_at=time.monotonic())
        logger.info("Signal WS client connected, clients=%s", len(self.clients))

        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=2)
            if len(raw) > 2048 or not self._client_message_allowed(state):
                await websocket.close(code=1008)
                self.clients.discard(websocket)
                return
            data = json.loads(raw)
            if isinstance(data, dict):
                last_signal_id = int(data.get("last_signal_id") or 0)
                pending_max_id = await self._send_pending(websocket, last_signal_id)
                self.last_signal_id = max(self.last_signal_id, pending_max_id, last_signal_id)
        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError):
            pass
        except WebSocketDisconnect:
            self.clients.discard(websocket)
            logger.info("Signal WS client disconnected during hello, clients=%s", len(self.clients))
            return

        try:
            while True:
                raw = await websocket.receive_text()
                if len(raw) > 2048 or not self._client_message_allowed(state):
                    await websocket.close(code=1008)
                    return
                await self._handle_client_message(websocket, raw)
        except WebSocketDisconnect:
            self.clients.discard(websocket)
            logger.info("Signal WS client disconnected, clients=%s", len(self.clients))
        finally:
            self.clients.discard(websocket)

    async def _broadcast_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.clients:
                    await self._sleep()
                    continue

                signals = await asyncio.to_thread(self.repository.list_pending, self.last_signal_id, 100, True)
                for signal in signals:
                    self.last_signal_id = max(self.last_signal_id, int(signal.get("signal_id") or 0))
                    await self._broadcast({"type": "signal.created", "signal": signal})
            except Exception:
                logger.exception("Signal hub broadcast loop failed")
            await self._sleep()

    async def _send_pending(self, websocket: WebSocket, after_id: int) -> int:
        max_id = after_id
        safe_after_id = max(int(after_id or 0), 0)
        signals = await asyncio.to_thread(self.repository.list_pending, safe_after_id, self.ws_pending_limit, True)
        for signal in signals:
            max_id = max(max_id, int(signal.get("signal_id") or 0))
            await websocket.send_json({"type": "signal.created", "signal": signal})
        if signals:
            logger.info("Signal WS sent pending=%s after_id=%s", len(signals), safe_after_id)
        return max_id

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        signal = payload.get("signal") if isinstance(payload.get("signal"), dict) else {}
        logger.info(
            "Signal WS broadcast: id=%s kind=%s status=%s clients=%s",
            signal.get("signal_id"),
            signal.get("kind"),
            signal.get("status"),
            len(self.clients),
        )
        for websocket in list(self.clients):
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self.clients.discard(websocket)

    async def _handle_client_message(self, websocket: WebSocket, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        if data.get("type") == "ping":
            await websocket.send_json({"type": "pong"})

    def _client_message_allowed(self, state: ClientState) -> bool:
        now = time.monotonic()
        if now - state.window_started_at > 60:
            state.window_started_at = now
            state.message_count = 0
        state.message_count += 1
        return state.message_count <= _env_int("SIGNAL_SERVER_WS_MAX_MESSAGES_PER_MINUTE", 30)

    async def _sleep(self) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval)
        except asyncio.TimeoutError:
            pass


def _poll_interval(value: float | None) -> float:
    if value is not None:
        return max(0.2, min(float(value), 5.0))
    raw = (os.getenv("SIGNAL_SERVER_DB_CHECK_SECONDS") or "0.5").strip()
    try:
        parsed = float(raw)
    except ValueError:
        parsed = 0.5
    return max(0.2, min(parsed, 5.0))


def _env_int(name: str, default: int) -> int:
    try:
        return int((os.getenv(name) or "").strip() or default)
    except ValueError:
        return default

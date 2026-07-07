from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

if TYPE_CHECKING:
    from app.platform.accounts.repository import AccountRepository
    from app.signal_server.repositories.signals import SignalRepository

logger = logging.getLogger(__name__)


@dataclass
class ClientState:
    message_count: int = 0
    window_started_at: float = 0.0


class SignalHub:
    def __init__(
        self,
        repository: 'SignalRepository',
        account_repository: 'AccountRepository | None' = None,
        poll_interval: float | None = None,
    ) -> None:
        self.repository = repository
        self.account_repository = account_repository
        self.poll_interval = _poll_interval(poll_interval)
        self.max_clients = _env_int("SIGNAL_SERVER_MAX_WS_CLIENTS", 120)
        self.ws_pending_limit = _env_int("SIGNAL_SERVER_WS_PENDING_LIMIT", 100)
        self.clients: set[WebSocket] = set()
        self.client_sessions: dict[WebSocket, dict[str, Any]] = {}
        self.connected_session_ids: set[int] = set()
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

    async def connect(self, websocket: WebSocket, session: dict[str, Any] | None = None) -> None:
        session = session or {"legacy": True, "session_id": 0, "user_id": 0, "user": {"login": "legacy"}}
        session_id = int(session.get("session_id") or 0)

        if len(self.clients) >= self.max_clients:
            await websocket.close(code=1013)
            logger.warning("Signal WS rejected: max clients reached (%s)", self.max_clients)
            return

        if session_id and session_id in self.connected_session_ids:
            await websocket.close(code=1008)
            logger.warning(
                "Signal WS rejected: session already connected session_id=%s user=%s",
                session_id,
                session.get("user", {}).get("login"),
            )
            return

        await websocket.accept()
        self.clients.add(websocket)
        self.client_sessions[websocket] = session
        if session_id:
            self.connected_session_ids.add(session_id)
        state = ClientState(window_started_at=time.monotonic())
        logger.info(
            "Signal WS client connected, clients=%s session_id=%s user=%s",
            len(self.clients),
            session_id or "legacy",
            session.get("user", {}).get("login"),
        )

        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=2)
            if len(raw) > 2048 or not self._client_message_allowed(state):
                await websocket.close(code=1008)
                self._drop_client(websocket)
                return
            data = json.loads(raw)
            if isinstance(data, dict):
                self._touch_session(session)
                client_last_signal_id = max(int(data.get("last_signal_id") or 0), 0)
                db_max_signal_id = await asyncio.to_thread(self.repository.max_signal_id)
                self._clamp_last_signal_id(db_max_signal_id)

                if _bool_value(data.get("fresh_start")):
                    fresh_start_after = data.get("fresh_start_after")
                    if fresh_start_after and hasattr(self.repository, "max_signal_id_before"):
                        fresh_start_after_id = await asyncio.to_thread(
                            self.repository.max_signal_id_before,
                            fresh_start_after,
                        )
                    else:
                        fresh_start_after_id = db_max_signal_id

                    if client_last_signal_id > db_max_signal_id:
                        logger.warning(
                            "Signal WS client last_signal_id=%s is ahead of DB max=%s during fresh start; ignoring stored client id",
                            client_last_signal_id,
                            db_max_signal_id,
                        )

                    client_last_signal_id = max(min(int(fresh_start_after_id or 0), db_max_signal_id), 0)

                    pending_max_id = await self._send_pending(websocket, client_last_signal_id)
                    self.last_signal_id = max(self.last_signal_id, pending_max_id, client_last_signal_id)
                    await websocket.send_json(
                        {
                            "type": "hello.ack",
                            "fresh_start": True,
                            "last_signal_id": self.last_signal_id,
                            "pending_skipped": True,
                        }
                    )
                    logger.info(
                        "Signal WS fresh start: skipped old pending up to id=%s after=%s user=%s",
                        client_last_signal_id,
                        fresh_start_after or "n/a",
                        session.get("user", {}).get("login"),
                    )
                else:
                    if client_last_signal_id > db_max_signal_id:
                        logger.warning(
                            "Signal WS client last_signal_id=%s is ahead of DB max=%s; treating it as fresh storage",
                            client_last_signal_id,
                            db_max_signal_id,
                        )
                        client_last_signal_id = 0
                    pending_max_id = await self._send_pending(websocket, client_last_signal_id)
                    self.last_signal_id = max(self.last_signal_id, pending_max_id, client_last_signal_id)
                    await websocket.send_json(
                        {
                            "type": "hello.ack",
                            "fresh_start": False,
                            "last_signal_id": self.last_signal_id,
                            "pending_skipped": False,
                        }
                    )
        except (asyncio.TimeoutError, json.JSONDecodeError, ValueError):
            pass
        except WebSocketDisconnect:
            self._drop_client(websocket)
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
            logger.info("Signal WS client disconnected, clients=%s", len(self.clients) - 1)
        finally:
            self._drop_client(websocket)

    async def _broadcast_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.clients:
                    await self._sleep()
                    continue

                db_max_signal_id = await asyncio.to_thread(self.repository.max_signal_id)
                self._clamp_last_signal_id(db_max_signal_id)

                signals = await asyncio.to_thread(self.repository.list_pending, self.last_signal_id, 100, True)
                for signal in signals:
                    self.last_signal_id = max(self.last_signal_id, int(signal.get("signal_id") or 0))
                    await self._broadcast({"type": "signal.created", "signal": signal})
            except Exception:
                logger.exception("Signal hub broadcast loop failed")
            await self._sleep()

    def _clamp_last_signal_id(self, db_max_signal_id: int) -> None:
        db_max = max(int(db_max_signal_id or 0), 0)
        if self.last_signal_id <= db_max:
            return
        logger.warning(
            "Signal hub last_signal_id=%s is ahead of DB max=%s; clamping to DB max",
            self.last_signal_id,
            db_max,
        )
        self.last_signal_id = db_max

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
                self._touch_session(self.client_sessions.get(websocket) or {})
            except Exception:
                stale.append(websocket)
        for websocket in stale:
            self._drop_client(websocket)

    async def _handle_client_message(self, websocket: WebSocket, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        session = self.client_sessions.get(websocket) or {}
        self._touch_session(session)
        if data.get("type") in {"ping", "client.ping"}:
            await websocket.send_json({"type": "pong"})

    def _touch_session(self, session: dict[str, Any]) -> None:
        session_id = int(session.get("session_id") or 0)
        if not session_id or self.account_repository is None:
            return
        try:
            self.account_repository.touch_session(session_id)
        except Exception:
            logger.exception("Failed to touch user session %s", session_id)

    def _drop_client(self, websocket: WebSocket) -> None:
        session = self.client_sessions.pop(websocket, {}) if websocket in self.client_sessions else {}
        session_id = int(session.get("session_id") or 0)
        if session_id:
            self.connected_session_ids.discard(session_id)
        self.clients.discard(websocket)

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


def _bool_value(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)

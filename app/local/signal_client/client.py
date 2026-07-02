from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets

from app.local.settings.store import LocalSettingsStore
from app.local.signal_client.store import LocalSignalStore
from app.local.trading.auto_trader import LocalAutoTrader

logger = logging.getLogger(__name__)


class LocalSignalClient:
    def __init__(
        self,
        settings_store: LocalSettingsStore,
        signal_store: LocalSignalStore,
        auto_trader: LocalAutoTrader | None = None,
    ) -> None:
        self.settings_store = settings_store
        self.signal_store = signal_store
        self.auto_trader = auto_trader
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()
        self._state = "starting"
        self._message = "Клиент сигналов запускается"
        self._connected_at = ""
        self._last_error_at = ""
        self._last_signal_at = ""
        self._last_ws_url = ""

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop = asyncio.Event()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    def status(self) -> dict[str, Any]:
        settings = self.settings_store.load()
        return {
            "listening": True,
            "state": self._state,
            "message": self._message,
            "server_ws_url": settings.signals.server_ws_url,
            "server_http_url": settings.signals.server_http_url,
            "connected_at": self._connected_at,
            "last_error_at": self._last_error_at,
            "last_signal_at": self._last_signal_at,
            "last_signal_id": settings.signals.last_signal_id,
            "local_recent_count": len(self.signal_store.list_recent(500)),
        }

    async def check_connection(self) -> dict[str, Any]:
        settings = self.settings_store.load()
        http_url = settings.signals.server_http_url.rstrip("/")
        if not http_url:
            return {**self.status(), "health_ok": False, "health_message": "HTTP URL сервера сигналов не задан"}

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{http_url}/health")
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            return {**self.status(), "health_ok": False, "health_message": f"HTTP {exc.response.status_code}: {body}"}
        except Exception as exc:
            return {**self.status(), "health_ok": False, "health_message": f"Сервер сигналов недоступен: {exc}"}

        return {**self.status(), "health_ok": True, "health_message": "HTTP /health OK", "health_response": data}

    async def _run(self) -> None:
        logger.info("Signal client runner started; signals are always listened")
        while not self._stop.is_set():
            settings = self.settings_store.load()
            url = settings.signals.server_ws_url.strip()
            self._last_ws_url = url

            if not url:
                self._set_state("error", "WebSocket URL сервера сигналов не задан")
                await self._sleep(2)
                continue

            try:
                self._set_state("connecting", f"Подключение к Signal Server: {url}")
                logger.info("Signal WS connecting: %s", url)
                async with websockets.connect(url, ping_interval=15, ping_timeout=10, close_timeout=5) as ws:
                    self._connected_at = _now()
                    self._set_state("connected", "WebSocket подключен, сигналы слушаются")
                    logger.info("Signal WS connected")
                    await ws.send(
                        json.dumps(
                            {
                                "type": "hello",
                                "last_signal_id": settings.signals.last_signal_id,
                            },
                            ensure_ascii=False,
                        )
                    )
                    async for raw in ws:
                        await self._handle_message(raw)
            except Exception as exc:
                self._last_error_at = _now()
                self._set_state("reconnecting", f"WebSocket отключен, переподключение: {exc}")
                logger.warning("Signal WS reconnect later: %s", exc)
                await self._sleep(1)

    async def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Signal WS ignored non-json message")
            return
        if not isinstance(data, dict) or data.get("type") != "signal.created":
            logger.debug("Signal WS ignored message: %s", data.get("type") if isinstance(data, dict) else type(data).__name__)
            return

        signal = data.get("signal") if isinstance(data.get("signal"), dict) else data
        self.signal_store.add(signal)
        self._last_signal_at = _now()
        signal_id = int(signal.get("signal_id") or signal.get("id") or 0)
        if signal_id:
            self.settings_store.update({"signals": {"last_signal_id": signal_id}})
            logger.info(
                "Signal WS received: id=%s kind=%s status=%s symbol=%s",
                signal_id,
                signal.get("kind"),
                signal.get("status"),
                signal.get("symbol") or signal.get("asset"),
            )

        if self.auto_trader is not None:
            await self.auto_trader.handle_signal(signal)

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    def _set_state(self, state: str, message: str) -> None:
        self._state = state
        self._message = message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

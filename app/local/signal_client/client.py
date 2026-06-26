# app/local/signal_client/client.py
from __future__ import annotations

import asyncio
import inspect
import json
import logging
from typing import Any

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

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop = asyncio.Event()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        logger.info("Signal client runner started in WebSocket-only mode")
        while not self._stop.is_set():
            settings = self.settings_store.load()
            if not settings.signals.enabled:
                await self._sleep(0.5)
                continue

            if not settings.signals.server_ws_url:
                logger.warning("Signal client enabled, but WebSocket URL is empty")
                await self._sleep(2)
                continue

            url = settings.signals.server_ws_url
            headers = _auth_headers(settings.signals.device_token)

            try:
                logger.info("Signal WS connecting: %s", url)
                async with _connect_ws(url, headers) as ws:
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


def _auth_headers(token: str) -> dict[str, str]:
    clean = (token or "").strip()
    return {"Authorization": f"Bearer {clean}"} if clean else {}


def _connect_ws(url: str, headers: dict[str, str]):
    kwargs: dict[str, Any] = {
        "ping_interval": 15,
        "ping_timeout": 10,
        "close_timeout": 5,
    }
    params = inspect.signature(websockets.connect).parameters
    if headers:
        if "additional_headers" in params:
            kwargs["additional_headers"] = headers
        elif "extra_headers" in params:
            kwargs["extra_headers"] = headers
    return websockets.connect(url, **kwargs)

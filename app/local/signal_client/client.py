from __future__ import annotations

import asyncio
import json
import logging

import websockets

from app.local.settings.store import LocalSettingsStore
from app.local.signal_client.store import LocalSignalStore

logger = logging.getLogger(__name__)


class LocalSignalClient:
    def __init__(self, settings_store: LocalSettingsStore, signal_store: LocalSignalStore) -> None:
        self.settings_store = settings_store
        self.signal_store = signal_store
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task

    async def _run(self) -> None:
        while not self._stop.is_set():
            settings = self.settings_store.load()
            if not settings.signals.enabled:
                await asyncio.sleep(3)
                continue

            if not settings.signals.server_ws_url:
                logger.warning("Signal client enabled, but WebSocket URL is empty")
                await asyncio.sleep(5)
                continue

            url = settings.signals.server_ws_url
            headers = {}
            if settings.signals.device_token:
                headers["Authorization"] = f"Bearer {settings.signals.device_token}"

            try:
                logger.info("Signal client connecting: %s", url)
                async with websockets.connect(url, additional_headers=headers) as ws:
                    logger.info("Signal client connected")
                    await ws.send(json.dumps({"type": "hello", "last_signal_id": settings.signals.last_signal_id}))
                    async for raw in ws:
                        await self._handle_message(raw)
            except Exception as exc:
                logger.warning("Signal client reconnect later: %s", exc)
                await asyncio.sleep(5)

    async def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict) or data.get("type") != "signal.created":
            return
        signal = data.get("signal") if isinstance(data.get("signal"), dict) else data
        self.signal_store.add(signal)
        signal_id = int(signal.get("signal_id") or signal.get("id") or 0)
        if signal_id:
            self.settings_store.update({"signals": {"last_signal_id": signal_id}})
            logger.info("Signal saved: id=%s symbol=%s", signal_id, signal.get("symbol") or signal.get("asset"))

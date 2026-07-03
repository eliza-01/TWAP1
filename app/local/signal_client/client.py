from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets

from app.local.settings.store import LocalSettingsStore
from app.local.signal_client.store import LocalSignalStore
from app.local.trading.auto_trader import LocalAutoTrader

logger = logging.getLogger(__name__)

_CHECK_COOLDOWN_SECONDS = 2.0


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

        self._last_check_monotonic = 0.0

        self._last_check_result: dict[str, Any] | None = None

        self._check_lock = asyncio.Lock()


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

            "has_access_key": bool(_access_key()),

            "connected_at": self._connected_at,

            "last_error_at": self._last_error_at,

            "last_signal_at": self._last_signal_at,

            "last_signal_id": settings.signals.last_signal_id,

            "local_recent_count": len(self.signal_store.list_recent(500)),

        }


    async def check_connection(self) -> dict[str, Any]:

        async with self._check_lock:

            now = time.monotonic()

            if self._last_check_result and now - self._last_check_monotonic < _CHECK_COOLDOWN_SECONDS:

                return {

                    **self._last_check_result,

                    "cooldown": True,

                    "cooldown_seconds_left": round(_CHECK_COOLDOWN_SECONDS - (now - self._last_check_monotonic), 2),

                }


            result = await self._check_connection_now()

            self._last_check_monotonic = now

            self._last_check_result = result

            return result


    async def _check_connection_now(self) -> dict[str, Any]:

        settings = self.settings_store.load()

        http_url = settings.signals.server_http_url.rstrip("/")

        if not http_url:

            return {**self.status(), "health_ok": False, "health_message": "LOCAL_SIGNAL_HTTP_URL не задан в .env"}


        try:

            async with httpx.AsyncClient(timeout=5.0) as client:

                response = await client.get(f"{http_url}/health", headers=_access_headers())

                response.raise_for_status()

                data = response.json()

        except httpx.HTTPStatusError as exc:

            body = exc.response.text[:500] if exc.response is not None else ""

            return {**self.status(), "health_ok": False, "health_message": f"HTTP {exc.response.status_code}: {body}"}

        except Exception as exc:

            return {**self.status(), "health_ok": False, "health_message": f"Сервер сигналов недоступен: {exc}"}


        return {**self.status(), "health_ok": True, "health_message": "HTTP /health OK", "health_response": data}


    async def _run(self) -> None:

        logger.info("Signal client runner started in WebSocket mode")

        reconnect_delay = 1.0

        while not self._stop.is_set():

            settings = self.settings_store.load()

            url = settings.signals.server_ws_url


            if not url:

                self._set_state("not_configured", "LOCAL_SIGNAL_WS_URL не задан в .env")

                await self._sleep(2)

                continue


            self._last_ws_url = url

            self._set_state("connecting", f"Подключение к {url}")


            try:

                logger.info("Signal WS connecting: %s", url)

                async with _connect_ws(url, _access_headers()) as ws:

                    reconnect_delay = 1.0

                    self._set_state("connected", "WebSocket подключен")

                    self._connected_at = _now_iso()

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

                self._last_error_at = _now_iso()

                self._connected_at = ""

                self._set_state("reconnecting", f"WebSocket недоступен: {exc}")

                logger.warning("Signal WS reconnect later: %s", exc)

                await self._sleep(reconnect_delay + random.uniform(0, 0.5))

                reconnect_delay = min(30.0, reconnect_delay * 1.7)


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

        self._last_signal_at = _now_iso()

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


def _access_key() -> str:

    return (os.getenv("LOCAL_SIGNAL_ACCESS_KEY") or "").strip()


def _access_headers() -> dict[str, str]:

    key = _access_key()

    return {"Authorization": f"Bearer {key}", "X-Signal-Access-Key": key} if key else {}


def _connect_ws(url: str, headers: dict[str, str]):

    kwargs: dict[str, Any] = {

        "ping_interval": 15,

        "ping_timeout": 10,

        "close_timeout": 5,

        "max_size": 1_000_000,

    }

    params = inspect.signature(websockets.connect).parameters

    if headers:

        if "additional_headers" in params:

            kwargs["additional_headers"] = headers

        elif "extra_headers" in params:

            kwargs["extra_headers"] = headers

    return websockets.connect(url, **kwargs)


def _now_iso() -> str:

    return datetime.now(timezone.utc).isoformat(timespec="seconds")

from __future__ import annotations

import asyncio
import inspect
import json
import logging
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
_FALLBACK_CHECK_SECONDS = 1.0


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
        self._fallback_task: asyncio.Task | None = None
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
        self._started_at = datetime.now(timezone.utc)
        self._fresh_start_pending = True
        self._startup_old_signals_skipped = 0

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop = asyncio.Event()
            self._started_at = datetime.now(timezone.utc)
            self._fresh_start_pending = True
            self._startup_old_signals_skipped = 0
            self._reset_local_signal_state_on_startup()
            self._task = asyncio.create_task(self._run())
        if self.auto_trader is not None and (self._fallback_task is None or self._fallback_task.done()):
            self._fallback_task = asyncio.create_task(self._run_fallback_watch())

    async def stop(self) -> None:
        self._stop.set()
        tasks = [task for task in (self._task, self._fallback_task) if task is not None]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def status(self) -> dict[str, Any]:
        settings = self.settings_store.load()
        return {
            "listening": True,
            "state": self._state,
            "message": self._message,
            "server_ws_url": settings.signals.server_ws_url,
            "server_http_url": settings.signals.server_http_url,
            "authenticated": bool(settings.account.session_token),
            "account_login": settings.account.login,
            "access_until": settings.account.access_until,
            "connected_at": self._connected_at,
            "last_error_at": self._last_error_at,
            "last_signal_at": self._last_signal_at,
            "last_signal_id": settings.signals.last_signal_id,
            "local_recent_count": len(self.signal_store.list_recent(500)),
            "fallback_close_enabled": settings.trading.fallback_close_enabled,
            "fallback_close_grace_seconds": settings.trading.fallback_close_grace_seconds,
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
                health_response = await client.get(f"{http_url}/health")
                health_response.raise_for_status()
                health_data = health_response.json()

                auth_data = None
                if settings.account.session_token:
                    auth_response = await client.get(
                        f"{http_url}/api/auth/me",
                        headers=_session_headers(settings.account.session_token),
                    )
                    auth_response.raise_for_status()
                    auth_data = auth_response.json()
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:500] if exc.response is not None else ""
            return {**self.status(), "health_ok": False, "health_message": f"HTTP {exc.response.status_code}: {body}"}
        except Exception as exc:
            return {**self.status(), "health_ok": False, "health_message": f"Сервер сигналов недоступен: {exc}"}

        return {
            **self.status(),
            "health_ok": True,
            "health_message": "HTTP /health OK",
            "health_response": health_data,
            "auth_response": auth_data,
        }

    def _reset_local_signal_state_on_startup(self) -> None:
        recent_cleared = self.signal_store.clear()
        self.settings_store.update({"signals": {"last_signal_id": 0}})

        if self.auto_trader is not None:
            self.auto_trader.reset_signal_runtime_state_on_startup(
                self._started_at,
                local_recent_signals_cleared=recent_cleared,
            )
            self.auto_trader.ignore_existing_open_trades_on_startup(self._started_at)
        else:
            logger.warning(
                "Startup fresh state: cleared local signal memory recent=%s and reset last_signal_id=0",
                recent_cleared,
            )

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
            if not settings.account.session_token:
                self._set_state("unauthorized", "Войдите в аккаунт: нужен логин, пароль и код из Telegram-бота")
                await self._sleep(2)
                continue

            self._last_ws_url = url
            self._set_state("connecting", f"Подключение к {url}")
            try:
                logger.info("Signal WS connecting: %s", url)
                async with _connect_ws(url, _session_headers(settings.account.session_token)) as ws:
                    reconnect_delay = 1.0
                    self._set_state("connected", "WebSocket подключен")
                    self._connected_at = _now_iso()
                    logger.info("Signal WS connected as %s", settings.account.login or "unknown")
                    hello = {
                        "type": "hello",
                        "last_signal_id": settings.signals.last_signal_id,
                    }
                    if self._fresh_start_pending:
                        hello["fresh_start"] = True
                        hello["fresh_start_after"] = self._started_at.isoformat()
                    await ws.send(json.dumps(hello, ensure_ascii=False))
                    ping_task = asyncio.create_task(_ws_ping_loop(ws))
                    try:
                        async for raw in ws:
                            await self._handle_message(raw)
                    finally:
                        ping_task.cancel()
                        await asyncio.gather(ping_task, return_exceptions=True)
            except Exception as exc:
                self._last_error_at = _now_iso()
                self._connected_at = ""
                self._set_state("reconnecting", f"WebSocket недоступен: {exc}")
                logger.warning("Signal WS reconnect later: %s", exc)
                await self._sleep(reconnect_delay + random.uniform(0, 0.5))
                reconnect_delay = min(30.0, reconnect_delay * 1.7)

    async def _run_fallback_watch(self) -> None:
        logger.info("Fallback close watcher started")
        while not self._stop.is_set():
            try:
                if self.auto_trader is not None:
                    await self.auto_trader.check_fallback_closures()
            except Exception as exc:
                logger.exception("Fallback close watcher failed: %s", exc)
            await self._sleep(_FALLBACK_CHECK_SECONDS)

    async def _handle_message(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Signal WS ignored non-json message")
            return

        if not isinstance(data, dict):
            logger.debug("Signal WS ignored non-dict message")
            return

        if data.get("type") == "hello.ack":
            self._handle_hello_ack(data)
            return

        if data.get("type") != "signal.created":
            logger.debug("Signal WS ignored message: %s", data.get("type"))
            return

        signal = data.get("signal") if isinstance(data.get("signal"), dict) else data
        signal_id = self._remember_signal_id(signal)

        if _is_before_dt(signal, self._started_at):
            self._startup_old_signals_skipped += 1
            self._last_signal_at = _now_iso()
            if self.auto_trader is not None:
                self.auto_trader.log_signal_skipped_before_startup(signal)
            if self._startup_old_signals_skipped == 1:
                logger.info("Signal WS skips signals created before local startup")
            return

        self.signal_store.add(signal)
        self._last_signal_at = _now_iso()
        if signal_id:
            logger.info(
                "Signal WS received: id=%s kind=%s status=%s symbol=%s",
                signal_id,
                signal.get("kind"),
                signal.get("status"),
                signal.get("symbol") or signal.get("asset"),
            )

        if self.auto_trader is not None:
            await self.auto_trader.handle_signal(signal)

    def _handle_hello_ack(self, data: dict[str, Any]) -> None:
        self._fresh_start_pending = False
        last_signal_id = _int_value(data.get("last_signal_id"))
        if last_signal_id > 0:
            self.settings_store.update({"signals": {"last_signal_id": last_signal_id}})
        logger.info(
            "Signal WS hello acknowledged: fresh_start=%s last_signal_id=%s",
            bool(data.get("fresh_start")),
            last_signal_id,
        )

    def _remember_signal_id(self, signal: dict[str, Any]) -> int:
        signal_id = _int_value(signal.get("signal_id") or signal.get("id"))
        if signal_id:
            self.settings_store.update({"signals": {"last_signal_id": signal_id}})
        return signal_id

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    def _set_state(self, state: str, message: str) -> None:
        self._state = state
        self._message = message


def _session_headers(token: str) -> dict[str, str]:
    token = (token or "").strip()
    return {"Authorization": f"Bearer {token}", "X-Client-Session-Token": token} if token else {}


async def _ws_ping_loop(ws) -> None:
    while True:
        await asyncio.sleep(30)
        await ws.send(json.dumps({"type": "client.ping"}, ensure_ascii=False))


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



def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_before_dt(signal: dict[str, Any], boundary: datetime) -> bool:
    signal_time = signal.get("created_at") or signal.get("message_date")
    signal_dt = _parse_dt(signal_time)
    if signal_dt is None:
        return False
    return signal_dt < boundary.astimezone(timezone.utc)


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx
import uvicorn
from dotenv import load_dotenv

APP_TITLE = "TWAPs"
HOST = "127.0.0.1"
DEFAULT_PROD_HTTP_URL = "https://twaps.ru"
DEFAULT_PROD_WS_URL = "wss://twaps.ru/ws/signals"

logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_data_dir() -> Path:
    configured = os.getenv("TWAPS_DATA_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    if is_frozen():
        base = os.getenv("APPDATA") or str(Path.home())
        return Path(base) / "TWAPs"

    return Path.cwd() / "local_data"


def prepare_desktop_environment() -> Path:
    """Prepare env vars before app.local.* modules create global stores."""
    exe_dir = executable_dir()

    # Allow a support/admin build to override signal URLs and paths without
    # rebuilding the executable: place .env next to TWAPs.exe or launch from
    # a project folder with .env.
    for candidate in (exe_dir / ".env", Path.cwd() / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)

    data_dir = default_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    _configure_desktop_logging(data_dir)

    os.environ.setdefault("LOCAL_SETTINGS_PATH", str(data_dir / "settings.json"))
    os.environ.setdefault("LOCAL_SIGNALS_PATH", str(data_dir / "signals.json"))
    os.environ.setdefault("LOCAL_TRADES_PATH", str(data_dir / "trades.json"))

    # Desktop builds should be usable without a project .env. Values can still
    # be overridden by .env or environment variables for stage/beta testing.
    os.environ.setdefault("LOCAL_SIGNAL_HTTP_URL", os.getenv("PUBLIC_BASE_URL") or DEFAULT_PROD_HTTP_URL)
    os.environ.setdefault("LOCAL_SIGNAL_WS_URL", os.getenv("PUBLIC_SIGNAL_WS_URL") or DEFAULT_PROD_WS_URL)

    return data_dir


def _configure_desktop_logging(data_dir: Path) -> None:
    """Write desktop errors to a file because the WV2 build has no console."""
    root = logging.getLogger()
    if any(getattr(handler, "_twaps_desktop_handler", False) for handler in root.handlers):
        return

    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(log_dir / "desktop.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler._twaps_desktop_handler = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((HOST, 0))
        return int(sock.getsockname()[1])


class LocalUiServer:
    def __init__(self, host: str = HOST, port: int | None = None) -> None:
        self.host = host
        self.port = port or find_free_port()
        self.url = f"http://{self.host}:{self.port}"
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._startup_error: BaseException | None = None

    def start(self) -> str:
        prepare_desktop_environment()

        # Import only after prepare_desktop_environment(): app.local.api.deps
        # creates settings/signal/trade stores at import time.
        from app.local.api.app_factory import create_local_app

        app = create_local_app()
        config = uvicorn.Config(
            app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
            lifespan="on",
            log_config=None,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._run_server, name="twaps-local-ui", daemon=True)
        self._thread.start()
        self._wait_until_ready()
        return self.url

    def stop(self, timeout: float = 5.0) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def open_trades(self) -> list[dict[str, Any]]:
        try:
            response = httpx.get(f"{self.url}/api/trading/open-trades", timeout=2.0)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items") if isinstance(payload, dict) else []
            return [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
        except Exception:
            return []

    def _run_server(self) -> None:
        assert self._server is not None
        try:
            asyncio.run(self._server.serve())
        except BaseException as exc:
            self._startup_error = exc
            logger.exception("Local UI server crashed")
            raise

    def _wait_until_ready(self, timeout: float = 15.0) -> None:
        deadline = time.time() + timeout
        last_error: Exception | None = None
        while time.time() < deadline:
            if self._startup_error is not None:
                raise RuntimeError(f"Локальный интерфейс TWAPs не запустился: {self._startup_error}") from self._startup_error
            if self._thread is not None and not self._thread.is_alive():
                raise RuntimeError("Локальный интерфейс TWAPs не запустился: процесс сервера завершился")
            try:
                with socket.create_connection((self.host, self.port), timeout=0.5):
                    return
            except OSError as exc:
                last_error = exc
                time.sleep(0.1)
        raise RuntimeError(f"Локальный интерфейс TWAPs не запустился: {last_error}")


def format_open_trades_for_warning(trades: list[dict[str, Any]], limit: int = 5) -> str:
    if not trades:
        return ""
    rows: list[str] = []
    for trade in trades[:limit]:
        symbol = str(trade.get("symbol") or trade.get("asset") or "?")
        direction = str(trade.get("direction") or "?")
        rows.append(f"• {symbol} / {direction}")
    if len(trades) > limit:
        rows.append(f"• ...и ещё {len(trades) - limit}")
    return "\n".join(rows)

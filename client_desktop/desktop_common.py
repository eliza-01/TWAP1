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


try:
    from client_desktop import build_config_generated as _build_config
except Exception:  # generated only by desktop compile scripts
    _build_config = None

APP_TITLE = str(getattr(_build_config, "APP_TITLE", "TWAPs"))
HOST = "127.0.0.1"
DEFAULT_STAGE_HTTP_URL = "https://beta.twaps.ru"
DEFAULT_STAGE_WS_URL = "wss://beta.twaps.ru/ws/signals"
DEFAULT_PROD_HTTP_URL = "https://twaps.ru"
DEFAULT_PROD_WS_URL = "wss://twaps.ru/ws/signals"
BUILD_FLAVOR = str(getattr(_build_config, "BUILD_FLAVOR", "stage")).strip().lower() or "stage"
BUILD_DEFAULT_HTTP_URL = str(getattr(_build_config, "DEFAULT_HTTP_URL", DEFAULT_STAGE_HTTP_URL)).strip().rstrip("/") or DEFAULT_STAGE_HTTP_URL
BUILD_DEFAULT_WS_URL = str(getattr(_build_config, "DEFAULT_WS_URL", DEFAULT_STAGE_WS_URL)).strip() or DEFAULT_STAGE_WS_URL

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
    os.environ.setdefault("TWAP_CLIENT_BUILD_ENV", BUILD_FLAVOR)

    # Desktop builds must be usable without a project .env. In customer/test
    # builds the safe default is the currently configured public stage server;
    # prod can still be forced by placing .env next to the exe or by exporting
    # TWAP_CLIENT_HTTP_URL / TWAP_CLIENT_WS_URL / LOCAL_SIGNAL_* variables.
    http_url, ws_url = _resolve_default_signal_urls()
    os.environ.setdefault("LOCAL_SIGNAL_HTTP_URL", http_url)
    os.environ.setdefault("LOCAL_SIGNAL_WS_URL", ws_url)

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


def _resolve_default_signal_urls() -> tuple[str, str]:
    explicit_http = (
        os.getenv("TWAP_CLIENT_HTTP_URL")
        or os.getenv("LOCAL_SIGNAL_HTTP_URL")
        or os.getenv("PUBLIC_BASE_URL")
        or ""
    ).strip().rstrip("/")
    explicit_ws = (
        os.getenv("TWAP_CLIENT_WS_URL")
        or os.getenv("LOCAL_SIGNAL_WS_URL")
        or os.getenv("PUBLIC_SIGNAL_WS_URL")
        or ""
    ).strip()

    if explicit_http and explicit_ws:
        return explicit_http, explicit_ws

    # Do not infer the customer endpoint from STAGE here. STAGE controls the
    # server deployment profile, while the desktop client may intentionally use
    # beta even when the project .env has STAGE=OFF. Production endpoint must be
    # selected explicitly through LOCAL_SIGNAL_* or TWAP_CLIENT_* variables.
    default_http = BUILD_DEFAULT_HTTP_URL
    default_ws = BUILD_DEFAULT_WS_URL

    if explicit_http and not explicit_ws:
        return explicit_http, _http_to_ws_url(explicit_http)
    if explicit_ws and not explicit_http:
        return _ws_to_http_url(explicit_ws), explicit_ws
    return default_http, default_ws


def _http_to_ws_url(http_url: str) -> str:
    clean = http_url.strip().rstrip("/")
    if clean.startswith("https://"):
        return "wss://" + clean.removeprefix("https://") + "/ws/signals"
    if clean.startswith("http://"):
        return "ws://" + clean.removeprefix("http://") + "/ws/signals"
    return BUILD_DEFAULT_WS_URL


def _ws_to_http_url(ws_url: str) -> str:
    clean = ws_url.strip()
    if clean.endswith("/ws/signals"):
        clean = clean[: -len("/ws/signals")]
    if clean.startswith("wss://"):
        return "https://" + clean.removeprefix("wss://").rstrip("/")
    if clean.startswith("ws://"):
        return "http://" + clean.removeprefix("ws://").rstrip("/")
    return BUILD_DEFAULT_HTTP_URL


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


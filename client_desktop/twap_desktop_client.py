from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from app.local.api.app_factory import create_local_app


def main() -> None:
    _configure_local_environment()
    host = "127.0.0.1"
    port = _pick_port(8765)
    url = f"http://{host}:{port}"

    thread = threading.Thread(
        target=_run_server,
        args=(host, port),
        daemon=True,
    )
    thread.start()

    time.sleep(1.2)
    webbrowser.open(url)

    print("TWAP Desktop Client started")
    print(f"Local UI: {url}")
    print("Close this window to stop the client.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def _configure_local_environment() -> None:
    data_dir = _data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("LOCAL_SETTINGS_PATH", str(data_dir / "settings.json"))
    os.environ.setdefault("LOCAL_SIGNALS_PATH", str(data_dir / "signals.json"))
    os.environ.setdefault("LOCAL_TRADES_PATH", str(data_dir / "trades.json"))

    # Public defaults for the stage build. For prod builds set these env vars before
    # running PyInstaller or edit build_windows.bat.
    http_url = os.getenv("TWAP_CLIENT_HTTP_URL") or os.getenv("LOCAL_SIGNAL_HTTP_URL") or "https://beta.twaps.ru"
    ws_url = os.getenv("TWAP_CLIENT_WS_URL") or os.getenv("LOCAL_SIGNAL_WS_URL") or "wss://beta.twaps.ru/ws/signals"
    os.environ.setdefault("LOCAL_SIGNAL_HTTP_URL", http_url.rstrip("/"))
    os.environ.setdefault("LOCAL_SIGNAL_WS_URL", ws_url)


def _data_dir() -> Path:
    if os.getenv("TWAP_CLIENT_DATA_DIR"):
        return Path(os.environ["TWAP_CLIENT_DATA_DIR"])
    if sys.platform.startswith("win") and os.getenv("APPDATA"):
        return Path(os.environ["APPDATA"]) / "TWAP Desktop Client"
    return Path.home() / ".twap_desktop_client"


def _pick_port(preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return 0


def _run_server(host: str, port: int) -> None:
    uvicorn.run(
        create_local_app(),
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()

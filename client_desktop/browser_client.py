from __future__ import annotations

import signal
import sys
import time
import webbrowser

from client_desktop.desktop_common import APP_TITLE, LocalUiServer, prepare_desktop_environment


def main() -> int:
    prepare_desktop_environment()
    server = LocalUiServer()

    try:
        url = server.start()
    except Exception as exc:
        print(f"{APP_TITLE}: не удалось запустить локальный интерфейс: {exc}")
        return 1

    print(f"{APP_TITLE}: локальный интерфейс запущен: {url}")
    print("Закройте это окно, чтобы остановить локальный клиент.")
    webbrowser.open(url, new=2)

    stopped = False

    def _stop(*_args: object) -> None:
        nonlocal stopped
        stopped = True
        server.stop()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    try:
        while not stopped:
            time.sleep(0.5)
    finally:
        server.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

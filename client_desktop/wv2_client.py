from __future__ import annotations

import ctypes
import sys
from typing import Final

from client_desktop.desktop_common import (
    APP_TITLE,
    LocalUiServer,
    format_open_trades_for_warning,
    prepare_desktop_environment,
)

MB_OK: Final[int] = 0x00000000
MB_ICONERROR: Final[int] = 0x00000010
MB_YESNO: Final[int] = 0x00000004
MB_ICONWARNING: Final[int] = 0x00000030
IDYES: Final[int] = 6


def _message_box(text: str, title: str = APP_TITLE, flags: int = MB_OK) -> int:
    try:
        return int(ctypes.windll.user32.MessageBoxW(None, text, title, flags))
    except Exception:
        print(f"{title}: {text}")
        return IDYES


def _confirm_close(server: LocalUiServer) -> bool:
    trades = server.open_trades()
    if not trades:
        return True

    details = format_open_trades_for_warning(trades)
    text = (
        "Есть активные сделки.\n\n"
        f"{details}\n\n"
        "Закрытие программы остановит локальный клиент и обработку новых сигналов.\n"
        "Завершить работу TWAPs?"
    )
    return _message_box(text, APP_TITLE, MB_YESNO | MB_ICONWARNING) == IDYES


def main() -> int:
    prepare_desktop_environment()
    server = LocalUiServer()

    try:
        url = server.start()
    except Exception as exc:
        _message_box(f"Не удалось запустить локальный интерфейс TWAPs:\n\n{exc}", APP_TITLE, MB_OK | MB_ICONERROR)
        return 1

    try:
        import webview
    except Exception as exc:
        server.stop()
        _message_box(
            "Не удалось загрузить pywebview.\n\n"
            "Проверьте, что WV2-сборка собрана через client_desktop\\build_wv2.bat.\n\n"
            f"Ошибка: {exc}",
            APP_TITLE,
            MB_OK | MB_ICONERROR,
        )
        return 1

    try:
        window = webview.create_window(
            APP_TITLE,
            url,
            width=1280,
            height=860,
            min_size=(1024, 720),
            confirm_close=False,
        )

        def on_closing() -> bool:
            return _confirm_close(server)

        window.events.closing += on_closing

        try:
            webview.start(gui="edgechromium")
        except Exception as exc:
            _message_box(
                "Не удалось открыть WebView2-окно.\n\n"
                "На этом компьютере может отсутствовать Microsoft Edge WebView2 Runtime. "
                "Установите WebView2 Runtime или соберите обычную browser-версию клиента.\n\n"
                f"Ошибка: {exc}",
                APP_TITLE,
                MB_OK | MB_ICONERROR,
            )
            return 1
    finally:
        server.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

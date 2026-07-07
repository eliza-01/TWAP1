from __future__ import annotations

import ctypes
import logging
import threading
from pathlib import Path
from typing import Callable, Final

from client_desktop.desktop_common import (
    APP_TITLE,
    LocalUiServer,
    app_icon_png_path,
    format_open_trades_for_warning,
    prepare_desktop_environment,
)

MB_OK: Final[int] = 0x00000000
MB_ICONERROR: Final[int] = 0x00000010
MB_YESNO: Final[int] = 0x00000004
MB_YESNOCANCEL: Final[int] = 0x00000003
MB_ICONWARNING: Final[int] = 0x00000030
IDYES: Final[int] = 6
IDNO: Final[int] = 7
IDCANCEL: Final[int] = 2

logger = logging.getLogger(__name__)


def _message_box(text: str, title: str = APP_TITLE, flags: int = MB_OK) -> int:
    try:
        return int(ctypes.windll.user32.MessageBoxW(None, text, title, flags))
    except Exception:
        print(f"{title}: {text}")
        return IDYES


def _close_question(server: LocalUiServer) -> str:
    trades = server.open_trades()
    active_trades_text = ""
    if trades:
        active_trades_text = (
            "\n\nЕсть активные сделки:\n"
            f"{format_open_trades_for_warning(trades)}\n\n"
            "Выход остановит локальный клиент и обработку новых сигналов."
        )

    return (
        "Что сделать с TWAPs?"
        f"{active_trades_text}\n\n"
        "Да — выйти из приложения.\n"
        "Нет — свернуть в трей.\n"
        "Отмена — продолжить работу."
    )


def _ask_exit_or_tray(server: LocalUiServer) -> str:
    result = _message_box(_close_question(server), APP_TITLE, MB_YESNOCANCEL | MB_ICONWARNING)
    if result == IDYES:
        return "exit"
    if result == IDNO:
        return "tray"
    return "cancel"


class TrayController:
    def __init__(self, icon_path: Path | None) -> None:
        self.icon_path = icon_path
        self._icon = None
        self._thread: threading.Thread | None = None

    def start(
        self,
        show_window: Callable[[], None],
        hide_window: Callable[[], None],
        exit_app: Callable[[], None],
    ) -> None:
        try:
            import pystray
            from PIL import Image
        except Exception as exc:
            logger.exception("System tray is unavailable")
            _message_box(
                "Не удалось запустить трей TWAPs.\n\n"
                "Приложение продолжит работу без иконки в трее.\n\n"
                f"Ошибка: {exc}",
                APP_TITLE,
                MB_OK | MB_ICONWARNING,
            )
            return

        try:
            image = Image.open(self.icon_path).convert("RGBA") if self.icon_path else Image.new("RGBA", (64, 64), (17, 26, 42, 255))
        except Exception as exc:
            logger.exception("Failed to load tray icon")
            image = Image.new("RGBA", (64, 64), (17, 26, 42, 255))

        def _show(_icon: object = None, _item: object = None) -> None:
            show_window()

        def _hide(_icon: object = None, _item: object = None) -> None:
            hide_window()

        def _exit(_icon: object = None, _item: object = None) -> None:
            exit_app()

        self._icon = pystray.Icon(
            "TWAPs",
            image,
            APP_TITLE,
            menu=pystray.Menu(
                pystray.MenuItem("Открыть", _show, default=True),
                pystray.MenuItem("Свернуть в трей", _hide),
                pystray.MenuItem("Выйти", _exit),
            ),
        )
        self._thread = threading.Thread(target=self._icon.run, name="twaps-tray", daemon=True)
        self._thread.start()

    def notify_hidden(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify("TWAPs продолжает работать в трее", APP_TITLE)
        except Exception:
            logger.debug("Tray notification is unavailable", exc_info=True)

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            logger.debug("Tray stop failed", exc_info=True)
        self._icon = None


def main() -> int:
    prepare_desktop_environment()
    server = LocalUiServer()
    tray = TrayController(app_icon_png_path())
    force_exit = False

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
            "Проверьте, что WV2-сборка собрана через client_desktop\\wv2\\compile_prod.bat "
            "или client_desktop\\wv2\\compile_stage.bat.\n\n"
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
            frameless=True,
            easy_drag=True,
        )

        def show_window() -> None:
            try:
                window.show()
                window.restore()
            except Exception:
                logger.debug("Show window failed", exc_info=True)

        def hide_window() -> None:
            try:
                window.hide()
                tray.notify_hidden()
            except Exception:
                logger.debug("Hide window failed", exc_info=True)

        def exit_app() -> None:
            nonlocal force_exit
            force_exit = True
            tray.stop()
            try:
                window.destroy()
            except Exception:
                logger.debug("Destroy window failed", exc_info=True)

        def on_closing() -> bool:
            if force_exit:
                return True
            action = _ask_exit_or_tray(server)
            if action == "exit":
                tray.stop()
                return True
            if action == "tray":
                hide_window()
                return False
            return False

        window.events.closing += on_closing
        tray.start(show_window=show_window, hide_window=hide_window, exit_app=exit_app)

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
        tray.stop()
        server.stop()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

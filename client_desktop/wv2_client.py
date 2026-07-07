from __future__ import annotations

import ctypes
import logging
import os
import threading
import time
from ctypes import wintypes
from pathlib import Path
from typing import Callable, Final

from client_desktop.desktop_common import (
    APP_TITLE,
    LocalUiServer,
    app_icon_ico_path,
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

WM_NCLBUTTONDOWN: Final[int] = 0x00A1
HTCAPTION: Final[int] = 2
WM_SETICON: Final[int] = 0x0080
ICON_SMALL: Final[int] = 0
ICON_BIG: Final[int] = 1
IMAGE_ICON: Final[int] = 1
LR_LOADFROMFILE: Final[int] = 0x0010
LR_DEFAULTSIZE: Final[int] = 0x0040
GCLP_HICON: Final[int] = -14
GCLP_HICONSM: Final[int] = -34

# Windows DWM titlebar styling. Color values are COLORREF: 0x00BBGGRR.
DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY: Final[int] = 19
DWMWA_USE_IMMERSIVE_DARK_MODE: Final[int] = 20
DWMWA_BORDER_COLOR: Final[int] = 34
DWMWA_CAPTION_COLOR: Final[int] = 35
DWMWA_TEXT_COLOR: Final[int] = 36

TITLEBAR_BG_COLOR: Final[int] = 0x001D110B  # rgb(11, 17, 29)
TITLEBAR_BORDER_COLOR: Final[int] = 0x00B7E76E  # rgb(110, 231, 183)
TITLEBAR_TEXT_COLOR: Final[int] = 0x00F8EEE8  # rgb(232, 238, 248)

WM_NCHITTEST: Final[int] = 0x0084
WM_NCCALCSIZE: Final[int] = 0x0083
WM_GETMINMAXINFO: Final[int] = 0x0024
GWL_STYLE: Final[int] = -16
GWL_WNDPROC: Final[int] = -4
WS_CAPTION: Final[int] = 0x00C00000
WS_THICKFRAME: Final[int] = 0x00040000
WS_SYSMENU: Final[int] = 0x00080000
WS_MINIMIZEBOX: Final[int] = 0x00020000
WS_MAXIMIZEBOX: Final[int] = 0x00010000
SWP_NOSIZE: Final[int] = 0x0001
SWP_NOMOVE: Final[int] = 0x0002
SWP_NOZORDER: Final[int] = 0x0004
SWP_FRAMECHANGED: Final[int] = 0x0020

HTCLIENT: Final[int] = 1
HTLEFT: Final[int] = 10
HTRIGHT: Final[int] = 11
HTTOP: Final[int] = 12
HTTOPLEFT: Final[int] = 13
HTTOPRIGHT: Final[int] = 14
HTBOTTOM: Final[int] = 15
HTBOTTOMLEFT: Final[int] = 16
HTBOTTOMRIGHT: Final[int] = 17

SM_CXSIZEFRAME: Final[int] = 32
SM_CXPADDEDBORDER: Final[int] = 92
MIN_WINDOW_WIDTH: Final[int] = 1024
MIN_WINDOW_HEIGHT: Final[int] = 720
DRAG_ZONE_HEIGHT: Final[int] = 76
DRAG_ZONE_MAX_WIDTH: Final[int] = 620

logger = logging.getLogger(__name__)
_NATIVE_CHROME_CONTROLLERS: list[NativeWindowChromeController] = []


def _message_box(text: str, title: str = APP_TITLE, flags: int = MB_OK) -> int:
    try:
        return int(ctypes.windll.user32.MessageBoxW(None, text, title, flags))
    except Exception:
        print(f"{title}: {text}")
        return IDYES




def _set_app_user_model_id() -> None:
    """Make Windows associate the taskbar icon with this app, not python/pywebview."""
    try:
        flavor = "stage" if "STAGE" in APP_TITLE.upper() else "prod"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"TWAPs.Client.{flavor}")
    except Exception:
        logger.debug("Could not set AppUserModelID", exc_info=True)


def _main_window_handle(preferred_title: str = APP_TITLE) -> int:
    handles = _current_process_window_handles(preferred_title)
    return handles[0] if handles else 0


def _begin_native_move_or_resize(hit_test_code: int) -> bool:
    try:
        user32 = ctypes.windll.user32
        hwnd = _main_window_handle(APP_TITLE) or user32.GetForegroundWindow()
        if not hwnd:
            return False
        user32.ReleaseCapture()
        user32.SendMessageW(wintypes.HWND(hwnd), WM_NCLBUTTONDOWN, hit_test_code, 0)
        return True
    except Exception:
        logger.debug("Native window move/resize failed", exc_info=True)
        return False


def _begin_window_drag() -> bool:
    """Start native frameless-window dragging from a custom HTML drag region."""
    return _begin_native_move_or_resize(HTCAPTION)


def _begin_window_resize(direction: str) -> bool:
    mapping = {
        "left": HTLEFT,
        "right": HTRIGHT,
        "top": HTTOP,
        "bottom": HTBOTTOM,
        "top-left": HTTOPLEFT,
        "top-right": HTTOPRIGHT,
        "bottom-left": HTBOTTOMLEFT,
        "bottom-right": HTBOTTOMRIGHT,
    }
    hit_test_code = mapping.get(str(direction or "").strip().lower())
    if not hit_test_code:
        return False
    return _begin_native_move_or_resize(hit_test_code)


def _current_process_window_handles(preferred_title: str) -> list[int]:
    handles: list[int] = []
    preferred: list[int] = []
    user32 = ctypes.windll.user32
    current_pid = os.getpid()

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def _callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if int(pid.value) != current_pid:
            return True

        title_buffer = ctypes.create_unicode_buffer(512)
        user32.GetWindowTextW(hwnd, title_buffer, len(title_buffer))
        title = title_buffer.value or ""

        if preferred_title and preferred_title in title:
            preferred.append(int(hwnd))
        else:
            handles.append(int(hwnd))
        return True

    user32.EnumWindows(enum_proc_type(_callback), 0)
    return preferred + handles


def _set_class_long_ptr(hwnd: int, index: int, value: int) -> None:
    user32 = ctypes.windll.user32
    try:
        setter = user32.SetClassLongPtrW
    except AttributeError:
        setter = user32.SetClassLongW
    setter(wintypes.HWND(hwnd), index, value)


def _set_window_icon(icon_path: Path | None) -> None:
    """Set taskbar/window icon at runtime in addition to the PyInstaller exe icon."""
    if not icon_path or not icon_path.exists():
        logger.warning("TWAPs .ico was not found for runtime window icon: %s", icon_path)
        return

    try:
        user32 = ctypes.windll.user32
        hicon = user32.LoadImageW(
            None,
            str(icon_path),
            IMAGE_ICON,
            0,
            0,
            LR_LOADFROMFILE | LR_DEFAULTSIZE,
        )
        if not hicon:
            logger.warning("Windows could not load TWAPs icon: %s", icon_path)
            return

        for hwnd in _current_process_window_handles(APP_TITLE):
            user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon)
            user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon)
            _set_class_long_ptr(hwnd, GCLP_HICON, hicon)
            _set_class_long_ptr(hwnd, GCLP_HICONSM, hicon)
    except Exception:
        logger.debug("Runtime window icon setup failed", exc_info=True)


def _dwm_set_int(hwnd: int, attribute: int, value: int) -> bool:
    try:
        dwmapi = ctypes.windll.dwmapi
        data = ctypes.c_int(value)
        result = int(dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(attribute),
            ctypes.byref(data),
            ctypes.sizeof(data),
        ))
        return result == 0
    except Exception:
        logger.debug("DWM int attribute setup failed: %s", attribute, exc_info=True)
        return False


def _dwm_set_color(hwnd: int, attribute: int, colorref: int) -> bool:
    try:
        dwmapi = ctypes.windll.dwmapi
        data = ctypes.c_uint(colorref)
        result = int(dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(attribute),
            ctypes.byref(data),
            ctypes.sizeof(data),
        ))
        return result == 0
    except Exception:
        logger.debug("DWM color attribute setup failed: %s", attribute, exc_info=True)
        return False


def _style_native_title_bar(hwnd: int) -> None:
    """Apply dark native Windows title bar/border colors to the WV2 window.

    Windows 11 supports explicit caption/border/text colors. Windows 10 usually
    supports only immersive dark mode; the calls that are unsupported are
    ignored by DWM.
    """
    if not hwnd or os.name != "nt":
        return

    # Try both attribute IDs because Microsoft changed this value around 20H1.
    _dwm_set_int(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, 1)
    _dwm_set_int(hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE_LEGACY, 1)

    _dwm_set_color(hwnd, DWMWA_CAPTION_COLOR, TITLEBAR_BG_COLOR)
    _dwm_set_color(hwnd, DWMWA_BORDER_COLOR, TITLEBAR_BORDER_COLOR)
    _dwm_set_color(hwnd, DWMWA_TEXT_COLOR, TITLEBAR_TEXT_COLOR)


def _style_all_native_title_bars(timeout_seconds: float = 5.0) -> None:
    if os.name != "nt":
        return

    deadline = time.time() + timeout_seconds
    applied: set[int] = set()
    while time.time() < deadline:
        handles = _current_process_window_handles(APP_TITLE)
        for hwnd in handles:
            if hwnd in applied:
                continue
            _style_native_title_bar(hwnd)
            applied.add(hwnd)
        if applied:
            return
        time.sleep(0.1)


def _apply_window_branding() -> None:
    _set_window_icon(app_icon_ico_path())
    _style_all_native_title_bars()


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class MINMAXINFO(ctypes.Structure):
    _fields_ = [
        ("ptReserved", POINT),
        ("ptMaxSize", POINT),
        ("ptMaxPosition", POINT),
        ("ptMinTrackSize", POINT),
        ("ptMaxTrackSize", POINT),
    ]


def _signed_screen_coord(value: int) -> int:
    return int(ctypes.c_short(value & 0xFFFF).value)


def _lparam_screen_point(lparam: int) -> tuple[int, int]:
    raw = int(lparam)
    return _signed_screen_coord(raw), _signed_screen_coord(raw >> 16)


def _get_window_long_ptr(hwnd: int, index: int) -> int:
    user32 = ctypes.windll.user32
    try:
        getter = user32.GetWindowLongPtrW
    except AttributeError:
        getter = user32.GetWindowLongW
    getter.argtypes = [wintypes.HWND, ctypes.c_int]
    getter.restype = ctypes.c_ssize_t
    return int(getter(wintypes.HWND(hwnd), index))


def _set_window_long_ptr(hwnd: int, index: int, value: int) -> int:
    user32 = ctypes.windll.user32
    try:
        setter = user32.SetWindowLongPtrW
    except AttributeError:
        setter = user32.SetWindowLongW
    setter.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    setter.restype = ctypes.c_ssize_t
    return int(setter(wintypes.HWND(hwnd), index, ctypes.c_ssize_t(value)))


def _default_resize_border() -> int:
    try:
        user32 = ctypes.windll.user32
        size_frame = int(user32.GetSystemMetrics(SM_CXSIZEFRAME) or 0)
        padded = int(user32.GetSystemMetrics(SM_CXPADDEDBORDER) or 0)
        return max(8, size_frame + padded)
    except Exception:
        return 8


def _force_resizable_frameless_style(hwnd: int) -> None:
    user32 = ctypes.windll.user32
    style = _get_window_long_ptr(hwnd, GWL_STYLE)
    style = (style | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX) & ~WS_CAPTION
    _set_window_long_ptr(hwnd, GWL_STYLE, style)
    user32.SetWindowPos(
        wintypes.HWND(hwnd),
        None,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
    )


class NativeWindowChromeController:
    """Windows-only frameless chrome: native resize borders and title-block drag."""

    def __init__(self, title: str = APP_TITLE) -> None:
        self.title = title
        self.hwnd = 0
        self._old_proc = 0
        self._wnd_proc = None
        self._border = _default_resize_border()

    def install(self, timeout_seconds: float = 8.0) -> bool:
        if not os.name == "nt":
            return False

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            hwnd = _main_window_handle(self.title)
            if hwnd:
                return self._install_for_hwnd(hwnd)
            time.sleep(0.1)

        logger.warning("Could not find TWAPs WV2 main HWND for native chrome")
        return False

    def _install_for_hwnd(self, hwnd: int) -> bool:
        try:
            self.hwnd = hwnd
            _force_resizable_frameless_style(hwnd)
            wnd_proc_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
            self._wnd_proc = wnd_proc_type(self._handle_message)
            self._old_proc = _set_window_long_ptr(hwnd, GWL_WNDPROC, ctypes.cast(self._wnd_proc, ctypes.c_void_p).value)
            logger.info("Native frameless chrome installed for HWND %s", hwnd)
            return True
        except Exception:
            logger.debug("Native frameless chrome install failed", exc_info=True)
            return False

    def _handle_message(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        try:
            if msg == WM_NCCALCSIZE and int(wparam):
                return 0

            if msg == WM_GETMINMAXINFO:
                info = ctypes.cast(lparam, ctypes.POINTER(MINMAXINFO)).contents
                info.ptMinTrackSize.x = MIN_WINDOW_WIDTH
                info.ptMinTrackSize.y = MIN_WINDOW_HEIGHT
                return 0

            if msg == WM_NCHITTEST:
                hit = self._hit_test(lparam)
                if hit != HTCLIENT:
                    return hit
        except Exception:
            logger.debug("Native chrome message handling failed", exc_info=True)

        return self._call_original(hwnd, msg, wparam, lparam)

    def _hit_test(self, lparam: int) -> int:
        user32 = ctypes.windll.user32
        rect = wintypes.RECT()
        if not user32.GetWindowRect(wintypes.HWND(self.hwnd), ctypes.byref(rect)):
            return HTCLIENT

        x, y = _lparam_screen_point(lparam)
        width = int(rect.right - rect.left)
        height = int(rect.bottom - rect.top)
        client_x = x - int(rect.left)
        client_y = y - int(rect.top)
        border = self._border

        on_left = client_x <= border
        on_right = client_x >= width - border
        on_top = client_y <= border
        on_bottom = client_y >= height - border

        if on_top and on_left:
            return HTTOPLEFT
        if on_top and on_right:
            return HTTOPRIGHT
        if on_bottom and on_left:
            return HTBOTTOMLEFT
        if on_bottom and on_right:
            return HTBOTTOMRIGHT
        if on_left:
            return HTLEFT
        if on_right:
            return HTRIGHT
        if on_top:
            return HTTOP
        if on_bottom:
            return HTBOTTOM

        drag_width = min(DRAG_ZONE_MAX_WIDTH, max(260, width - 360))
        if border < client_x < drag_width and border < client_y <= DRAG_ZONE_HEIGHT:
            return HTCAPTION

        return HTCLIENT

    def _call_original(self, hwnd: int, msg: int, wparam: int, lparam: int) -> int:
        user32 = ctypes.windll.user32
        user32.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        return int(user32.CallWindowProcW(ctypes.c_void_p(self._old_proc), hwnd, msg, wparam, lparam))


def _install_native_window_chrome() -> None:
    controller = NativeWindowChromeController(APP_TITLE)
    if controller.install():
        _NATIVE_CHROME_CONTROLLERS.append(controller)


class WindowBridge:
    def __init__(self) -> None:
        self._minimize: Callable[[], None] | None = None
        self._minimize_to_tray: Callable[[], None] | None = None
        self._request_close: Callable[[], None] | None = None

    def bind(
        self,
        *,
        minimize: Callable[[], None],
        minimize_to_tray: Callable[[], None],
        request_close: Callable[[], None],
    ) -> None:
        self._minimize = minimize
        self._minimize_to_tray = minimize_to_tray
        self._request_close = request_close

    def minimize(self) -> bool:
        if self._minimize is None:
            return False
        self._minimize()
        return True

    def minimize_to_tray(self) -> bool:
        if self._minimize_to_tray is None:
            return False
        self._minimize_to_tray()
        return True

    def request_close(self) -> bool:
        if self._request_close is None:
            return False
        self._request_close()
        return True


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
    _set_app_user_model_id()
    server = LocalUiServer()
    tray = TrayController(app_icon_png_path())
    bridge = WindowBridge()
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
            frameless=False,
            resizable=True,
            easy_drag=False,
            js_api=bridge,
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

        def minimize_window() -> None:
            try:
                window.minimize()
            except Exception:
                logger.debug("Minimize window failed", exc_info=True)

        def exit_app() -> None:
            nonlocal force_exit
            force_exit = True
            tray.stop()
            try:
                window.destroy()
            except Exception:
                logger.debug("Destroy window failed", exc_info=True)

        def ask_and_apply_close_action() -> None:
            action = _ask_exit_or_tray(server)
            if action == "exit":
                exit_app()
            elif action == "tray":
                hide_window()

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

        bridge.bind(
            minimize=minimize_window,
            minimize_to_tray=hide_window,
            request_close=ask_and_apply_close_action,
        )
        window.events.closing += on_closing
        tray.start(show_window=show_window, hide_window=hide_window, exit_app=exit_app)

        try:
            webview.start(
                func=_apply_window_branding,
                gui="edgechromium",
            )
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

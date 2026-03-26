import logging
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import webview
from aw_core.log import setup_logging
from PIL import Image

from .api import AppApi
from .manager import Manager
from .server_info import get_root_url, wait_for_server
from .settings import load_settings

logger = logging.getLogger(__name__)


class TrayController:
    def __init__(self, window, shutdown_handler: Callable[..., None], manager: Manager) -> None:
        self._window = window
        self._shutdown_handler = shutdown_handler
        self._manager = manager
        self._tray_icon = None
        self._is_quitting = False
        self._is_paused = False
        self._monitor_stop = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        self._tray_thread: Optional[threading.Thread] = None

    @property
    def is_available(self) -> bool:
        return self._tray_icon is not None

    @property
    def is_quitting(self) -> bool:
        return self._is_quitting

    def install(self) -> None:
        if sys.platform not in ["win32", "cygwin"]:
            return
        if self._tray_icon is not None:
            return

        try:
            import pystray

            image = self._load_tray_image()
            self._tray_icon = pystray.Icon(
                "activitywatch",
                image,
                "ActivityWatch",
                menu=pystray.Menu(
                    pystray.MenuItem("显示窗口", self._on_show_window),
                    pystray.MenuItem("设置", self._on_open_settings),
                    pystray.MenuItem(self._pause_menu_label, self._on_toggle_pause),
                    pystray.MenuItem("退出", self._on_quit),
                ),
            )
            self._tray_thread = threading.Thread(target=self._run_tray, name="aw-tray-icon", daemon=True)
            self._tray_thread.start()
            self._start_minimize_monitor()
        except Exception:
            logger.exception("Failed to initialize tray icon")

    def _run_tray(self) -> None:
        if self._tray_icon is None:
            return
        try:
            self._tray_icon.run()
        except Exception:
            logger.exception("Tray icon loop failed")

    def hide_window(self) -> None:
        if not self.is_available:
            return
        try:
            self._window.hide()
        except Exception:
            logger.exception("Failed to hide window to tray")

    def show_window(self) -> None:
        try:
            self._window.restore()
        except Exception:
            logger.debug("Window restore failed", exc_info=True)

        try:
            self._window.show()
        except Exception:
            logger.exception("Failed to show window from tray")
            return

        native = getattr(self._window, "native", None)
        if native is not None:
            for attr_name in ("Activate", "activate"):
                activate = getattr(native, attr_name, None)
                if callable(activate):
                    try:
                        activate()
                        break
                    except Exception:
                        logger.debug("Native activate failed", exc_info=True)

    def open_settings(self) -> None:
        self.show_window()
        try:
            self._window.evaluate_js("window.AwPywebviewApp?.openSettingsFromTray?.(); true;")
        except Exception:
            logger.exception("Failed to open settings from tray")

    def toggle_pause(self) -> None:
        try:
            if self._is_paused:
                self._manager.resume_tracking()
                self._is_paused = False
            else:
                self._manager.pause_tracking()
                self._is_paused = True
            self._update_tray_menu()
        except Exception:
            logger.exception("Failed to toggle tray pause state")

    def _pause_menu_label(self, _item) -> str:
        return "恢复统计" if self._is_paused else "暂停统计"

    def _update_tray_menu(self) -> None:
        if self._tray_icon is None:
            return
        try:
            self._tray_icon.update_menu()
        except Exception:
            logger.debug("Failed to refresh tray menu", exc_info=True)

    def _start_minimize_monitor(self) -> None:
        if self._monitor_thread is not None:
            return

        def _monitor() -> None:
            while not self._monitor_stop.wait(0.6):
                if self._is_quitting or not self.is_available:
                    continue
                try:
                    if self._is_native_minimized():
                        self.hide_window()
                except Exception:
                    logger.debug("Tray minimize monitor check failed", exc_info=True)

        self._monitor_thread = threading.Thread(target=_monitor, name="aw-tray-monitor", daemon=True)
        self._monitor_thread.start()

    def _is_native_minimized(self) -> bool:
        native = getattr(self._window, "native", None)
        if native is None:
            return False

        for attr_name in ("WindowState", "windowState"):
            state = getattr(native, attr_name, None)
            if state is None:
                continue
            try:
                return str(state) == "Minimized" or int(state) == 1
            except Exception:
                return str(state) == "Minimized"

        return False

    def quit(self) -> None:
        self._is_quitting = True
        self.dispose()
        self._shutdown_handler()

    def dispose(self) -> None:
        self._monitor_stop.set()
        if self._tray_icon is None:
            return
        try:
            self._tray_icon.stop()
        except Exception:
            logger.debug("Failed to stop tray icon", exc_info=True)
        finally:
            self._tray_icon = None

    def _resolve_icon_path(self) -> Optional[Path]:
        candidates = [
            Path(__file__).parent / "ui" / "activitywatch.ico",
            Path(__file__).parent / "ui" / "favicon.ico",
            Path(__file__).resolve().parents[2] / "media" / "logo.ico",
            Path(__file__).resolve().parents[2] / "aw-server" / "aw-webui" / "media" / "logo" / "logo.ico",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _load_tray_image(self):
        icon_path = self._resolve_icon_path()
        if icon_path and icon_path.exists():
            return Image.open(icon_path)
        return Image.new("RGBA", (64, 64), (31, 41, 55, 255))

    def _on_show_window(self, _icon=None, _item=None) -> None:
        self.show_window()

    def _on_open_settings(self, _icon=None, _item=None) -> None:
        self.open_settings()

    def _on_toggle_pause(self, _icon=None, _item=None) -> None:
        self.toggle_pause()

    def _on_quit(self, _icon=None, _item=None) -> None:
        self.quit()


def _start_modules(manager: Manager, autostart_modules: List[str]) -> None:
    manager.autostart(autostart_modules)


def _wait_until_server_ready(settings: dict) -> str:
    url = get_root_url(testing=False)
    timeout = int(settings.get("server_start_timeout", 20))
    if not wait_for_server(url, timeout=timeout):
        raise RuntimeError("aw-server 启动超时")
    logger.info("Server ready at %s", url)
    return url


def _window_size(settings: dict) -> Tuple[int, int]:
    return int(settings.get("window_width", 1200)), int(settings.get("window_height", 800))


def _get_ui_path() -> str:
    ui_dir = Path(__file__).parent / "ui"
    return (ui_dir / "index.html").resolve().as_uri()


def _build_shutdown_handler(manager: Manager) -> Callable[..., None]:
    def _shutdown(*_args):
        logger.info("Shutdown requested")
        manager.stop_all()
        os._exit(0)

    return _shutdown


def _register_signal_handlers(shutdown_handler: Callable[..., None]) -> None:
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)


def _create_window(width: int, height: int, settings: dict):
    ui_url = _get_ui_path()
    api = AppApi(settings)
    return webview.create_window(
        "ActivityWatch",
        ui_url,
        width=width,
        height=height,
        js_api=api,
    )


def main() -> None:
    settings = load_settings()
    setup_logging("aw-pywebview", verbose=True, log_file=True)

    manager = Manager()
    _start_modules(manager, settings["autostart_modules"])
    _wait_until_server_ready(settings)

    width, height = _window_size(settings)
    shutdown_handler = _build_shutdown_handler(manager)
    _register_signal_handlers(shutdown_handler)

    window = _create_window(width, height, settings)
    tray_controller = TrayController(window, shutdown_handler, manager)

    def _install_tray():
        tray_controller.install()

    def _on_minimized():
        tray_controller.hide_window()

    def _on_closing():
        if tray_controller.is_quitting or not tray_controller.is_available:
            return
        tray_controller.hide_window()
        return False

    def _on_closed():
        tray_controller.dispose()
        if not tray_controller.is_quitting:
            shutdown_handler()

    window.events.shown += _install_tray
    window.events.loaded += _install_tray
    window.events.minimized += _on_minimized
    window.events.closing += _on_closing
    window.events.closed += _on_closed
    webview.start(debug=False)


if __name__ == "__main__":
    main()

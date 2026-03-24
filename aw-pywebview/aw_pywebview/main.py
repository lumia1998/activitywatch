import logging
import os
import signal
from pathlib import Path
from typing import Callable, List, Tuple

import webview
from aw_core.config import load_config_toml
from aw_core.log import setup_logging

from .api import AppApi
from .manager import Manager
from .server_info import get_root_url, wait_for_server

logger = logging.getLogger(__name__)


_DEFAULT_CONFIG = """
[aw-pywebview]
autostart_modules = ["aw-server", "aw-watcher-afk", "aw-watcher-window", "aw-watcher-input"]
window_width = 1200
window_height = 800
server_start_timeout = 20
""".strip()


def _load_settings() -> dict:
    config = load_config_toml("aw-pywebview", _DEFAULT_CONFIG)
    return config["aw-pywebview"]


def _start_modules(manager: Manager, autostart_modules: List[str]) -> None:
    # 先启动服务端，再启动 watcher
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


def _create_window(width: int, height: int):
    ui_url = _get_ui_path()
    api = AppApi()
    return webview.create_window(
        "ActivityWatch",
        ui_url,
        width=width,
        height=height,
        js_api=api,
    )


def main() -> None:
    settings = _load_settings()
    setup_logging("aw-pywebview", verbose=True, log_file=True)

    manager = Manager()
    _start_modules(manager, settings["autostart_modules"])
    _wait_until_server_ready(settings)

    width, height = _window_size(settings)
    shutdown_handler = _build_shutdown_handler(manager)
    _register_signal_handlers(shutdown_handler)

    window = _create_window(width, height)

    def _on_closed():
        shutdown_handler()

    window.events.closed += _on_closed
    webview.start(debug=False)


if __name__ == "__main__":
    main()

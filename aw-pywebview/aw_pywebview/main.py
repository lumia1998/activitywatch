import logging
import os
import signal
import threading
from pathlib import Path
from typing import List

import webview
from aw_core.config import load_config_toml
from aw_core.log import setup_logging

from .api import AppApi
from .manager import Manager
from .scheduler import run_report_scheduler_forever
from .server_info import get_root_url, wait_for_server

logger = logging.getLogger(__name__)


_DEFAULT_CONFIG = """
[aw-pywebview]
autostart_modules = ["aw-server", "aw-watcher-afk", "aw-watcher-window"]
window_width = 1200
window_height = 800
server_start_timeout = 20

[aw-pywebview.report]
enabled = false
# 24 小时制
hour = 0
minute = 0
# 统计近 N 天
days = 1
# daily_24h: 昨天 00:00-24:00
# today_so_far: 今天 00:00-现在
mode = "daily_24h"
# 输出目录，留空则使用默认 data 目录
output_dir = ""
""".strip()


def _load_settings() -> dict:
    config = load_config_toml("aw-pywebview", _DEFAULT_CONFIG)
    return config["aw-pywebview"]


def _start_modules(manager: Manager, autostart_modules: List[str]) -> None:
    # 先启动服务端，再启动 watcher
    manager.autostart(autostart_modules)


def _get_ui_path() -> str:
    ui_dir = Path(__file__).parent / "ui"
    return (ui_dir / "index.html").resolve().as_uri()


def main() -> None:
    settings = _load_settings()
    setup_logging("aw-pywebview", verbose=True, log_file=True)

    manager = Manager()
    autostart_modules = settings["autostart_modules"]
    _start_modules(manager, autostart_modules)

    url = get_root_url(testing=False)
    timeout = int(settings.get("server_start_timeout", 20))
    if not wait_for_server(url, timeout=timeout):
        raise RuntimeError("aw-server 启动超时")

    logger.info("Server ready at %s", url)

    scheduler_thread = threading.Thread(
        target=run_report_scheduler_forever, daemon=True
    )
    scheduler_thread.start()

    width = int(settings.get("window_width", 1200))
    height = int(settings.get("window_height", 800))

    def _shutdown(*_args):
        logger.info("Shutdown requested")
        manager.stop_all()
        os._exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    ui_url = _get_ui_path()
    api = AppApi()

    window = webview.create_window(
        "ActivityWatch",
        ui_url,
        width=width,
        height=height,
        js_api=api,
    )

    def _on_closed():
        _shutdown()

    window.events.closed += _on_closed
    webview.start(debug=False)


if __name__ == "__main__":
    main()

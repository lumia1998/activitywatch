import argparse
import sys

from aw_core.config import load_config_toml

default_config = """
[aw-watcher-input]
poll_time = 1.0
include_window_info = false

[aw-watcher-input-testing]
poll_time = 0.2
include_window_info = false
""".strip()


def load_config(testing: bool):
    section = "aw-watcher-input" + ("-testing" if testing else "")
    return load_config_toml("aw-watcher-input", default_config)[section]


def parse_args():
    testing = "--testing" in sys.argv
    config = load_config(testing)

    parser = argparse.ArgumentParser(
        description="A watcher for keyboard and mouse input activity."
    )
    parser.add_argument("--host", dest="host")
    parser.add_argument("--port", dest="port")
    parser.add_argument("--testing", dest="testing", action="store_true")
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="run with verbose logging",
    )
    parser.add_argument(
        "--poll-time", dest="poll_time", type=float, default=config["poll_time"]
    )
    parser.add_argument(
        "--include-window-info",
        dest="include_window_info",
        action="store_true",
        default=bool(config["include_window_info"]),
        help="attach active window app/title information to emitted events",
    )
    return parser.parse_args()

from typing import Dict, List

import tomlkit
from aw_core.config import load_config_toml, save_config_toml

DEFAULT_CONFIG = """
[aw-pywebview]
autostart_modules = ["aw-server", "aw-watcher-afk", "aw-watcher-window", "aw-watcher-input"]
window_width = 1200
window_height = 800
server_start_timeout = 20
excluded_apps = ["desktopMgr64"]

[aw-pywebview.app_aliases]
360FileBrowser64 = "360文件夹"
explorer = "360文件夹"
""".strip()


def _normalize_string_list(values) -> List[str]:
    items: List[str] = []
    if not isinstance(values, list):
        return items
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        if normalized and normalized not in items:
            items.append(normalized)
    return items


def _normalize_aliases(values) -> Dict[str, str]:
    items: Dict[str, str] = {}
    if not isinstance(values, dict):
        return items
    for key, value in values.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        normalized_key = key.strip()
        normalized_value = value.strip()
        if normalized_key and normalized_value:
            items[normalized_key] = normalized_value
    return items


def load_settings() -> dict:
    config = load_config_toml("aw-pywebview", DEFAULT_CONFIG)
    return config["aw-pywebview"]


def get_settings_payload(settings: dict | None = None) -> Dict[str, object]:
    current = settings or load_settings()
    return {
        "excluded_apps": _normalize_string_list(current.get("excluded_apps")),
        "app_aliases": _normalize_aliases(current.get("app_aliases")),
    }


def save_settings_payload(excluded_apps=None, app_aliases=None) -> Dict[str, object]:
    config = load_config_toml("aw-pywebview", DEFAULT_CONFIG)
    section = config["aw-pywebview"]
    section["excluded_apps"] = _normalize_string_list(excluded_apps)
    section["app_aliases"] = _normalize_aliases(app_aliases)
    save_config_toml("aw-pywebview", tomlkit.dumps(config))
    return get_settings_payload(section)

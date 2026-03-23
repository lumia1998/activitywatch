import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-watcher-window"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

import aw_watcher_window.lib as lib_module


def test_get_current_window_windows_emits_stable_app_and_display_name(monkeypatch):
    class FakeWindows:
        @staticmethod
        def get_active_window_handle():
            return 1

        @staticmethod
        def get_app_name(_hwnd):
            return "Visual Studio Code"

        @staticmethod
        def get_process_name(_hwnd):
            return "python"

        @staticmethod
        def get_app_name_wmi(_hwnd):
            return "Visual Studio Code"

        @staticmethod
        def get_process_name_wmi(_hwnd):
            return "python"

        @staticmethod
        def get_window_title(_hwnd):
            return "activitywatch - Visual Studio Code"

    monkeypatch.setitem(sys.modules, "aw_watcher_window.windows", FakeWindows)

    payload = lib_module.get_current_window_windows()

    assert payload == {
        "app": "python",
        "display_name": "Visual Studio Code",
        "title": "activitywatch - Visual Studio Code",
    }

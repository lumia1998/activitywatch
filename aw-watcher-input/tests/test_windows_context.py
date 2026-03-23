import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-watcher-input", "aw-watcher-window"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

MODULE_PATH = ROOT / "aw-watcher-input" / "aw_watcher_input" / "windows.py"
SPEC = spec_from_file_location("aw_watcher_input.windows", MODULE_PATH)
windows_module = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(windows_module)


def test_get_active_window_context_includes_display_name(monkeypatch):
    monkeypatch.setattr(
        windows_module,
        "get_current_window_windows",
        lambda: {
            "app": "python",
            "display_name": "Visual Studio Code",
            "title": "activitywatch - Visual Studio Code",
        },
    )

    assert windows_module.get_active_window_context() == {
        "app": "python",
        "display_name": "Visual Studio Code",
        "title": "activitywatch - Visual Studio Code",
    }

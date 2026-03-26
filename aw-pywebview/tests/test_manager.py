import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-server", "aw-pywebview"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

PACKAGE_ROOT = ROOT / "aw-pywebview" / "aw_pywebview"
package = types.ModuleType("aw_pywebview")
package.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("aw_pywebview", package)

MODULE_PATH = PACKAGE_ROOT / "manager.py"
SPEC = spec_from_file_location("aw_pywebview.manager", MODULE_PATH)
manager_module = module_from_spec(SPEC)
sys.modules["aw_pywebview.manager"] = manager_module
assert SPEC.loader is not None
SPEC.loader.exec_module(manager_module)

Manager = manager_module.Manager
Module = manager_module.Module


def test_autostart_starts_server_before_other_modules(monkeypatch):
    manager = object.__new__(Manager)
    manager.modules = [
        Module("aw-server", Path("/tmp/aw-server"), "source"),
        Module("aw-watcher-window", Path("/tmp/aw-watcher-window"), "source"),
        Module("aw-watcher-input", Path("/tmp/aw-watcher-input"), "source"),
    ]
    manager.testing = False

    calls = []
    monkeypatch.setattr(manager, "start", lambda name: calls.append(name))

    manager.autostart(["aw-watcher-input", "aw-server", "aw-watcher-window"])

    assert calls[0] == "aw-server"
    assert set(calls[1:]) == {"aw-watcher-input", "aw-watcher-window"}




def test_pause_tracking_stops_watchers_and_resume_restarts_them(monkeypatch):
    manager = object.__new__(Manager)
    manager.testing = False
    manager._paused_modules = []

    server = Module("aw-server", Path("/tmp/aw-server"), "source")
    watcher_window = Module("aw-watcher-window", Path("/tmp/aw-watcher-window"), "source")
    watcher_input = Module("aw-watcher-input", Path("/tmp/aw-watcher-input"), "source")
    manager.modules = [server, watcher_window, watcher_input]

    monkeypatch.setattr(server, "is_alive", lambda: True)
    monkeypatch.setattr(watcher_window, "is_alive", lambda: True)
    monkeypatch.setattr(watcher_input, "is_alive", lambda: True)

    stopped = []
    monkeypatch.setattr(server, "stop", lambda: stopped.append("aw-server"))
    monkeypatch.setattr(watcher_window, "stop", lambda: stopped.append("aw-watcher-window"))
    monkeypatch.setattr(watcher_input, "stop", lambda: stopped.append("aw-watcher-input"))

    restarted = []
    monkeypatch.setattr(manager, "start", lambda name: restarted.append(name))

    manager.pause_tracking()

    assert stopped == ["aw-watcher-window", "aw-watcher-input"]
    assert manager._paused_modules == ["aw-watcher-window", "aw-watcher-input"]

    manager.resume_tracking()

    assert restarted == ["aw-watcher-window", "aw-watcher-input"]
    assert manager._paused_modules == []

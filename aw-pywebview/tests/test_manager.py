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


def test_start_prefers_bundled_then_system_then_source(monkeypatch):
    manager = object.__new__(Manager)
    manager.testing = True

    bundled = Module("aw-server", Path("/tmp/bundled-aw-server"), "bundled")
    system = Module("aw-server", Path("/tmp/system-aw-server"), "system")
    source = Module("aw-server", Path("/tmp/source-aw-server"), "source")
    manager.modules = [source, system, bundled]

    started = []
    monkeypatch.setattr(bundled, "start", lambda testing: started.append(("bundled", testing)))
    monkeypatch.setattr(system, "start", lambda testing: started.append(("system", testing)))
    monkeypatch.setattr(source, "start", lambda testing: started.append(("source", testing)))

    manager.start("aw-server")

    assert started == [("bundled", True)]

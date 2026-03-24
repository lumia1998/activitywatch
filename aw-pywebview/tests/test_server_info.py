import sys
import types
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-server", "aw-pywebview"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

requests_module = types.ModuleType("requests")
requests_module.get = lambda *args, **kwargs: None
sys.modules.setdefault("requests", requests_module)

aw_server_package = types.ModuleType("aw_server")
aw_server_package.__path__ = []
sys.modules.setdefault("aw_server", aw_server_package)

aw_server_config_module = types.ModuleType("aw_server.config")
aw_server_config_module.config = {
    "server": {"host": "127.0.0.1", "port": 5600},
    "server-testing": {"host": "127.0.0.1", "port": 5666},
}
sys.modules.setdefault("aw_server.config", aw_server_config_module)

PACKAGE_ROOT = ROOT / "aw-pywebview" / "aw_pywebview"
package = types.ModuleType("aw_pywebview")
package.__path__ = [str(PACKAGE_ROOT)]
sys.modules.setdefault("aw_pywebview", package)

MODULE_PATH = PACKAGE_ROOT / "server_info.py"
SPEC = spec_from_file_location("aw_pywebview.server_info", MODULE_PATH)
server_info_module = module_from_spec(SPEC)
sys.modules["aw_pywebview.server_info"] = server_info_module
assert SPEC.loader is not None
SPEC.loader.exec_module(server_info_module)

wait_for_server = server_info_module.wait_for_server


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


def test_wait_for_server_returns_true_after_retry(monkeypatch):
    calls = {"count": 0}
    timeline = iter([0.0, 0.2, 0.7])

    def fake_get(url, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("booting")
        return FakeResponse(200)

    monkeypatch.setattr(server_info_module.requests, "get", fake_get)
    monkeypatch.setattr(server_info_module.time, "time", lambda: next(timeline))
    monkeypatch.setattr(server_info_module.time, "sleep", lambda seconds: None)

    assert wait_for_server("http://127.0.0.1:5600", timeout=2) is True
    assert calls["count"] == 2


def test_wait_for_server_times_out_when_server_never_ready(monkeypatch):
    timeline = iter([0.0, 0.3, 0.9, 1.2])

    monkeypatch.setattr(server_info_module.requests, "get", lambda url, timeout: FakeResponse(503))
    monkeypatch.setattr(server_info_module.time, "time", lambda: next(timeline))
    monkeypatch.setattr(server_info_module.time, "sleep", lambda seconds: None)

    assert wait_for_server("http://127.0.0.1:5600", timeout=1) is False

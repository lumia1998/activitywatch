import sys
import types
from datetime import datetime, timedelta
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

MODULE_PATH = PACKAGE_ROOT / "api.py"
SPEC = spec_from_file_location("aw_pywebview.api", MODULE_PATH)
api_module = module_from_spec(SPEC)
sys.modules["aw_pywebview.api"] = api_module
assert SPEC.loader is not None
SPEC.loader.exec_module(api_module)

AppApi = api_module.AppApi


class FakeClient:
    client_hostname = "testhost"


class TrackingApi(AppApi):
    def __init__(self):
        super().__init__()
        self.client = FakeClient()

    def _get_client(self):
        return self.client


def test_get_dashboard_data_returns_unified_payload(monkeypatch):
    api = TrackingApi()
    calls = {}
    summary = {"time_range": {"start": "2026-03-20", "end": "2026-03-21"}, "result": {}}
    payload = {
        "summary": summary,
        "activity": [{"app": "Editor", "duration": 1}],
        "timeline": [{"start": "s", "end": "e"}],
        "inputTopApps": [{"app": "Editor", "presses": 1, "clicks": 2, "scroll": 3}],
        "inputSummary": {"available": True, "totals": {"presses": 1, "clicks": 2, "scroll": 3, "moves": 4, "total": 6}},
        "inputTrend": [{"hour": 9, "presses": 1, "clicks": 2, "scroll": 3, "moves": 4, "total": 6}],
        "inputByApp": [{"app": "Editor", "presses": 1, "clicks": 2, "scroll": 3, "moves": 4, "total": 6}],
        "visualization": {"hourlyBars": [], "gantt": {"lanes": []}, "heatmap": {"apps": []}},
    }

    def fake_build_summary_range(start, end, client):
        calls["summary"] = (start, end, client)
        return summary

    def fake_build_dashboard_payload(**kwargs):
        calls["payload"] = kwargs
        return payload

    monkeypatch.setattr(api_module, "build_summary_range", fake_build_summary_range)
    monkeypatch.setattr(api_module, "build_dashboard_payload", fake_build_dashboard_payload)

    result = api.get_dashboard_data(days=3, activity_limit=7, timeline_limit=8, top_n_apps=9)

    assert result == {
        "ok": True,
        "error": None,
        **payload,
        "warnings": [],
    }
    assert calls["summary"][2] is api.client
    assert calls["payload"]["summary"] is summary
    assert calls["payload"]["client"] is api.client
    assert calls["payload"]["activity_limit"] == 7
    assert calls["payload"]["timeline_limit"] == 8
    assert calls["payload"]["top_n_apps"] == 9
    assert isinstance(calls["payload"]["start"], datetime)
    assert isinstance(calls["payload"]["end"], datetime)
    assert calls["payload"]["end"] - calls["payload"]["start"] >= timedelta(days=2, hours=23)


def test_get_dashboard_data_returns_missing_bucket_error(monkeypatch):
    api = TrackingApi()

    monkeypatch.setattr(api_module, "build_summary_range", lambda start, end, client: {"error": "Missing buckets"})

    result = api.get_dashboard_data()

    assert result["ok"] is False
    assert result["error"]["code"] == "missing_buckets"
    assert result["summary"] is None
    assert result["visualization"] is None


def test_get_dashboard_data_returns_query_failed_when_payload_build_crashes(monkeypatch):
    api = TrackingApi()
    summary = {"time_range": {"start": "2026-03-20", "end": "2026-03-21"}, "result": {}}

    monkeypatch.setattr(api_module, "build_summary_range", lambda start, end, client: summary)
    monkeypatch.setattr(api_module, "build_dashboard_payload", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    result = api.get_dashboard_data()

    assert result["ok"] is False
    assert result["error"]["code"] == "query_failed"
    assert "boom" in result["error"]["details"]

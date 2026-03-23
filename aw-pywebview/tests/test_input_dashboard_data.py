import sys
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-server", "aw-pywebview"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

MODULE_PATH = Path(__file__).resolve().parents[1] / "aw_pywebview" / "data.py"
SPEC = spec_from_file_location("aw_pywebview_data", MODULE_PATH)
data_module = module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(data_module)

build_activity_from_summary = data_module.build_activity_from_summary
build_activity_with_input = data_module.build_activity_with_input
build_input_stats_full = data_module.build_input_stats_full
build_input_trend = data_module.build_input_trend
build_input_by_app = data_module.build_input_by_app
build_dashboard_payload = data_module.build_dashboard_payload


class FakeEvent:
    def __init__(self, timestamp: str, data: dict):
        self.timestamp = datetime.fromisoformat(timestamp)
        self.data = data


class FakeClient:
    client_hostname = "testhost"

    def __init__(self, events):
        self.events = events

    def get_buckets(self):
        return {"aw-watcher-input_testhost": {}}

    def get_events(self, bucket, start, end):
        assert bucket == "aw-watcher-input_testhost"
        return self.events


def _summary():
    return {
        "time_range": {
            "start": "2026-03-20T09:00:00+08:00",
            "end": "2026-03-20T12:00:00+08:00",
        },
        "result": {
            "window": {
                "app_events": [
                    {
                        "duration": 3600,
                        "data": {"app": "python", "display_name": "Visual Studio Code", "title": "activitywatch - Visual Studio Code"},
                    },
                    {
                        "duration": 2400,
                        "data": {"app": "msedgewebview2", "title": "Widget Runtime - Microsoft Edge WebView2"},
                    },
                ]
            },
            "events": [
                {
                    "timestamp": "2026-03-20T09:00:00+08:00",
                    "duration": 3600,
                    "data": {"app": "python", "display_name": "Visual Studio Code", "$category": ["work"], "title": "activitywatch - Visual Studio Code"},
                },
                {
                    "timestamp": "2026-03-20T10:00:00+08:00",
                    "duration": 3600,
                    "data": {"app": "msedgewebview2", "$category": ["research"], "title": "Widget Runtime - Microsoft Edge WebView2"},
                },
            ]
        },
    }


def test_build_activity_from_summary_prefers_display_name():
    result = build_activity_from_summary(_summary(), limit=10)

    assert result == [
        {
            "app": "python",
            "display_name": "Visual Studio Code",
            "title": "activitywatch - Visual Studio Code",
            "duration": 3600,
        },
        {
            "app": "msedgewebview2",
            "display_name": "Microsoft Edge WebView2",
            "title": "Widget Runtime - Microsoft Edge WebView2",
            "duration": 2400,
        },
    ]


def test_build_activity_with_input_merges_stats_without_changing_order():
    client = FakeClient(
        [
            FakeEvent("2026-03-20T09:10:00+08:00", {"presses": 10, "clicks": 2, "scrollX": 0, "scrollY": 3, "deltaX": 0, "deltaY": 0}),
            FakeEvent("2026-03-20T10:20:00+08:00", {"presses": 5, "clicks": 1, "scrollX": 0, "scrollY": 2, "deltaX": 0, "deltaY": 0}),
        ]
    )

    result = build_activity_with_input(
        summary=_summary(),
        start=datetime.fromisoformat("2026-03-20T09:00:00+08:00"),
        end=datetime.fromisoformat("2026-03-20T12:00:00+08:00"),
        limit=10,
        client=client,
    )

    assert result[0]["app"] == "python"
    assert result[0]["display_name"] == "Visual Studio Code"
    assert result[0]["presses"] == 10
    assert result[0]["clicks"] == 2
    assert result[0]["scroll"] == 3
    assert result[1]["app"] == "msedgewebview2"
    assert result[1]["display_name"] == "Microsoft Edge WebView2"
    assert result[1]["presses"] == 5
    assert result[1]["clicks"] == 1
    assert result[1]["scroll"] == 2


def test_build_input_stats_full_summarizes_all_metrics():
    client = FakeClient(
        [
            FakeEvent("2026-03-20T09:10:00+08:00", {"presses": 10, "clicks": 2, "scrollX": 0, "scrollY": 3, "deltaX": 4, "deltaY": 5}),
            FakeEvent("2026-03-20T10:20:00+08:00", {"presses": 5, "clicks": 1, "scrollX": 0, "scrollY": 2, "deltaX": 1, "deltaY": 1}),
        ]
    )

    result = build_input_stats_full(
        datetime.fromisoformat("2026-03-20T09:00:00+08:00"),
        datetime.fromisoformat("2026-03-20T12:00:00+08:00"),
        client=client,
    )

    assert result["available"] is True
    assert result["totals"] == {
        "presses": 15,
        "clicks": 3,
        "scroll": 5,
        "moves": 11,
        "total": 23,
    }
    assert result["peakHour"] == {"hour": 9, "total": 15}


def test_build_input_by_app_assigns_events_to_active_window_ranges():
    client = FakeClient(
        [
            FakeEvent("2026-03-20T09:10:00+08:00", {"presses": 10, "clicks": 2, "scrollX": 0, "scrollY": 3, "deltaX": 0, "deltaY": 0}),
            FakeEvent("2026-03-20T10:20:00+08:00", {"presses": 5, "clicks": 1, "scrollX": 0, "scrollY": 2, "deltaX": 0, "deltaY": 0}),
        ]
    )

    result = build_input_by_app(
        summary=_summary(),
        start=datetime.fromisoformat("2026-03-20T09:00:00+08:00"),
        end=datetime.fromisoformat("2026-03-20T12:00:00+08:00"),
        top_n=6,
        client=client,
    )

    assert result == [
        {"app": "python", "display_name": "Visual Studio Code", "presses": 10, "clicks": 2, "scroll": 3, "moves": 0, "total": 15},
        {"app": "msedgewebview2", "display_name": "Microsoft Edge WebView2", "presses": 5, "clicks": 1, "scroll": 2, "moves": 0, "total": 8},
    ]


def test_build_input_trend_groups_metrics_by_hour():
    client = FakeClient(
        [
            FakeEvent("2026-03-20T09:10:00+08:00", {"presses": 10, "clicks": 2, "scrollX": 0, "scrollY": 3, "deltaX": 4, "deltaY": 5}),
            FakeEvent("2026-03-20T10:20:00+08:00", {"presses": 5, "clicks": 1, "scrollX": 0, "scrollY": 2, "deltaX": 1, "deltaY": 1}),
        ]
    )

    result = build_input_trend(
        datetime.fromisoformat("2026-03-20T09:00:00+08:00"),
        datetime.fromisoformat("2026-03-20T12:00:00+08:00"),
        client=client,
    )

    assert result[9] == {"hour": 9, "presses": 10, "clicks": 2, "scroll": 3, "moves": 9, "total": 15}
    assert result[10] == {"hour": 10, "presses": 5, "clicks": 1, "scroll": 2, "moves": 2, "total": 8}
    assert result[11] == {"hour": 11, "presses": 0, "clicks": 0, "scroll": 0, "moves": 0, "total": 0}


def test_build_dashboard_payload_includes_full_input_sections():
    client = FakeClient(
        [
            FakeEvent("2026-03-20T09:10:00+08:00", {"presses": 10, "clicks": 2, "scrollX": 0, "scrollY": 3, "deltaX": 4, "deltaY": 5}),
        ]
    )

    payload = build_dashboard_payload(
        summary=_summary(),
        start=datetime.fromisoformat("2026-03-20T09:00:00+08:00"),
        end=datetime.fromisoformat("2026-03-20T12:00:00+08:00"),
        client=client,
    )

    assert payload["activity"][0]["display_name"] == "Visual Studio Code"
    assert payload["activity"][0]["presses"] == 10
    assert payload["inputSummary"]["available"] is True
    assert payload["inputSummary"]["totals"]["presses"] == 10
    assert payload["inputTrend"][9]["total"] == 15


def test_build_input_stats_prefers_activitywatch_bucket_over_keystats_fallback(monkeypatch):
    client = FakeClient(
        [
            FakeEvent("2026-03-23T09:10:00+08:00", {"presses": 7, "clicks": 2, "scrollX": 1, "scrollY": 3, "deltaX": 4, "deltaY": 6}),
        ]
    )

    monkeypatch.setattr(
        data_module,
        "_resolve_key_stats_day_payload",
        lambda start, end: {
            "date": "2026-03-23T00:00:00+08:00",
            "keyPresses": 999,
            "leftClicks": 999,
            "rightClicks": 0,
            "middleClicks": 0,
            "sideBackClicks": 0,
            "sideForwardClicks": 0,
            "scrollDistance": 999,
            "mouseDistance": 999,
            "appStats": {},
        },
    )

    start = datetime.fromisoformat("2026-03-23T00:00:00+08:00")
    end = datetime.fromisoformat("2026-03-23T23:59:59+08:00")
    summary = build_input_stats_full(start, end, client=client)

    assert summary["source"] == "activitywatch"
    assert summary["totals"] == {
        "presses": 7,
        "clicks": 2,
        "scroll": 4,
        "moves": 10,
        "total": 13,
    }


def test_build_input_stats_falls_back_to_keystats_json(monkeypatch):
    day_payload = {
        "date": "2026-03-23T00:00:00+08:00",
        "keyPresses": 120,
        "leftClicks": 10,
        "rightClicks": 5,
        "middleClicks": 1,
        "sideBackClicks": 0,
        "sideForwardClicks": 0,
        "scrollDistance": 40,
        "mouseDistance": 500,
        "appStats": {
            "python": {
                "AppName": "python",
                "DisplayName": "ActivityWatch",
                "KeyPresses": 100,
                "LeftClicks": 4,
                "RightClicks": 1,
                "MiddleClicks": 0,
                "SideBackClicks": 0,
                "SideForwardClicks": 0,
                "ScrollDistance": 20,
            },
            "QQ": {
                "AppName": "QQ",
                "DisplayName": "QQ",
                "KeyPresses": 20,
                "LeftClicks": 6,
                "RightClicks": 4,
                "MiddleClicks": 1,
                "SideBackClicks": 0,
                "SideForwardClicks": 0,
                "ScrollDistance": 20,
            },
        },
    }

    monkeypatch.setattr(data_module, "_load_input_events", lambda start, end, client=None: None)
    monkeypatch.setattr(data_module, "_resolve_key_stats_day_payload", lambda start, end: day_payload)

    start = datetime.fromisoformat("2026-03-23T00:00:00+08:00")
    end = datetime.fromisoformat("2026-03-23T23:59:59+08:00")

    summary = build_input_stats_full(start, end)
    trend = build_input_trend(start, end)
    by_app = build_input_by_app(summary=_summary(), start=start, end=end)

    assert summary["available"] is True
    assert summary["source"] == "keystats"
    assert summary["totals"] == {
        "presses": 120,
        "clicks": 16,
        "scroll": 40,
        "moves": 500,
        "total": 176,
    }
    assert trend[12]["total"] == 176
    assert by_app[0]["app"] == "python"
    assert by_app[0]["display_name"] == "ActivityWatch"
    assert by_app[0]["total"] == 125

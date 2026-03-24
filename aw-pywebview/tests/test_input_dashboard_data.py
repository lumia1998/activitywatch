import sys
import types
from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-server", "aw-pywebview"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

aw_client_module = types.ModuleType("aw_client")
aw_client_module.ActivityWatchClient = object
sys.modules.setdefault("aw_client", aw_client_module)

queries_module = types.ModuleType("aw_client.queries")
queries_module.DesktopQueryParams = lambda **kwargs: kwargs
queries_module.fullDesktopQuery = lambda params: params
sys.modules.setdefault("aw_client.queries", queries_module)

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
build_browser_by_domain = data_module.build_browser_by_domain
build_browser_summary = data_module.build_browser_summary
build_browser_trend = data_module.build_browser_trend


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
            "browser": {
                "duration": 4800,
                "domains": [
                    {
                        "duration": 3000,
                        "data": {"$domain": "github.com"},
                    },
                    {
                        "duration": 1800,
                        "data": {"$domain": "bilibili.com"},
                    },
                ],
                "urls": [
                    {
                        "duration": 1800,
                        "data": {"url": "https://github.com/ActivityWatch/activitywatch"},
                    },
                    {
                        "duration": 1200,
                        "data": {"url": "https://github.com/ActivityWatch/aw-webui"},
                    },
                    {
                        "duration": 1800,
                        "data": {"url": "https://www.bilibili.com/video/BV1xx"},
                    },
                ],
                "events": [
                    {
                        "timestamp": "2026-03-20T09:10:00+08:00",
                        "duration": 1800,
                        "data": {"$domain": "github.com", "url": "https://github.com/ActivityWatch/activitywatch"},
                    },
                    {
                        "timestamp": "2026-03-20T10:15:00+08:00",
                        "duration": 1200,
                        "data": {"$domain": "github.com", "url": "https://github.com/ActivityWatch/aw-webui"},
                    },
                    {
                        "timestamp": "2026-03-20T11:00:00+08:00",
                        "duration": 1800,
                        "data": {"$domain": "bilibili.com", "url": "https://www.bilibili.com/video/BV1xx"},
                    },
                ],
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


def _summary_without_browser_data():
    summary = _summary()
    summary["result"]["browser"] = {
        "duration": 0,
        "domains": [],
        "urls": [],
        "events": [],
    }
    return summary


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




def test_build_input_trend_projects_utc_event_hours_into_requested_timezone():
    client = FakeClient(
        [
            FakeEvent("2026-03-20T01:10:00+00:00", {"presses": 10, "clicks": 2, "scrollX": 0, "scrollY": 3, "deltaX": 4, "deltaY": 5}),
            FakeEvent("2026-03-20T02:20:00+00:00", {"presses": 5, "clicks": 1, "scrollX": 0, "scrollY": 2, "deltaX": 1, "deltaY": 1}),
        ]
    )

    result = build_input_trend(
        datetime.fromisoformat("2026-03-20T09:00:00+08:00"),
        datetime.fromisoformat("2026-03-20T12:00:00+08:00"),
        client=client,
    )

    assert result[9] == {"hour": 9, "presses": 10, "clicks": 2, "scroll": 3, "moves": 9, "total": 15}
    assert result[10] == {"hour": 10, "presses": 5, "clicks": 1, "scroll": 2, "moves": 2, "total": 8}
    assert result[1] == {"hour": 1, "presses": 0, "clicks": 0, "scroll": 0, "moves": 0, "total": 0}




def test_build_dashboard_payload_includes_full_input_and_browser_sections():
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
    assert payload["browserSummary"]["available"] is True
    assert payload["browserByDomain"][0]["domain"] == "github.com"
    assert payload["browserTrend"]["hourlyBars"][9]["total"] == 1800.0


def test_build_browser_by_domain_aggregates_domain_duration_and_url_count():
    result = build_browser_by_domain(_summary(), limit=10)

    assert result == [
        {"domain": "github.com", "duration": 3000.0, "share": 3000 / 4800, "urlCount": 2},
        {"domain": "bilibili.com", "duration": 1800.0, "share": 1800 / 4800, "urlCount": 1},
    ]




def test_build_dashboard_payload_preserves_contract_keys_and_shapes():
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

    assert set(payload.keys()) == {
        "summary",
        "activity",
        "timeline",
        "inputTopApps",
        "inputSummary",
        "inputTrend",
        "inputByApp",
        "browserSummary",
        "browserByDomain",
        "browserTrend",
        "visualization",
    }
    assert isinstance(payload["activity"], list)
    assert isinstance(payload["timeline"], list)
    assert isinstance(payload["inputTopApps"], list)
    assert isinstance(payload["inputTrend"], list)
    assert isinstance(payload["inputByApp"], list)
    assert isinstance(payload["browserByDomain"], list)
    assert isinstance(payload["browserTrend"], dict)
    assert isinstance(payload["visualization"], dict)


def test_build_browser_summary_returns_top_domain_and_totals():
    summary = build_browser_summary(_summary())

    assert summary["available"] is True
    assert summary["totalDuration"] == 4800
    assert summary["domainCount"] == 2
    assert summary["urlCount"] == 3
    assert summary["topDomain"] == {
        "domain": "github.com",
        "duration": 3000.0,
        "share": 3000 / 4800,
    }
    trend = build_browser_trend(_summary(), top_n_domains=4)

    assert trend["activeHour"] == 9
    assert trend["meta"]["days"] == 1
    assert trend["hourlyBars"][9] == {
        "hour": 9,
        "total": 1800.0,
        "segments": [
            {"domain": "github.com", "duration": 1800.0, "color": trend["colorMap"]["github.com"]},
        ],
    }
    assert trend["hourlyBars"][10] == {
        "hour": 10,
        "total": 1200.0,
        "segments": [
            {"domain": "github.com", "duration": 1200.0, "color": trend["colorMap"]["github.com"]},
        ],
    }
    assert trend["hourlyBars"][11] == {
        "hour": 11,
        "total": 1800.0,
        "segments": [
            {"domain": "bilibili.com", "duration": 1800.0, "color": trend["colorMap"]["bilibili.com"]},
        ],
    }


def test_build_browser_trend_projects_utc_hours_into_summary_timezone():
    summary = _summary()
    summary["result"]["browser"]["events"] = [
        {
            "timestamp": "2026-03-20T01:10:00+00:00",
            "duration": 1800,
            "data": {"$domain": "github.com", "url": "https://github.com/ActivityWatch/activitywatch"},
        },
        {
            "timestamp": "2026-03-20T03:00:00+00:00",
            "duration": 1800,
            "data": {"$domain": "bilibili.com", "url": "https://www.bilibili.com/video/BV1xx"},
        },
    ]

    trend = build_browser_trend(summary, top_n_domains=4)

    assert trend["hourlyBars"][9]["total"] == 1800.0
    assert trend["hourlyBars"][11]["total"] == 1800.0
    assert trend["hourlyBars"][1]["total"] == 0.0


def test_build_browser_helpers_return_empty_state_without_browser_data(monkeypatch):
    summary = _summary_without_browser_data()

    assert build_browser_by_domain(summary) == []
    assert build_browser_summary(summary) == {
        "available": False,
        "totalDuration": 0.0,
        "domainCount": 0,
        "urlCount": 0,
        "topDomain": None,
    }
    trend = build_browser_trend(summary)
    assert trend["activeHour"] is None
    assert all(item == {"hour": item["hour"], "total": 0.0, "segments": []} for item in trend["hourlyBars"])

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

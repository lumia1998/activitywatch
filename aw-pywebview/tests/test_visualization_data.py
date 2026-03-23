import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime

from pytest import approx

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

build_summary_range = data_module.build_summary_range
build_visualization_data = data_module.build_visualization_data
get_consistent_color_mapping = data_module.get_consistent_color_mapping


def _summary(events):
    return {
        "time_range": {
            "start": "2026-03-20T00:00:00+08:00",
            "end": "2026-03-22T00:00:00+08:00",
        },
        "result": {
            "events": events,
        },
    }


def _event(timestamp, duration, app, category, title=""):
    return {
        "timestamp": timestamp,
        "duration": duration,
        "data": {
            "app": app,
            "$category": category,
            "title": title,
        },
    }


def test_build_summary_range_does_not_crash_when_classes_setting_is_null(monkeypatch):
    captured = {}

    def fake_full_desktop_query(params):
        captured["params"] = params
        return "RETURN = {};"

    class FakeClient:
        client_hostname = "testhost"

        def get_buckets(self):
            return {
                "aw-watcher-window_testhost": {},
                "aw-watcher-afk_testhost": {},
            }

        def query(self, query, timeperiods):
            captured["query"] = query
            captured["timeperiods"] = timeperiods
            return [{"events": []}]

    monkeypatch.setattr(data_module, "fullDesktopQuery", fake_full_desktop_query)
    monkeypatch.setattr(
        data_module,
        "DesktopQueryParams",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    summary = build_summary_range(
        datetime.fromisoformat("2026-03-20T00:00:00+08:00"),
        datetime.fromisoformat("2026-03-20T01:00:00+08:00"),
        client=FakeClient(),
    )

    assert summary == {
        "time_range": {
            "start": "2026-03-20T00:00:00+08:00",
            "end": "2026-03-20T01:00:00+08:00",
        },
        "result": {"events": []},
    }
    assert captured["params"].bid_window == "aw-watcher-window_testhost"
    assert captured["params"].bid_afk == "aw-watcher-afk_testhost"
    assert captured["params"].bid_browsers == []
    assert captured["query"] == "RETURN = {};"
    assert len(captured["timeperiods"]) == 1


def test_build_visualization_data_splits_across_hours_and_filters_short_events():
    summary = _summary(
        [
            _event("2026-03-20T09:50:00+08:00", 1200, "Editor", ["work"], "Deep work"),
            _event("2026-03-20T10:15:00+08:00", 1.5, "Chat", ["social"], "Ping"),
            _event("2026-03-20T10:25:00+08:00", 600, "Browser", ["research"], "Docs"),
            _event("2026-03-21T09:10:00+08:00", 1800, "Editor", ["work"], "Review"),
        ]
    )

    data = build_visualization_data(summary, min_duration=2, top_n_apps=5)

    hourly = {item["hour"]: item for item in data["hourlyBars"]}
    assert len(data["hourlyBars"]) == 24
    assert hourly[9]["total"] == 2400
    assert hourly[10]["total"] == 1200
    assert hourly[9]["segments"] == [{"app": "Editor", "duration": 2400, "color": data["colorMap"]["Editor"]}]
    assert hourly[10]["segments"] == [
        {"app": "Browser", "duration": 600, "color": data["colorMap"]["Browser"]},
        {"app": "Editor", "duration": 600, "color": data["colorMap"]["Editor"]},
    ]

    lanes = {lane["app"]: lane for lane in data["gantt"]["lanes"]}
    assert set(lanes) == {"Editor", "Browser"}
    editor_blocks = lanes["Editor"]["blocks"]
    assert len(editor_blocks) == 2
    assert editor_blocks[0]["start"] == approx(9 + 10 / 60)
    assert editor_blocks[0]["end"] == approx(9 + 40 / 60)
    assert editor_blocks[0]["duration"] == approx(1800)
    assert editor_blocks[1]["start"] == approx(9 + 50 / 60)
    assert editor_blocks[1]["end"] == approx(10 + 10 / 60)
    assert editor_blocks[1]["duration"] == approx(1200)

    heatmap = {row["app"]: row for row in data["heatmap"]["apps"]}
    assert heatmap["Editor"]["hours"][9] == 2400
    assert heatmap["Editor"]["hours"][10] == 600
    assert heatmap["Browser"]["hours"][10] == 600
    assert all(value == 0 for idx, value in enumerate(heatmap["Browser"]["hours"]) if idx != 10)



def test_gantt_projection_keeps_same_named_blocks_from_different_days_separate():
    summary = _summary(
        [
            _event("2026-03-20T09:00:00+08:00", 1800, "Editor", ["work"], "Standup"),
            _event("2026-03-21T09:00:00+08:00", 2700, "Editor", ["work"], "Standup"),
        ]
    )

    data = build_visualization_data(summary, min_duration=2, top_n_apps=5)

    lanes = {lane["app"]: lane for lane in data["gantt"]["lanes"]}
    editor_blocks = lanes["Editor"]["blocks"]

    assert len(editor_blocks) == 2
    assert [block["title"] for block in editor_blocks] == ["Standup", "Standup"]
    assert editor_blocks[0]["start"] == approx(9)
    assert editor_blocks[0]["end"] == approx(9.5)
    assert editor_blocks[0]["duration"] == approx(1800)
    assert editor_blocks[1]["start"] == approx(9)
    assert editor_blocks[1]["end"] == approx(9.75)
    assert editor_blocks[1]["duration"] == approx(2700)


def test_color_mapping_is_stable_and_meta_projects_multi_day_to_single_day():
    summary = _summary(
        [
            _event("2026-03-20T08:00:00+08:00", 600, "Mail", ["communication"], "Inbox"),
            _event("2026-03-21T08:30:00+08:00", 900, "Mail", ["communication"], "Reply"),
            _event("2026-03-21T11:00:00+08:00", 1200, "IDE", ["work"], "Coding"),
        ]
    )

    data = build_visualization_data(summary, min_duration=2, top_n_apps=10)
    color_map = get_consistent_color_mapping(summary)

    assert color_map == data["colorMap"]
    assert color_map["Mail"] == get_consistent_color_mapping(summary)["Mail"]
    assert color_map["IDE"] == get_consistent_color_mapping(summary)["IDE"]
    assert data["meta"]["days"] == 2
    assert data["meta"]["projectedToSingleDay"] is True
    assert data["activeHour"] == 8

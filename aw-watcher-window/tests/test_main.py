import sys
import types
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-watcher-window"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

sys.modules.setdefault("aw_client", types.SimpleNamespace(ActivityWatchClient=object))
sys.modules.setdefault("aw_core.log", types.SimpleNamespace(setup_logging=lambda **kwargs: None))
sys.modules.setdefault(
    "aw_core.models",
    types.SimpleNamespace(Event=lambda timestamp, data: types.SimpleNamespace(timestamp=timestamp, data=data)),
)

main_module = import_module("aw_watcher_window.main")


class FakeClient:
    def __init__(self):
        self.calls = []

    def heartbeat(self, bucket_id, event, pulsetime, queued):
        self.calls.append((bucket_id, event, pulsetime, queued))


def test_should_emit_window_requires_three_seconds_by_default():
    assert main_module._should_emit_window(2.0) is False
    assert main_module._should_emit_window(3.0) is True



def test_next_stable_duration_accumulates_only_for_same_window():
    window_a = {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"}
    window_b = {"app": "python", "title": "B", "display_name": "Visual Studio Code", "process_name": "python"}

    assert main_module._next_stable_duration(window_a, None, 0.0, 1.0) == 1.0
    assert main_module._next_stable_duration(window_a, dict(window_a), 1.0, 1.0) == 2.0
    assert main_module._next_stable_duration(window_b, dict(window_a), 2.0, 1.0) == 1.0



def test_heartbeat_loop_emits_only_after_three_seconds_of_stable_focus(monkeypatch):
    windows = iter(
        [
            {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"},
            {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"},
            {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"},
        ]
    )
    parent_pids = iter([123, 123, 123, 1])
    client = FakeClient()

    monkeypatch.setattr(main_module.os, "getppid", lambda: next(parent_pids))
    monkeypatch.setattr(main_module, "get_current_window", lambda _strategy: next(windows))
    monkeypatch.setattr(main_module, "sleep", lambda _seconds: None)

    main_module.heartbeat_loop(client, "bucket", poll_time=1.0, strategy=None)

    assert len(client.calls) == 1
    bucket_id, event, pulsetime, queued = client.calls[0]
    assert bucket_id == "bucket"
    assert event.data["title"] == "A"
    assert pulsetime == 2.0
    assert queued is True



def test_heartbeat_loop_resets_stability_after_missing_window(monkeypatch):
    windows = iter(
        [
            {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"},
            None,
            {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"},
            {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"},
            {"app": "python", "title": "A", "display_name": "Visual Studio Code", "process_name": "python"},
        ]
    )
    parent_pids = iter([123, 123, 123, 123, 123, 1])
    client = FakeClient()

    monkeypatch.setattr(main_module.os, "getppid", lambda: next(parent_pids))
    monkeypatch.setattr(main_module, "get_current_window", lambda _strategy: next(windows))
    monkeypatch.setattr(main_module, "sleep", lambda _seconds: None)

    main_module.heartbeat_loop(client, "bucket", poll_time=1.0, strategy=None)

    assert len(client.calls) == 1
    assert client.calls[0][1].data["title"] == "A"

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
for rel in ["aw-client", "aw-core", "aw-watcher-afk", "aw-watcher-window", "aw-watcher-input"]:
    path = str(ROOT / rel)
    if path not in sys.path:
        sys.path.insert(0, path)

from aw_watcher_input.main import InputWatcher, _merge_input_payloads
from aw_watcher_input.windows import (
    MAX_SEGMENT_DISTANCE,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_SYSKEYDOWN,
    WM_SYSKEYUP,
    WindowsHookInputSource,
)


class FakeSource:
    def __init__(self, payload=None):
        self.payload = payload
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def has_new_event(self):
        return self.payload is not None

    def next_event(self):
        payload = self.payload
        self.payload = None
        return payload


class FakeClient:
    client_name = "aw-watcher-input"
    client_hostname = "testhost"

    def __init__(self):
        self.waited = False
        self.created = []
        self.inserted = []

    def wait_for_start(self):
        self.waited = True

    def create_bucket(self, bucket_id, event_type, queued=False):
        self.created.append((bucket_id, event_type, queued))

    def insert_event(self, bucket_id, event):
        self.inserted.append((bucket_id, event))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_merge_input_payloads_combines_known_fields_only():
    merged = _merge_input_payloads(
        {"presses": 2, "clicks": 1, "scrollY": 3, "unexpected": 9},
        {"clicks": 4, "deltaX": 5, "deltaY": 6},
    )

    assert merged == {
        "presses": 2,
        "clicks": 5,
        "scrollX": 0,
        "scrollY": 3,
        "deltaX": 5,
        "deltaY": 6,
    }


def test_run_once_emits_input_event_with_context():
    client = FakeClient()
    args = SimpleNamespace(
        poll_time=1.0,
        host=None,
        port=None,
        testing=True,
        include_window_info=False,
    )
    watcher = InputWatcher(
        args,
        client=client,
        input_source=FakeSource({"presses": 3, "clicks": 2, "scrollY": 4, "deltaX": 5, "deltaY": 6}),
        context_provider=lambda: {"app": "Editor", "title": "Coding"},
    )

    emitted = watcher.run_once(now=datetime(2026, 3, 23, tzinfo=timezone.utc))

    assert emitted is True
    assert len(client.inserted) == 1
    bucket_id, event = client.inserted[0]
    assert bucket_id == "aw-watcher-input_testhost"
    assert event.data == {
        "presses": 3,
        "clicks": 2,
        "scrollY": 4,
        "deltaX": 5,
        "deltaY": 6,
        "app": "Editor",
        "title": "Coding",
    }
    assert event.duration.total_seconds() == 1.0


def test_run_once_skips_empty_payload():
    client = FakeClient()
    args = SimpleNamespace(
        poll_time=1.0,
        host=None,
        port=None,
        testing=True,
        include_window_info=False,
    )
    watcher = InputWatcher(
        args,
        client=client,
        input_source=FakeSource(None),
    )

    emitted = watcher.run_once()

    assert emitted is False
    assert client.inserted == []


def test_windows_hook_source_deduplicates_key_repeats():
    source = WindowsHookInputSource()

    source.handle_key_message(WM_KEYDOWN, 65)
    source.handle_key_message(WM_KEYDOWN, 65)
    source.handle_key_message(WM_SYSKEYDOWN, 65)
    source.handle_key_message(WM_KEYUP, 65)
    source.handle_key_message(WM_SYSKEYUP, 65)
    source.handle_key_message(WM_KEYDOWN, 65)

    payload = source.next_event()
    assert payload["presses"] == 2


def test_windows_hook_source_accumulates_mouse_stats():
    source = WindowsHookInputSource()

    source.handle_mouse_click()
    source.handle_mouse_scroll(240)
    source.handle_mouse_scroll(-120, horizontal=True)
    source.handle_mouse_move(10, 10)
    source.handle_mouse_move(16, 19)

    payload = source.next_event()
    assert payload["clicks"] == 1
    assert payload["scrollY"] == 2
    assert payload["scrollX"] == 1
    assert payload["deltaX"] == 6
    assert payload["deltaY"] == 9


def test_windows_hook_source_filters_large_mouse_jumps():
    source = WindowsHookInputSource()

    source.handle_mouse_move(0, 0)
    source.handle_mouse_move(int(MAX_SEGMENT_DISTANCE + 50), 0)

    payload = source.next_event()
    assert payload["deltaX"] == 0
    assert payload["deltaY"] == 0

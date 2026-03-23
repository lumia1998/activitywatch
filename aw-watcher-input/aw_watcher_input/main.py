import logging
import sys
from datetime import datetime, timezone
from time import sleep
from typing import Callable, Dict, Optional

from aw_client import ActivityWatchClient
from aw_core.log import setup_logging
from aw_core.models import Event
from aw_watcher_afk.listeners import KeyboardListener, MouseListener

from .config import parse_args

logger = logging.getLogger(__name__)
_EVENT_KEYS = ("presses", "clicks", "scrollX", "scrollY", "deltaX", "deltaY")


class AggregatedListenerSource:
    def __init__(self, keyboard=None, mouse=None) -> None:
        self.keyboard = keyboard or KeyboardListener()
        self.mouse = mouse or MouseListener()

    def start(self) -> None:
        self.keyboard.start()
        self.mouse.start()

    def stop(self) -> None:
        return None

    def has_new_event(self) -> bool:
        return self.keyboard.has_new_event() or self.mouse.has_new_event()

    def next_event(self) -> Dict[str, int]:
        keyboard_payload = self.keyboard.next_event() if self.keyboard.has_new_event() else None
        mouse_payload = self.mouse.next_event() if self.mouse.has_new_event() else None
        return _merge_input_payloads(keyboard_payload, mouse_payload)


def _empty_event_data() -> Dict[str, int]:
    return {key: 0 for key in _EVENT_KEYS}


def _to_int(value) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _merge_input_payloads(*payloads: Optional[dict]) -> Dict[str, int]:
    data = _empty_event_data()
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        for key in _EVENT_KEYS:
            data[key] += _to_int(payload.get(key, 0))
    return data


def _has_input(data: Dict[str, int]) -> bool:
    return any(data.values())


def _get_context_provider(include_window_info: bool) -> Optional[Callable[[], Dict[str, str]]]:
    if not include_window_info:
        return None
    if sys.platform not in {"win32", "cygwin"}:
        return None

    try:
        from .windows import get_active_window_context
    except Exception:
        logger.exception("Failed to initialize active window context provider")
        return None

    return get_active_window_context


def _build_input_source():
    if sys.platform in {"win32", "cygwin"}:
        from .windows import WindowsHookInputSource

        return WindowsHookInputSource()
    return AggregatedListenerSource()


class InputWatcher:
    def __init__(
        self,
        args,
        client: Optional[ActivityWatchClient] = None,
        input_source=None,
        context_provider: Optional[Callable[[], Dict[str, str]]] = None,
    ) -> None:
        self.poll_time = float(args.poll_time)
        self.client = client or ActivityWatchClient(
            "aw-watcher-input",
            host=args.host,
            port=args.port,
            testing=args.testing,
        )
        self.bucket_id = f"{self.client.client_name}_{self.client.client_hostname}"
        self.event_type = "os.hid.input"
        self.input_source = input_source or _build_input_source()
        self.context_provider = (
            context_provider
            if context_provider is not None
            else _get_context_provider(bool(getattr(args, "include_window_info", False)))
        )

    def start_listeners(self) -> None:
        self.input_source.start()

    def stop_listeners(self) -> None:
        stop = getattr(self.input_source, "stop", None)
        if callable(stop):
            stop()

    def collect_input_data(self) -> Optional[Dict[str, object]]:
        if not self.input_source.has_new_event():
            return None

        data = self.input_source.next_event()
        if not _has_input(data):
            return None

        if self.context_provider is not None:
            try:
                context = self.context_provider() or {}
            except Exception:
                logger.debug("Failed to resolve active window context", exc_info=True)
                context = {}
            if isinstance(context, dict):
                for key, value in context.items():
                    if value not in (None, ""):
                        data[key] = value

        return data

    def emit_event(self, data: Dict[str, object], now: Optional[datetime] = None) -> None:
        timestamp = now or datetime.now(timezone.utc)
        event = Event(timestamp=timestamp, duration=self.poll_time, data=data)
        self.client.insert_event(self.bucket_id, event)

    def run_once(self, now: Optional[datetime] = None) -> bool:
        data = self.collect_input_data()
        if data is None:
            return False
        self.emit_event(data, now=now)
        return True

    def run(self) -> None:
        logger.info("aw-watcher-input started")
        self.client.wait_for_start()
        self.client.create_bucket(self.bucket_id, self.event_type, queued=False)
        self.start_listeners()

        try:
            with self.client:
                while True:
                    try:
                        self.run_once()
                        sleep(self.poll_time)
                    except KeyboardInterrupt:
                        logger.info("aw-watcher-input stopped by keyboard interrupt")
                        break
                    except Exception:
                        logger.exception("aw-watcher-input failed during polling loop")
                        sleep(self.poll_time)
        finally:
            self.stop_listeners()


def main() -> None:
    args = parse_args()
    setup_logging(
        name="aw-watcher-input",
        testing=args.testing,
        verbose=args.verbose,
        log_stderr=True,
        log_file=True,
    )
    watcher = InputWatcher(args)
    watcher.run()

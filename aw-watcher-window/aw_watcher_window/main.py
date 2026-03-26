import logging
import os
import re
import signal
import subprocess
import sys
from datetime import datetime, timezone
from time import sleep

from aw_client import ActivityWatchClient
from aw_core.log import setup_logging
from aw_core.models import Event

from .config import parse_args
from .exceptions import FatalError
from .lib import get_current_window
from .macos_permissions import background_ensure_permissions

logger = logging.getLogger(__name__)

# run with LOG_LEVEL=DEBUG
log_level = os.environ.get("LOG_LEVEL")
if log_level:
    logger.setLevel(logging.__getattribute__(log_level.upper()))

MIN_STABLE_WINDOW_SECONDS = 3.0


def kill_process(pid):
    logger.info("Killing process {}".format(pid))
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        logger.info("Process {} already dead".format(pid))


def try_compile_title_regex(title):
    try:
        return re.compile(title, re.IGNORECASE)
    except re.error:
        logger.error(f"Invalid regex pattern: {title}")
        exit(1)


def _window_identity(window):
    if not isinstance(window, dict):
        return None
    return (
        window.get("app") or "",
        window.get("title") or "",
        window.get("display_name") or "",
        window.get("process_name") or "",
    )


def _next_stable_duration(current_window, previous_window, previous_duration, poll_time):
    current_identity = _window_identity(current_window)
    previous_identity = _window_identity(previous_window)
    if not current_identity:
        return 0.0
    if current_identity != previous_identity:
        return float(poll_time)
    return float(previous_duration) + float(poll_time)


def _should_emit_window(stable_duration, minimum_seconds=MIN_STABLE_WINDOW_SECONDS):
    return float(stable_duration) >= float(minimum_seconds)


def main():
    args = parse_args()

    if sys.platform.startswith("linux") and (
        "DISPLAY" not in os.environ or not os.environ["DISPLAY"]
    ):
        raise Exception("DISPLAY environment variable not set")

    setup_logging(
        name="aw-watcher-window",
        testing=args.testing,
        verbose=args.verbose,
        log_stderr=True,
        log_file=True,
    )

    if sys.platform == "darwin":
        background_ensure_permissions()

    client = ActivityWatchClient(
        "aw-watcher-window", host=args.host, port=args.port, testing=args.testing
    )

    bucket_id = f"{client.client_name}_{client.client_hostname}"
    event_type = "currentwindow"

    client.create_bucket(bucket_id, event_type, queued=True)

    logger.info("aw-watcher-window started")
    client.wait_for_start()

    with client:
        if sys.platform == "darwin" and args.strategy == "swift":
            logger.info("Using swift strategy, calling out to swift binary")
            binpath = os.path.join(
                os.path.dirname(os.path.realpath(__file__)), "aw-watcher-window-macos"
            )

            try:
                p = subprocess.Popen(
                    [
                        binpath,
                        client.server_address,
                        bucket_id,
                        client.client_hostname,
                        client.client_name,
                    ]
                )
                # terminate swift process when this process dies
                signal.signal(signal.SIGTERM, lambda *_: kill_process(p.pid))
                p.wait()
            except KeyboardInterrupt:
                print("KeyboardInterrupt")
                kill_process(p.pid)
        else:
            heartbeat_loop(
                client,
                bucket_id,
                poll_time=args.poll_time,
                strategy=args.strategy,
                exclude_title=args.exclude_title,
                exclude_titles=[
                    try_compile_title_regex(title)
                    for title in args.exclude_titles
                    if title is not None
                ],
            )


def heartbeat_loop(
    client, bucket_id, poll_time, strategy, exclude_title=False, exclude_titles=[]
):
    previous_window = None
    stable_duration = 0.0
    while True:
        if os.getppid() == 1:
            logger.info("window-watcher stopped because parent process died")
            break

        current_window = None
        try:
            current_window = get_current_window(strategy)
            logger.debug(current_window)
        except (FatalError, OSError):
            # Fatal exceptions should quit the program
            try:
                logger.exception("Fatal error, stopping")
            except OSError:
                pass
            break
        except Exception:
            # Non-fatal exceptions should be logged
            try:
                logger.exception("Exception thrown while trying to get active window")
            except OSError:
                break

        if current_window is None:
            logger.debug("Unable to fetch window, trying again on next poll")
            previous_window = None
            stable_duration = 0.0
        else:
            for pattern in exclude_titles:
                if pattern.search(current_window["title"]):
                    current_window["title"] = "excluded"

            if exclude_title:
                current_window["title"] = "excluded"

            stable_duration = _next_stable_duration(
                current_window=current_window,
                previous_window=previous_window,
                previous_duration=stable_duration,
                poll_time=poll_time,
            )

            if _should_emit_window(stable_duration):
                now = datetime.now(timezone.utc)
                current_window_event = Event(timestamp=now, data=current_window)
                client.heartbeat(
                    bucket_id, current_window_event, pulsetime=poll_time + 1.0, queued=True
                )

            previous_window = dict(current_window)

        sleep(poll_time)

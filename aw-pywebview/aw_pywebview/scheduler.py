import time
from datetime import datetime, timedelta
from typing import Optional

from .report import generate_report_by_config, load_report_config


def _next_run_time(hour: int, minute: int) -> datetime:
    now = datetime.now()
    run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if run_at <= now:
        run_at += timedelta(days=1)
    return run_at


def _sleep_until(target: datetime) -> None:
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        time.sleep(min(remaining, 30))


def run_report_scheduler_once() -> Optional[str]:
    cfg = load_report_config()
    if not cfg.enabled:
        return None

    path = generate_report_by_config(cfg)
    return path or None


def run_report_scheduler_forever(stop_event=None) -> None:
    while True:
        cfg = load_report_config()
        if not cfg.enabled:
            time.sleep(60)
            continue

        next_run = _next_run_time(cfg.hour, cfg.minute)
        _sleep_until(next_run)

        generate_report_by_config(cfg)

        if stop_event and stop_event.is_set():
            return

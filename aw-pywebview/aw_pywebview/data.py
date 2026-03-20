from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from aw_client import ActivityWatchClient
from aw_client.queries import DesktopQueryParams, fullDesktopQuery


INPUT_BUCKET_PREFIX = "aw-watcher-input"
WINDOW_BUCKET_PREFIX = "aw-watcher-window"
AFK_BUCKET_PREFIX = "aw-watcher-afk"


def _guess_bucket(buckets: Dict[str, dict], prefix: str, hostname: str) -> Optional[str]:
    exact = f"{prefix}_{hostname}"
    if exact in buckets:
        return exact
    for key in buckets.keys():
        if key.startswith(prefix + "_"):
            return key
    return None


def _to_seconds(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _category_to_label(cat) -> str:
    if isinstance(cat, list):
        return ">".join(cat)
    if isinstance(cat, str):
        return cat
    return "未分类"


def _parse_timestamp(ts: str) -> datetime:
    if ts.endswith("Z"):
        ts = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(ts)


def _build_summary_with_client(
    start: datetime, end: datetime, client: ActivityWatchClient
) -> Dict[str, object]:
    buckets = client.get_buckets()
    hostname = client.client_hostname

    bid_window = _guess_bucket(buckets, WINDOW_BUCKET_PREFIX, hostname)
    bid_afk = _guess_bucket(buckets, AFK_BUCKET_PREFIX, hostname)
    bid_browsers = [
        bid
        for bid in buckets.keys()
        if bid.startswith("aw-watcher-window-") or bid.startswith("aw-watcher-web-")
    ]

    if not bid_window or not bid_afk:
        return {"error": "Missing buckets"}

    params = DesktopQueryParams(
        bid_window=bid_window,
        bid_afk=bid_afk,
        bid_browsers=bid_browsers,
    )
    query = fullDesktopQuery(params)
    res = client.query(query, [(start, end)])

    return {
        "time_range": {
            "start": start.isoformat(),
            "end": end.isoformat(),
        },
        "result": res[0] if res else {},
    }


def build_summary_range(
    start: datetime, end: datetime, client: Optional[ActivityWatchClient] = None
) -> Dict[str, object]:
    client = client or ActivityWatchClient("aw-pywebview")
    return _build_summary_with_client(start, end, client)


def build_summary(
    days: int = 1, client: Optional[ActivityWatchClient] = None
) -> Dict[str, object]:
    now = datetime.now().astimezone()
    start = now - timedelta(days=days)
    client = client or ActivityWatchClient("aw-pywebview")
    return _build_summary_with_client(start, now, client)


def build_activity_from_summary(
    summary: Dict[str, object], limit: int = 20
) -> List[Dict[str, object]]:
    result = summary.get("result") if isinstance(summary, dict) else None
    if not result:
        return []

    app_events = result.get("window", {}).get("app_events", [])
    items = []
    for ev in app_events[:limit]:
        items.append(
            {
                "app": ev.get("data", {}).get("app", "unknown"),
                "duration": ev.get("duration", 0),
            }
        )
    return items


def build_timeline_from_summary(
    summary: Dict[str, object], limit: int = 200
) -> List[Dict[str, object]]:
    result = summary.get("result") if isinstance(summary, dict) else None
    if not result:
        return []

    events = result.get("events", [])
    events = list(sorted(events, key=lambda e: e.get("timestamp", "")))

    items: List[Dict[str, object]] = []
    for ev in events:
        start_ts = ev.get("timestamp")
        if not start_ts:
            continue
        duration_sec = _to_seconds(ev.get("duration"))
        end_ts = (_parse_timestamp(start_ts) + timedelta(seconds=duration_sec)).isoformat()
        data = ev.get("data", {})
        items.append(
            {
                "start": start_ts,
                "end": end_ts,
                "app": data.get("app", "unknown"),
                "title": data.get("title", ""),
                "category": _category_to_label(data.get("$category")),
                "duration": duration_sec,
            }
        )

    if limit > 0:
        items = items[-limit:]

    return items


def build_input_stats(
    start: datetime, end: datetime, client: Optional[ActivityWatchClient] = None
) -> Dict[str, object]:
    client = client or ActivityWatchClient("aw-pywebview")
    buckets = client.get_buckets()
    hostname = client.client_hostname

    bid_input = _guess_bucket(buckets, INPUT_BUCKET_PREFIX, hostname)
    if not bid_input:
        return {"error": "Missing input bucket"}

    events = client.get_events(bid_input, start=start, end=end)

    presses = 0
    clicks = 0
    scroll = 0
    moves = 0
    for ev in events:
        data = ev.data
        presses += int(data.get("presses", 0))
        clicks += int(data.get("clicks", 0))
        scroll += int(data.get("scrollX", 0)) + int(data.get("scrollY", 0))
        moves += int(data.get("deltaX", 0)) + int(data.get("deltaY", 0))

    return {
        "presses": presses,
        "clicks": clicks,
        "scroll": scroll,
        "moves": moves,
    }


def build_input_stats_by_top_apps(
    summary: Dict[str, object],
    start: datetime,
    end: datetime,
    top_n: int = 6,
    client: Optional[ActivityWatchClient] = None,
) -> List[Dict[str, object]]:
    client = client or ActivityWatchClient("aw-pywebview")
    buckets = client.get_buckets()
    hostname = client.client_hostname

    bid_input = _guess_bucket(buckets, INPUT_BUCKET_PREFIX, hostname)
    if not bid_input:
        return []

    events = client.get_events(bid_input, start=start, end=end)
    events = list(sorted(events, key=lambda e: e.timestamp))

    top_apps = build_activity_from_summary(summary, limit=top_n)
    if not top_apps:
        return []

    window_events = summary.get("result", {}).get("events", [])
    window_events = list(sorted(window_events, key=lambda e: e.get("timestamp", "")))

    app_ranges: Dict[str, List[Tuple[datetime, datetime]]] = {
        a["app"]: [] for a in top_apps
    }

    for ev in window_events:
        app = ev.get("data", {}).get("app")
        if not app or app not in app_ranges:
            continue
        start_ts = _parse_timestamp(ev.get("timestamp"))
        duration_sec = _to_seconds(ev.get("duration"))
        end_ts = start_ts + timedelta(seconds=duration_sec)
        app_ranges[app].append((start_ts, end_ts))

    stats = {app: {"presses": 0, "clicks": 0, "scroll": 0} for app in app_ranges.keys()}

    for ev in events:
        t = ev.timestamp
        data = ev.data
        for app, ranges in app_ranges.items():
            if any(r[0] <= t <= r[1] for r in ranges):
                stats[app]["presses"] += int(data.get("presses", 0))
                stats[app]["clicks"] += int(data.get("clicks", 0))
                stats[app]["scroll"] += int(data.get("scrollX", 0)) + int(data.get("scrollY", 0))
                break

    return [
        {"app": app["app"], **stats[app["app"]]} for app in top_apps
    ]


def build_input_trend(
    start: datetime,
    end: datetime,
    bucket_count: int = 24,
    client: Optional[ActivityWatchClient] = None,
) -> List[Dict[str, int]]:
    client = client or ActivityWatchClient("aw-pywebview")
    buckets = client.get_buckets()
    hostname = client.client_hostname

    bid_input = _guess_bucket(buckets, INPUT_BUCKET_PREFIX, hostname)
    if not bid_input:
        return []

    events = client.get_events(bid_input, start=start, end=end)
    if not events:
        return []

    start_ts = start.timestamp()
    end_ts = end.timestamp()
    span = max(end_ts - start_ts, 1)

    buckets_out = [{"count": 0} for _ in range(bucket_count)]

    for ev in events:
        t = ev.timestamp.timestamp()
        idx = int(((t - start_ts) / span) * bucket_count)
        idx = max(0, min(bucket_count - 1, idx))
        data = ev.data
        count = int(data.get("presses", 0)) + int(data.get("clicks", 0))
        count += int(data.get("scrollX", 0)) + int(data.get("scrollY", 0))
        buckets_out[idx]["count"] += count

    return buckets_out

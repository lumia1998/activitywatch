from collections import defaultdict
from datetime import datetime, timedelta, tzinfo
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from aw_client import ActivityWatchClient
from aw_client.queries import DesktopQueryParams, fullDesktopQuery


INPUT_BUCKET_PREFIX = "aw-watcher-input"
WINDOW_BUCKET_PREFIX = "aw-watcher-window"
AFK_BUCKET_PREFIX = "aw-watcher-afk"
HOST_PROCESS_NAMES = {
    "java",
    "javaw",
    "python",
    "pythonw",
    "node",
    "dotnet",
}
GENERIC_DISPLAY_NAMES = {
    "java(tm) platform se binary",
    "openjdk platform binary",
    "python",
    "pythonw",
    "node.js javascript runtime",
    "microsoft(r) .net host",
}
WINDOW_APP_ALIASES = {
    "centbrowser": "Cent Browser",
    "msedgewebview2": "Microsoft Edge WebView2",
    "explorer": "Windows 资源管理器",
}
TITLE_SEPARATORS = (" - ", " | ", " — ", " – ", ":")
DEFAULT_COLOR_PALETTE = [

    "#3b82f6",
    "#ef4444",
    "#10b981",
    "#f59e0b",
    "#8b5cf6",
    "#ec4899",
    "#14b8a6",
    "#f97316",
    "#6366f1",
    "#84cc16",
]


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


def _extract_timezone(reference: object) -> Optional[tzinfo]:
    if isinstance(reference, datetime):
        return reference.tzinfo
    if isinstance(reference, str):
        return _parse_timestamp(reference).tzinfo
    return None


def _convert_to_timezone(value: datetime, target_tz: Optional[tzinfo]) -> datetime:
    if not target_tz or value.tzinfo is None:
        return value
    return value.astimezone(target_tz)


def _summary_timezone(summary: Dict[str, object]) -> Optional[tzinfo]:
    time_range = summary.get("time_range", {}) if isinstance(summary, dict) else {}
    return _extract_timezone(time_range.get("start"))


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
        if bid.startswith("aw-watcher-web")
    ]

    if not bid_window or not bid_afk:
        missing = []
        if not bid_window:
            missing.append(WINDOW_BUCKET_PREFIX)
        if not bid_afk:
            missing.append(AFK_BUCKET_PREFIX)
        return {"error": f"Missing buckets: {', '.join(missing)}"}

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


def _normalize_app_name(value: object) -> str:
    if not isinstance(value, str):
        return "unknown"
    normalized = value.strip()
    return normalized or "unknown"


def _extract_meaningful_title(window_title: str) -> str:
    normalized = window_title.strip()
    if not normalized:
        return ""

    cut_index = -1
    for separator in TITLE_SEPARATORS:
        index = normalized.find(separator)
        if index <= 0:
            continue
        if cut_index == -1 or index < cut_index:
            cut_index = index

    segment = normalized[:cut_index].strip() if cut_index > 0 else normalized
    if len(segment) < 2 or len(segment) > 64:
        return ""
    if ".exe" in segment.lower() or "\\" in segment or "/" in segment:
        return ""
    return segment


def _is_preferred_display_name(candidate: object, app_name: str) -> bool:
    if not isinstance(candidate, str):
        return False

    normalized = candidate.strip()
    if not normalized:
        return False

    lowered = normalized.lower()
    if lowered in {"unknown", app_name.lower()}:
        return False

    return lowered not in GENERIC_DISPLAY_NAMES


def _resolve_display_name(app_name: object, title: object, preferred: object = None) -> str:
    normalized_app = _normalize_app_name(app_name)
    normalized_title = title.strip() if isinstance(title, str) else ""

    if isinstance(preferred, str) and preferred.strip():
        normalized_preferred = preferred.strip()
        if _is_preferred_display_name(normalized_preferred, normalized_app):
            return normalized_preferred

    lower_app = normalized_app.lower()
    if lower_app == "unknown":
        return "unknown"

    if "minecraft" in normalized_title.lower():
        return "Minecraft"

    if lower_app in HOST_PROCESS_NAMES:
        title_name = _extract_meaningful_title(normalized_title)
        if title_name:
            return title_name

    alias = WINDOW_APP_ALIASES.get(lower_app)
    if alias:
        return alias

    return normalized_app


def _extract_activity_item(ev: Dict[str, object]) -> Dict[str, object]:
    data = ev.get("data", {}) if isinstance(ev, dict) else {}
    app = _normalize_app_name(data.get("app"))
    title = data.get("title", "") if isinstance(data.get("title"), str) else ""
    display_name = _resolve_display_name(
        app_name=app,
        title=title,
        preferred=data.get("display_name") or data.get("app_display") or data.get("app_name"),
    )
    return {
        "app": app,
        "display_name": display_name,
        "title": title,
        "duration": ev.get("duration", 0),
    }


def _activity_lookup(items: List[Dict[str, object]]) -> Dict[str, Dict[str, object]]:
    return {
        item["app"]: item
        for item in items
        if isinstance(item.get("app"), str)
    }


def build_activity_from_summary(
    summary: Dict[str, object], limit: int = 20
) -> List[Dict[str, object]]:
    result = summary.get("result") if isinstance(summary, dict) else None
    if not result:
        return []

    app_events = result.get("window", {}).get("app_events", [])
    items = [_extract_activity_item(ev) for ev in app_events]
    return items[:limit] if limit > 0 else items


def build_activity_with_input(
    summary: Dict[str, object],
    start: datetime,
    end: datetime,
    limit: int = 20,
    client: Optional[ActivityWatchClient] = None,
    events=None,
) -> List[Dict[str, object]]:
    items = build_activity_from_summary(summary, limit=limit)
    if not items:
        return []

    input_by_app = build_input_by_app(
        summary=summary,
        start=start,
        end=end,
        top_n=0,
        client=client,
        events=events,
    )
    stats_by_app = {item["app"]: item for item in input_by_app}

    return [
        {
            **item,
            "presses": int(stats_by_app.get(item["app"], {}).get("presses", 0)),
            "clicks": int(stats_by_app.get(item["app"], {}).get("clicks", 0)),
            "scroll": int(stats_by_app.get(item["app"], {}).get("scroll", 0)),
            "moves": int(stats_by_app.get(item["app"], {}).get("moves", 0)),
        }
        for item in items
    ]


def build_timeline_from_summary(
    summary: Dict[str, object], limit: int = 200
) -> List[Dict[str, object]]:
    result = summary.get("result") if isinstance(summary, dict) else None
    if not result:
        return []

    target_tz = _summary_timezone(summary)
    events = result.get("events", [])
    events = list(sorted(events, key=lambda e: e.get("timestamp", "")))

    items: List[Dict[str, object]] = []
    for ev in events:
        start_ts = ev.get("timestamp")
        if not start_ts:
            continue
        duration_sec = _to_seconds(ev.get("duration"))
        start_dt = _convert_to_timezone(_parse_timestamp(start_ts), target_tz)
        end_ts = (start_dt + timedelta(seconds=duration_sec)).isoformat()
        data = ev.get("data", {})
        items.append(
            {
                "start": start_dt.isoformat(),
                "end": end_ts,
                "app": data.get("app", "unknown"),
                "display_name": _resolve_display_name(
                    data.get("app"),
                    data.get("title"),
                    data.get("display_name") or data.get("app_display") or data.get("app_name"),
                ),
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




def _key_stats_data_paths() -> List[Path]:
    local_appdata = os.environ.get("LOCALAPPDATA")
    paths: List[Path] = []
    if local_appdata:
        base = Path(local_appdata) / "KeyStats"
        paths.extend([
            base / "daily_stats.json",
            base / "history.json",
        ])
    return paths


def _load_key_stats_json(path: Path) -> Optional[Any]:
    try:
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _resolve_key_stats_day_payload(start: datetime, end: datetime) -> Optional[Dict[str, Any]]:
    daily_path, history_path = _key_stats_data_paths()[:2]
    target_date = end.astimezone().date().isoformat()

    daily_payload = _load_key_stats_json(daily_path)
    if isinstance(daily_payload, dict):
        daily_date = str(daily_payload.get("date", ""))[:10]
        if daily_date == target_date:
            return daily_payload

    history_payload = _load_key_stats_json(history_path)
    if isinstance(history_payload, dict):
        day_payload = history_payload.get(target_date)
        if isinstance(day_payload, dict):
            return day_payload

    for key, value in sorted((history_payload or {}).items(), reverse=True):
        if not isinstance(value, dict):
            continue
        day = str(value.get("date", key))[:10]
        if str(start.date()) <= day <= str(end.date()):
            return value

    return None


def _key_stats_clicks_total(item: Dict[str, Any]) -> int:
    fields = [
        ("LeftClicks", "leftClicks"),
        ("RightClicks", "rightClicks"),
        ("MiddleClicks", "middleClicks"),
        ("SideBackClicks", "sideBackClicks"),
        ("SideForwardClicks", "sideForwardClicks"),
    ]
    return sum(int(item.get(primary, item.get(fallback, 0)) or 0) for primary, fallback in fields)


def _build_key_stats_summary(day_payload: Dict[str, Any]) -> Dict[str, object]:
    presses = int(day_payload.get("keyPresses", 0) or 0)
    clicks = _key_stats_clicks_total(day_payload)
    scroll = int(round(float(day_payload.get("scrollDistance", 0) or 0)))
    moves = int(round(float(day_payload.get("mouseDistance", 0) or 0)))
    total = presses + clicks + scroll
    date_text = str(day_payload.get("date", ""))[:10]

    return {
        "available": total > 0 or moves > 0,
        "totals": {
            "presses": presses,
            "clicks": clicks,
            "scroll": scroll,
            "moves": moves,
            "total": total,
        },
        "averagePerHour": total / 24 if total > 0 else 0.0,
        "peakHour": {"hour": 12, "total": total} if total > 0 else None,
        "source": "keystats",
        "sourceDate": date_text,
    }


def _build_key_stats_by_app(day_payload: Dict[str, Any], top_n: int = 6) -> List[Dict[str, object]]:
    app_stats = day_payload.get("appStats") or {}
    if not isinstance(app_stats, dict):
        return []

    items: List[Dict[str, object]] = []
    for app_name, raw in app_stats.items():
        if not isinstance(raw, dict):
            continue
        presses = int(raw.get("KeyPresses", 0) or 0)
        clicks = _key_stats_clicks_total(raw)
        scroll = int(round(float(raw.get("ScrollDistance", 0) or 0)))
        total = presses + clicks + scroll
        if total <= 0:
            continue
        stable_app = _normalize_app_name(raw.get("AppName") or app_name)
        display_name = _resolve_display_name(
            stable_app,
            "",
            raw.get("DisplayName") or raw.get("display_name") or raw.get("app_display"),
        )
        items.append(
            {
                "app": stable_app,
                "display_name": display_name,
                "presses": presses,
                "clicks": clicks,
                "scroll": scroll,
                "moves": 0,
                "total": total,
            }
        )

    items.sort(key=lambda item: (-item["total"], -item["presses"], item["display_name"], item["app"]))
    return items[:top_n] if top_n > 0 else items


def _build_key_stats_trend(day_payload: Dict[str, Any], bucket_count: int = 24) -> List[Dict[str, int]]:
    totals = _build_key_stats_summary(day_payload)["totals"]
    return [
        {
            "hour": hour,
            "presses": totals["presses"] if hour == 12 else 0,
            "clicks": totals["clicks"] if hour == 12 else 0,
            "scroll": totals["scroll"] if hour == 12 else 0,
            "moves": totals["moves"] if hour == 12 else 0,
            "total": totals["total"] if hour == 12 else 0,
        }
        for hour in range(bucket_count)
    ]


def _load_input_events(
    start: datetime, end: datetime, client: Optional[ActivityWatchClient] = None
):
    client = client or ActivityWatchClient("aw-pywebview")
    try:
        buckets = client.get_buckets()
        hostname = client.client_hostname
        bid_input = _guess_bucket(buckets, INPUT_BUCKET_PREFIX, hostname)
        if not bid_input:
            return None
        events = client.get_events(bid_input, start=start, end=end)
        return list(sorted(events, key=lambda e: e.timestamp))
    except Exception:
        return None


def _input_values_from_event(ev) -> Dict[str, int]:
    data = ev.data
    presses = int(data.get("presses", 0))
    clicks = int(data.get("clicks", 0))
    scroll = int(data.get("scrollX", 0)) + int(data.get("scrollY", 0))
    moves = int(data.get("deltaX", 0)) + int(data.get("deltaY", 0))
    return {
        "presses": presses,
        "clicks": clicks,
        "scroll": scroll,
        "moves": moves,
        "total": presses + clicks + scroll,
    }


def _empty_input_summary() -> Dict[str, object]:
    return {
        "available": False,
        "totals": {
            "presses": 0,
            "clicks": 0,
            "scroll": 0,
            "moves": 0,
            "total": 0,
        },
        "averagePerHour": 0.0,
        "peakHour": None,
    }


def _build_window_ranges(summary: Dict[str, object]) -> List[Dict[str, object]]:
    window_events = summary.get("result", {}).get("events", []) if isinstance(summary, dict) else []
    target_tz = _summary_timezone(summary)
    activity_lookup = _activity_lookup(build_activity_from_summary(summary, limit=0))
    ranges: List[Dict[str, object]] = []
    for ev in sorted(window_events, key=lambda item: item.get("timestamp", "")):
        timestamp = ev.get("timestamp")
        if not timestamp:
            continue
        start_ts = _convert_to_timezone(_parse_timestamp(timestamp), target_tz)
        duration_sec = _to_seconds(ev.get("duration"))
        if duration_sec <= 0:
            continue
        data = ev.get("data", {}) if isinstance(ev, dict) else {}
        app = _normalize_app_name(data.get("app"))
        activity_item = activity_lookup.get(app, {})
        display_name = _resolve_display_name(
            app,
            data.get("title"),
            activity_item.get("display_name") or data.get("display_name") or data.get("app_display") or data.get("app_name"),
        )
        ranges.append(
            {
                "start": start_ts,
                "end": start_ts + timedelta(seconds=duration_sec),
                "app": app,
                "display_name": display_name,
            }
        )
    return ranges


def build_input_by_app(
    summary: Dict[str, object],
    start: datetime,
    end: datetime,
    top_n: int = 6,
    client: Optional[ActivityWatchClient] = None,
    events=None,
) -> List[Dict[str, object]]:
    input_events = events if events is not None else _load_input_events(start, end, client=client)
    if input_events is None:
        key_stats_day = _resolve_key_stats_day_payload(start, end)
        return _build_key_stats_by_app(key_stats_day, top_n=top_n) if key_stats_day else []

    target_tz = _summary_timezone(summary) or _extract_timezone(start) or _extract_timezone(end)
    window_ranges = _build_window_ranges(summary)
    if not window_ranges:
        return []

    stats: Dict[str, Dict[str, object]] = defaultdict(
        lambda: {
            "display_name": "unknown",
            "presses": 0,
            "clicks": 0,
            "scroll": 0,
            "moves": 0,
            "total": 0,
        }
    )
    range_index = 0

    for ev in input_events:
        event_timestamp = _convert_to_timezone(ev.timestamp, target_tz)
        while range_index < len(window_ranges) and window_ranges[range_index]["end"] < event_timestamp:
            range_index += 1
        if range_index >= len(window_ranges):
            break

        active_range = window_ranges[range_index]
        if not (active_range["start"] <= event_timestamp <= active_range["end"]):
            continue

        values = _input_values_from_event(ev)
        app_stats = stats[active_range["app"]]
        app_stats["display_name"] = active_range["display_name"]
        for key, value in values.items():
            app_stats[key] += value

    items = [
        {"app": app, **values}
        for app, values in stats.items()
        if values["total"] > 0 or values["moves"] > 0
    ]
    items.sort(
        key=lambda item: (
            -item["total"],
            -item["presses"],
            str(item.get("display_name", "")),
            item["app"],
        )
    )
    return items[:top_n] if top_n > 0 else items


def build_input_stats_by_top_apps(
    summary: Dict[str, object],
    start: datetime,
    end: datetime,
    top_n: int = 6,
    client: Optional[ActivityWatchClient] = None,
) -> List[Dict[str, object]]:
    items = build_input_by_app(
        summary=summary,
        start=start,
        end=end,
        top_n=top_n,
        client=client,
    )
    return [
        {
            "app": item["app"],
            "display_name": item.get("display_name", item["app"]),
            "presses": item["presses"],
            "clicks": item["clicks"],
            "scroll": item["scroll"],
        }
        for item in items
    ]


def build_input_trend(
    start: datetime,
    end: datetime,
    bucket_count: int = 24,
    client: Optional[ActivityWatchClient] = None,
    events=None,
) -> List[Dict[str, int]]:
    buckets_out = [
        {"hour": hour, "presses": 0, "clicks": 0, "scroll": 0, "moves": 0, "total": 0}
        for hour in range(bucket_count)
    ]

    input_events = events if events is not None else _load_input_events(start, end, client=client)
    if input_events is None:
        key_stats_day = _resolve_key_stats_day_payload(start, end)
        return _build_key_stats_trend(key_stats_day, bucket_count=bucket_count) if key_stats_day else []
    if not input_events:
        return buckets_out

    target_tz = _extract_timezone(start) or _extract_timezone(end)
    for ev in input_events:
        event_timestamp = _convert_to_timezone(ev.timestamp, target_tz)
        bucket = buckets_out[event_timestamp.hour % bucket_count]
        values = _input_values_from_event(ev)
        for key, value in values.items():
            bucket[key] += value

    return buckets_out


def build_input_stats_full(
    start: datetime,
    end: datetime,
    client: Optional[ActivityWatchClient] = None,
    events=None,
) -> Dict[str, object]:
    input_events = events if events is not None else _load_input_events(start, end, client=client)
    if input_events is None:
        key_stats_day = _resolve_key_stats_day_payload(start, end)
        return _build_key_stats_summary(key_stats_day) if key_stats_day else _empty_input_summary()

    trend = build_input_trend(start, end, client=client, events=input_events)
    totals = {
        "presses": 0,
        "clicks": 0,
        "scroll": 0,
        "moves": 0,
        "total": 0,
    }
    for bucket in trend:
        for key in totals.keys():
            totals[key] += bucket.get(key, 0)

    tracked_hours = max((end - start).total_seconds() / 3600, 1 / 60)
    peak = max(trend, key=lambda item: (item["total"], -item["hour"]), default=None)

    return {
        "available": True,
        "totals": totals,
        "averagePerHour": totals["total"] / tracked_hours,
        "peakHour": (
            {"hour": peak["hour"], "total": peak["total"]}
            if peak and peak["total"] > 0
            else None
        ),
        "source": "activitywatch",
    }


def _browser_result(summary: Dict[str, object]) -> Dict[str, object]:
    result = summary.get("result", {}) if isinstance(summary, dict) else {}
    browser = result.get("browser") if isinstance(result, dict) else {}
    return browser if isinstance(browser, dict) else {}


def _domain_from_url(url: object) -> str:
    if not isinstance(url, str):
        return ""
    normalized = url.strip()
    if not normalized:
        return ""
    parsed = urlparse(normalized if "://" in normalized else f"//{normalized}")
    hostname = (parsed.hostname or parsed.netloc or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]
    return hostname


def _normalize_domain(value: object) -> str:
    if not isinstance(value, str):
        return "未知域名"
    normalized = value.strip().lower()
    if not normalized:
        return "未知域名"
    hostname = _domain_from_url(normalized)
    if hostname:
        return hostname
    return normalized[4:] if normalized.startswith("www.") else normalized


def _extract_browser_domain(data: Dict[str, object]) -> str:
    domain = _normalize_domain(data.get("$domain") or data.get("domain") or "")
    if domain != "未知域名":
        return domain
    return _normalize_domain(data.get("url") or "")


def _projected_days(time_range: Dict[str, object], events: List[Dict[str, object]]) -> int:
    return max(
        1,
        len({event["start"].date().isoformat() for event in events}) or (1 if time_range else 0),
    )


def _empty_browser_summary() -> Dict[str, object]:
    return {
        "available": False,
        "totalDuration": 0.0,
        "domainCount": 0,
        "urlCount": 0,
        "topDomain": None,
    }


def _empty_browser_trend(
    summary: Optional[Dict[str, object]] = None,
    bucket_count: int = 24,
    min_duration: float = 2,
    top_n_domains: int = 6,
) -> Dict[str, object]:
    time_range = summary.get("time_range", {}) if isinstance(summary, dict) else {}
    return {
        "meta": {
            "rangeStart": time_range.get("start"),
            "rangeEnd": time_range.get("end"),
            "days": 1 if time_range else 0,
            "projectedToSingleDay": True,
            "minDuration": min_duration,
            "topDomainsLimit": top_n_domains,
        },
        "colorMap": {},
        "activeHour": None,
        "hourlyBars": [
            {"hour": hour, "total": 0.0, "segments": []}
            for hour in range(bucket_count)
        ],
    }


def _build_browser_url_counts(summary: Dict[str, object]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for event in _browser_result(summary).get("urls", []) or []:
        data = event.get("data", {}) if isinstance(event, dict) else {}
        domain = _extract_browser_domain(data)
        counts[domain] += 1
    return counts


def build_browser_by_domain(
    summary: Dict[str, object], limit: int = 12
) -> List[Dict[str, object]]:
    browser = _browser_result(summary)
    total_duration = _to_seconds(browser.get("duration", 0))
    url_counts = _build_browser_url_counts(summary)

    items: List[Dict[str, object]] = []
    for event in browser.get("domains", []) or []:
        data = event.get("data", {}) if isinstance(event, dict) else {}
        domain = _extract_browser_domain(data)
        duration = _to_seconds(event.get("duration", 0))
        if duration <= 0:
            continue
        items.append(
            {
                "domain": domain,
                "duration": duration,
                "share": duration / total_duration if total_duration > 0 else 0.0,
                "urlCount": int(url_counts.get(domain, 0)),
            }
        )

    items.sort(key=lambda item: (-item["duration"], item["domain"]))
    return items[:limit] if limit > 0 else items


def build_browser_summary(
    summary: Dict[str, object], items: Optional[List[Dict[str, object]]] = None
) -> Dict[str, object]:
    browser = _browser_result(summary)
    all_items = items if items is not None else build_browser_by_domain(summary, limit=0)
    total_duration = _to_seconds(browser.get("duration", 0)) or sum(
        item.get("duration", 0) for item in all_items
    )
    url_count = len(browser.get("urls", []) or [])
    top_domain = all_items[0] if all_items else None

    if total_duration <= 0 or not all_items:
        return _empty_browser_summary()

    return {
        "available": True,
        "totalDuration": total_duration,
        "domainCount": len(all_items),
        "urlCount": url_count,
        "topDomain": (
            {
                "domain": top_domain["domain"],
                "duration": top_domain["duration"],
                "share": top_domain.get("share", 0.0),
            }
            if top_domain
            else None
        ),
    }


def _iter_browser_events(
    summary: Dict[str, object], min_duration: float = 2
) -> List[Dict[str, object]]:
    browser = _browser_result(summary)
    target_tz = _summary_timezone(summary)
    browser_events: List[Dict[str, object]] = []

    for event in browser.get("events", []) or []:
        timestamp = event.get("timestamp")
        if not timestamp:
            continue

        duration = _to_seconds(event.get("duration", 0))
        if duration <= min_duration:
            continue

        data = event.get("data", {}) if isinstance(event, dict) else {}
        start = _convert_to_timezone(_parse_timestamp(timestamp), target_tz)
        browser_events.append(
            {
                "start": start,
                "end": start + timedelta(seconds=duration),
                "duration": duration,
                "domain": _extract_browser_domain(data),
                "url": data.get("url", "") or "",
            }
        )

    return sorted(browser_events, key=lambda item: item["start"])


def build_browser_trend(
    summary: Dict[str, object], min_duration: float = 2, top_n_domains: int = 6
) -> Dict[str, object]:
    time_range = summary.get("time_range", {}) if isinstance(summary, dict) else {}
    browser_events = _iter_browser_events(summary, min_duration=min_duration)
    if not browser_events:
        return _empty_browser_trend(
            summary,
            min_duration=min_duration,
            top_n_domains=top_n_domains,
        )

    slices = [
        sliced
        for event in browser_events
        for sliced in _slice_event_into_hours(event)
        if sliced.get("slice_duration", 0) > 0
    ]

    domain_totals: Dict[str, float] = defaultdict(float)
    for sliced in slices:
        domain_totals[sliced["domain"]] += sliced["slice_duration"]

    top_domains = [
        domain
        for domain, _ in sorted(domain_totals.items(), key=lambda item: (-item[1], item[0]))[:top_n_domains]
    ]
    segment_keys = top_domains + (["其他"] if len(domain_totals) > len(top_domains) else [])
    color_map = _build_stable_color_mapping(segment_keys)

    hourly_by_domain: Dict[int, Dict[str, float]] = {hour: defaultdict(float) for hour in range(24)}
    hourly_totals: Dict[int, float] = {hour: 0.0 for hour in range(24)}
    for sliced in slices:
        hour = sliced["hour"]
        domain = sliced["domain"] if sliced["domain"] in top_domains else "其他"
        duration = sliced["slice_duration"]
        hourly_by_domain[hour][domain] += duration
        hourly_totals[hour] += duration

    hourly_bars = []
    for hour in range(24):
        segments = [
            {
                "domain": domain,
                "duration": duration,
                "color": color_map.get(domain),
            }
            for domain, duration in sorted(
                hourly_by_domain[hour].items(), key=lambda item: (-item[1], item[0])
            )
        ]
        hourly_bars.append(
            {
                "hour": hour,
                "total": hourly_totals[hour],
                "segments": segments,
            }
        )

    active_hour = None
    if any(item["total"] > 0 for item in hourly_bars):
        active_hour = max(hourly_bars, key=lambda item: (item["total"], -item["hour"]))["hour"]

    return {
        "meta": {
            "rangeStart": time_range.get("start"),
            "rangeEnd": time_range.get("end"),
            "days": _projected_days(time_range, browser_events),
            "projectedToSingleDay": True,
            "minDuration": min_duration,
            "topDomainsLimit": top_n_domains,
        },
        "colorMap": color_map,
        "activeHour": active_hour,
        "hourlyBars": hourly_bars,
    }


def _iter_visual_events(
    summary: Dict[str, object], min_duration: float = 2
) -> List[Dict[str, object]]:
    result = summary.get("result", {}) if isinstance(summary, dict) else {}
    target_tz = _summary_timezone(summary)
    events = result.get("events", [])

    visual_events: List[Dict[str, object]] = []
    for ev in events:
        timestamp = ev.get("timestamp")
        if not timestamp:
            continue

        duration = _to_seconds(ev.get("duration", 0))
        if duration <= min_duration:
            continue

        start = _convert_to_timezone(_parse_timestamp(timestamp), target_tz)
        end = start + timedelta(seconds=duration)
        data = ev.get("data", {})
        visual_events.append(
            {
                "start": start,
                "end": end,
                "duration": duration,
                "app": data.get("app", "unknown") or "unknown",
                "title": data.get("title", "") or "",
                "category": _category_to_label(data.get("$category")),
            }
        )

    return sorted(visual_events, key=lambda item: item["start"])


def _slice_event_into_hours(event: Dict[str, object]) -> List[Dict[str, object]]:
    start = event["start"]
    end = event["end"]
    slices: List[Dict[str, object]] = []

    cursor = start
    while cursor < end:
        hour_end = (cursor.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        slice_end = min(hour_end, end)
        duration = max((slice_end - cursor).total_seconds(), 0.0)
        if duration > 0:
            slices.append(
                {
                    **event,
                    "slice_start": cursor,
                    "slice_end": slice_end,
                    "slice_duration": duration,
                    "hour": cursor.hour,
                }
            )
        cursor = slice_end

    return slices


def _build_stable_color_mapping(keys: List[str]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for index, key in enumerate(sorted({key for key in keys if key})):
        mapping[key] = DEFAULT_COLOR_PALETTE[index % len(DEFAULT_COLOR_PALETTE)]
    return mapping


def build_visualization_data(
    summary: Dict[str, object], min_duration: float = 2, top_n_apps: int = 10
) -> Dict[str, object]:
    time_range = summary.get("time_range", {}) if isinstance(summary, dict) else {}
    visual_events = _iter_visual_events(summary, min_duration=min_duration)
    slices = [
        sliced
        for event in visual_events
        for sliced in _slice_event_into_hours(event)
        if sliced.get("slice_duration", 0) > 0
    ]

    category_keys = [event["category"] for event in visual_events]
    app_totals: Dict[str, float] = defaultdict(float)
    for sliced in slices:
        app_totals[sliced["app"]] += sliced["slice_duration"]

    top_apps = [
        app
        for app, _ in sorted(app_totals.items(), key=lambda item: (-item[1], item[0]))[:top_n_apps]
    ]
    hourly_segment_keys = top_apps + (["其他"] if len(app_totals) > len(top_apps) else [])
    color_map = _build_stable_color_mapping(category_keys + hourly_segment_keys)

    hourly_by_app: Dict[int, Dict[str, float]] = {hour: defaultdict(float) for hour in range(24)}
    hourly_totals: Dict[int, float] = {hour: 0.0 for hour in range(24)}
    for sliced in slices:
        hour = sliced["hour"]
        app = sliced["app"] if sliced["app"] in top_apps else "其他"
        duration = sliced["slice_duration"]
        hourly_by_app[hour][app] += duration
        hourly_totals[hour] += duration

    hourly_bars = []
    for hour in range(24):
        apps = hourly_by_app[hour]
        segments = [
            {
                "app": app,
                "duration": duration,
                "color": color_map.get(app),
            }
            for app, duration in sorted(apps.items(), key=lambda item: (-item[1], item[0]))
        ]
        hourly_bars.append(
            {
                "hour": hour,
                "total": hourly_totals[hour],
                "segments": segments,
            }
        )

    heatmap_apps = []
    for app in top_apps:
        durations = [0.0] * 24
        for sliced in slices:
            if sliced["app"] == app:
                durations[sliced["hour"]] += sliced["slice_duration"]
        heatmap_apps.append(
            {
                "app": app,
                "total": sum(durations),
                "hours": durations,
                "color": color_map.get(app),
            }
        )

    gantt_lanes = []
    blocks_by_lane: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for sliced in slices:
        app = sliced["app"]
        if app not in top_apps:
            continue

        block_key = (
            app,
            sliced["category"],
            sliced["title"],
            sliced["slice_start"].date().isoformat(),
        )
        start_dt = sliced["slice_start"]
        end_dt = sliced["slice_end"]
        start_minutes = (
            start_dt.hour * 60 + start_dt.minute + start_dt.second / 60 + start_dt.microsecond / 60000000
        )
        end_minutes = (
            end_dt.hour * 60 + end_dt.minute + end_dt.second / 60 + end_dt.microsecond / 60000000
        )
        if end_minutes <= start_minutes:
            continue

        blocks_by_lane[app].append(
            {
                "merge_key": block_key,
                "app": app,
                "category": sliced["category"],
                "title": sliced["title"],
                "start_minutes": start_minutes,
                "end_minutes": end_minutes,
                "duration": sliced["slice_duration"],
            }
        )

    for app in top_apps:
        merged_blocks: List[Dict[str, object]] = []
        pending_by_key: Dict[Tuple[str, str, str, str], Dict[str, object]] = {}
        for block in sorted(
            blocks_by_lane.get(app, []), key=lambda item: (item["merge_key"], item["start_minutes"])
        ):
            merge_key = block.pop("merge_key")
            pending = pending_by_key.get(merge_key)
            if pending and block["start_minutes"] <= pending["end_minutes"] + 1e-6:
                pending["end_minutes"] = max(pending["end_minutes"], block["end_minutes"])
                pending["duration"] += block["duration"]
            else:
                pending = dict(block)
                pending_by_key[merge_key] = pending
                merged_blocks.append(pending)

        merged_blocks.sort(key=lambda item: (item["start_minutes"], item["end_minutes"], item["title"]))
        gantt_lanes.append(
            {
                "app": app,
                "total": app_totals.get(app, 0.0),
                "color": color_map.get(app),
                "blocks": [
                    {
                        **block,
                        "start": block["start_minutes"] / 60,
                        "end": block["end_minutes"] / 60,
                    }
                    for block in merged_blocks
                ],
            }
        )

    active_hour = None
    if any(item["total"] > 0 for item in hourly_bars):
        active_hour = max(hourly_bars, key=lambda item: (item["total"], -item["hour"]))["hour"]

    return {
        "meta": {
            "rangeStart": time_range.get("start"),
            "rangeEnd": time_range.get("end"),
            "days": max(
                1,
                len(
                    {
                        event["start"].date().isoformat()
                        for event in visual_events
                    }
                )
                or (1 if time_range else 0),
            ),
            "projectedToSingleDay": True,
            "minDuration": min_duration,
            "topAppsLimit": top_n_apps,
        },
        "colorMap": color_map,
        "activeHour": active_hour,
        "hourlyBars": hourly_bars,
        "gantt": {
            "lanes": gantt_lanes,
        },
        "heatmap": {
            "apps": heatmap_apps,
        },
    }


def get_consistent_color_mapping(summary: Dict[str, object]) -> Dict[str, str]:
    return build_visualization_data(summary).get("colorMap", {})


def build_hourly_category_breakdown(
    summary: Dict[str, object], min_duration: float = 2
) -> List[Dict[str, object]]:
    return build_visualization_data(summary, min_duration=min_duration).get("hourlyBars", [])


def build_gantt_data(
    summary: Dict[str, object], min_duration: float = 2, top_n_apps: int = 10
) -> Dict[str, object]:
    return build_visualization_data(
        summary, min_duration=min_duration, top_n_apps=top_n_apps
    ).get("gantt", {"lanes": []})


def build_heatmap_data(
    summary: Dict[str, object], min_duration: float = 2, top_n_apps: int = 10
) -> Dict[str, object]:
    return build_visualization_data(
        summary, min_duration=min_duration, top_n_apps=top_n_apps
    ).get("heatmap", {"apps": []})


def _build_activity_section(
    summary: Dict[str, object],
    start: datetime,
    end: datetime,
    activity_limit: int,
    timeline_limit: int,
    client: ActivityWatchClient,
    input_events,
) -> Dict[str, object]:
    return {
        "activity": build_activity_with_input(
            summary,
            start=start,
            end=end,
            limit=activity_limit,
            client=client,
            events=input_events,
        ),
        "timeline": build_timeline_from_summary(summary, limit=timeline_limit),
    }


def _build_input_section(
    summary: Dict[str, object],
    start: datetime,
    end: datetime,
    top_n_apps: int,
    client: ActivityWatchClient,
    input_events,
) -> Dict[str, object]:
    input_by_app = build_input_by_app(
        summary=summary,
        start=start,
        end=end,
        top_n=top_n_apps,
        client=client,
        events=input_events,
    )
    return {
        "inputTopApps": [
            {
                "app": item["app"],
                "display_name": item.get("display_name", item["app"]),
                "presses": item["presses"],
                "clicks": item["clicks"],
                "scroll": item["scroll"],
            }
            for item in input_by_app
        ],
        "inputSummary": build_input_stats_full(
            start=start,
            end=end,
            client=client,
            events=input_events,
        ),
        "inputTrend": build_input_trend(
            start=start,
            end=end,
            client=client,
            events=input_events,
        ),
        "inputByApp": input_by_app,
    }


def _build_browser_section(
    summary: Dict[str, object], activity_limit: int, top_n_apps: int
) -> Dict[str, object]:
    browser_by_domain = build_browser_by_domain(summary, limit=activity_limit)
    return {
        "browserSummary": build_browser_summary(summary, items=browser_by_domain),
        "browserByDomain": browser_by_domain,
        "browserTrend": build_browser_trend(summary, top_n_domains=max(top_n_apps, 1)),
    }


def _build_visualization_section(summary: Dict[str, object]) -> Dict[str, object]:
    return {
        "visualization": build_visualization_data(summary),
    }


def build_dashboard_payload(
    summary: Dict[str, object],
    start: datetime,
    end: datetime,
    top_n_apps: int = 6,
    activity_limit: int = 12,
    timeline_limit: int = 40,
    client: Optional[ActivityWatchClient] = None,
) -> Dict[str, object]:
    client = client or ActivityWatchClient("aw-pywebview")
    input_events = _load_input_events(start, end, client=client)

    return {
        "summary": summary,
        **_build_activity_section(
            summary=summary,
            start=start,
            end=end,
            activity_limit=activity_limit,
            timeline_limit=timeline_limit,
            client=client,
            input_events=input_events,
        ),
        **_build_input_section(
            summary=summary,
            start=start,
            end=end,
            top_n_apps=top_n_apps,
            client=client,
            input_events=input_events,
        ),
        **_build_browser_section(
            summary=summary,
            activity_limit=activity_limit,
            top_n_apps=top_n_apps,
        ),
        **_build_visualization_section(summary),
    }

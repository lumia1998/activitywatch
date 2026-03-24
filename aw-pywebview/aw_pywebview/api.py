from datetime import datetime, timedelta
from typing import Dict, List

from aw_client import ActivityWatchClient

from .data import (
    build_activity_with_input,
    build_dashboard_payload,
    build_gantt_data,
    build_heatmap_data,
    build_hourly_category_breakdown,
    build_input_stats_by_top_apps,
    build_summary,
    build_summary_range,
    build_timeline_from_summary,
    build_visualization_data,
    get_consistent_color_mapping,
)


def _start_of_day() -> datetime:
    now = datetime.now().astimezone()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _empty_browser_summary() -> Dict[str, object]:
    return {
        "available": False,
        "totalDuration": 0.0,
        "domainCount": 0,
        "urlCount": 0,
        "topDomain": None,
    }


def _empty_browser_trend() -> Dict[str, object]:
    return {
        "meta": {
            "rangeStart": None,
            "rangeEnd": None,
            "days": 0,
            "projectedToSingleDay": True,
            "minDuration": 2,
            "topDomainsLimit": 0,
        },
        "colorMap": {},
        "activeHour": None,
        "hourlyBars": [
            {"hour": hour, "total": 0.0, "segments": []}
            for hour in range(24)
        ],
    }


def _error_response(code: str, message: str, details: str = "") -> Dict[str, object]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "summary": None,
        "activity": [],
        "timeline": [],
        "inputTopApps": [],
        "inputSummary": None,
        "inputTrend": [],
        "inputByApp": [],
        "browserSummary": _empty_browser_summary(),
        "browserByDomain": [],
        "browserTrend": _empty_browser_trend(),
        "visualization": None,
        "warnings": [],
    }


class AppApi:
    def __init__(self) -> None:
        pass

    def _get_client(self) -> ActivityWatchClient:
        return ActivityWatchClient("aw-pywebview")

    def get_buckets(self) -> Dict[str, dict]:
        return self._get_client().get_buckets()

    def get_summary_today(self) -> Dict[str, object]:
        start = _start_of_day()
        end = datetime.now().astimezone()
        return build_summary_range(start, end, client=self._get_client())

    def get_summary(self, days: int = 1) -> Dict[str, object]:
        return build_summary(days=days, client=self._get_client())

    def get_activity(self, days: int = 1, limit: int = 20) -> List[Dict[str, object]]:
        end = datetime.now().astimezone()
        start = end - timedelta(days=days)
        client = self._get_client()
        summary = build_summary_range(start, end, client=client)
        if "error" in summary:
            return []
        return build_activity_with_input(summary, start=start, end=end, limit=limit, client=client)

    def get_timeline(self, days: int = 1, limit: int = 200) -> List[Dict[str, object]]:
        summary = self.get_summary(days)
        return build_timeline_from_summary(summary, limit=limit)

    def get_timeline_today(self, limit: int = 200) -> List[Dict[str, object]]:
        summary = self.get_summary_today()
        return build_timeline_from_summary(summary, limit=limit)

    def get_input_top_apps(self, days: int = 1, top_n: int = 6) -> List[Dict[str, object]]:
        end = datetime.now().astimezone()
        start = end - timedelta(days=days)
        summary = build_summary_range(start, end, client=self._get_client())
        if "error" in summary:
            return []
        return build_input_stats_by_top_apps(
            summary=summary,
            start=start,
            end=end,
            top_n=top_n,
            client=self._get_client(),
        )

    def get_color_mapping(self, days: int = 1) -> Dict[str, str]:
        summary = self.get_summary(days)
        return get_consistent_color_mapping(summary)

    def get_hourly_breakdown(self, days: int = 1) -> List[Dict[str, object]]:
        summary = self.get_summary(days)
        return build_hourly_category_breakdown(summary)

    def get_gantt_data(self, days: int = 1) -> Dict[str, object]:
        summary = self.get_summary(days)
        return build_gantt_data(summary)

    def get_heatmap_data(self, days: int = 1) -> Dict[str, object]:
        summary = self.get_summary(days)
        return build_heatmap_data(summary)

    def get_hourly_stats(self, days: int = 1) -> Dict[str, object]:
        """Unified visualization payload for hourly bars, gantt, and heatmap."""
        summary = self.get_summary(days)
        return build_visualization_data(summary)

    def get_dashboard_data(
        self,
        days: int = 1,
        activity_limit: int = 12,
        timeline_limit: int = 40,
        top_n_apps: int = 6,
    ) -> Dict[str, object]:
        end = datetime.now().astimezone()
        start = end - timedelta(days=days)
        client = self._get_client()

        try:
            summary = build_summary_range(start, end, client=client)
        except Exception as exc:
            return _error_response("query_failed", "查询数据失败", str(exc))

        if "error" in summary:
            return _error_response("missing_buckets", "缺少数据桶", str(summary["error"]))

        warnings: List[str] = []

        try:
            payload = build_dashboard_payload(
                summary=summary,
                start=start,
                end=end,
                top_n_apps=top_n_apps,
                activity_limit=activity_limit,
                timeline_limit=timeline_limit,
                client=client,
            )
        except Exception as exc:
            return _error_response("query_failed", "查询数据失败", str(exc))

        return {
            "ok": True,
            "error": None,
            **payload,
            "warnings": warnings,
        }

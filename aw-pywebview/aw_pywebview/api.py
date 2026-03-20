import os
import socket
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from aw_client import ActivityWatchClient

from .data import (
    build_activity_from_summary,
    build_input_stats_by_top_apps,
    build_summary,
    build_summary_range,
    build_timeline_from_summary,
)
from .report import generate_report_image


def _start_of_day() -> datetime:
    now = datetime.now().astimezone()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class AppApi:
    def __init__(self) -> None:
        self.client = ActivityWatchClient("aw-pywebview")

    def get_buckets(self) -> Dict[str, dict]:
        return self.client.get_buckets()

    def get_summary_today(self) -> Dict[str, object]:
        start = _start_of_day()
        end = datetime.now().astimezone()
        return build_summary_range(start, end, client=self.client)

    def generate_report_today(self) -> Optional[str]:
        """Generate a report for today and save it to the analytics folder."""
        summary = self.get_summary_today()
        if "error" in summary:
            return None
        
        # Get project root (relative to this file: aw_pywebview/api.py -> aw_pywebview -> aw-pywebview -> root)
        # Wait, if file is in aw_pywebview/api.py:
        # dirname(__file__) is aw_pywebview/
        # .. is aw-pywebview/
        # .. is root/
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        output_dir = os.path.join(project_root, "analytics")
        
        path = generate_report_image(summary, output_dir)
        return path

    def get_summary(self, days: int = 1) -> Dict[str, object]:
        return build_summary(days=days, client=self.client)

    def get_activity(self, days: int = 1, limit: int = 20) -> List[Dict[str, object]]:
        summary = self.get_summary(days)
        return build_activity_from_summary(summary, limit=limit)

    def get_timeline(self, days: int = 1, limit: int = 200) -> List[Dict[str, object]]:
        summary = self.get_summary(days)
        return build_timeline_from_summary(summary, limit=limit)

    def get_timeline_today(self, limit: int = 200) -> List[Dict[str, object]]:
        summary = self.get_summary_today()
        return build_timeline_from_summary(summary, limit=limit)

    def get_input_top_apps(self, days: int = 1, top_n: int = 6) -> List[Dict[str, object]]:
        end = datetime.now().astimezone()
        start = end - timedelta(days=days)
        summary = build_summary_range(start, end, client=self.client)
        if "error" in summary:
            return []
        return build_input_stats_by_top_apps(
            summary=summary,
            start=start,
            end=end,
            top_n=top_n,
            client=self.client,
        )

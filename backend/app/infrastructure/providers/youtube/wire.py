"""Stable query construction for the YouTube Data and Analytics APIs."""

from __future__ import annotations

from datetime import date

from app.domain.metrics import MetricId

YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_ANALYTICS_REPORTS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"

YOUTUBE_DAILY_METRICS = (
    MetricId.VIEWS.value,
    "likes",
    "comments",
    "shares",
    "subscribersGained",
    "subscribersLost",
)


def channel_query(channel_id: str) -> dict[str, str]:
    if not channel_id.strip():
        raise ValueError("provider_account_id_required")
    return {
        "part": "id,snippet,statistics",
        "id": channel_id,
        "maxResults": "1",
    }


def daily_metrics_query(*, since: date, until: date) -> dict[str, str]:
    if until < since:
        raise ValueError("metric_range_invalid")
    return {
        "ids": "channel==MINE",
        "startDate": since.isoformat(),
        "endDate": until.isoformat(),
        "metrics": ",".join(YOUTUBE_DAILY_METRICS),
        "dimensions": "day",
        "sort": "day",
    }


__all__ = [
    "YOUTUBE_ANALYTICS_REPORTS_URL",
    "YOUTUBE_CHANNELS_URL",
    "YOUTUBE_DAILY_METRICS",
    "channel_query",
    "daily_metrics_query",
]

"""Stable query construction for the YouTube Data and Analytics APIs."""

from __future__ import annotations

from datetime import date

from app.domain.metrics import MetricId

YOUTUBE_CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_PLAYLIST_ITEMS_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
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


def uploads_playlist_query(channel_id: str) -> dict[str, str]:
    if not channel_id.strip():
        raise ValueError("provider_account_id_required")
    return {
        "part": "id,contentDetails",
        "id": channel_id,
        "maxResults": "1",
    }


def playlist_items_query(
    playlist_id: str, *, cursor: str | None = None
) -> dict[str, str]:
    if not playlist_id.strip():
        raise ValueError("provider_playlist_id_required")
    query = {
        "part": "contentDetails",
        "playlistId": playlist_id,
        "maxResults": "50",
    }
    if cursor:
        query["pageToken"] = cursor
    return query


def videos_query(video_ids: tuple[str, ...]) -> dict[str, str]:
    if not video_ids or len(video_ids) > 50 or any(not value.strip() for value in video_ids):
        raise ValueError("provider_video_ids_invalid")
    return {
        "part": "id,snippet,statistics",
        "id": ",".join(video_ids),
        "maxResults": str(len(video_ids)),
    }


def comment_threads_query(
    video_id: str, *, cursor: str | None = None
) -> dict[str, str]:
    if not video_id.strip():
        raise ValueError("provider_video_id_required")
    query = {
        "part": "id,snippet",
        "videoId": video_id,
        "maxResults": "100",
        "order": "time",
        "textFormat": "plainText",
    }
    if cursor:
        query["pageToken"] = cursor
    return query


__all__ = [
    "YOUTUBE_ANALYTICS_REPORTS_URL",
    "YOUTUBE_CHANNELS_URL",
    "YOUTUBE_COMMENT_THREADS_URL",
    "YOUTUBE_DAILY_METRICS",
    "YOUTUBE_PLAYLIST_ITEMS_URL",
    "YOUTUBE_VIDEOS_URL",
    "channel_query",
    "comment_threads_query",
    "daily_metrics_query",
    "playlist_items_query",
    "uploads_playlist_query",
    "videos_query",
]

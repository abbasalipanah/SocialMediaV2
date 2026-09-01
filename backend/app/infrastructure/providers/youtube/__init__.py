"""YouTube Data and Analytics API adapter boundary."""

from .content import YouTubeContentReader
from .daily_metrics import (
    MAX_YOUTUBE_DAILY_WINDOW_DAYS,
    YOUTUBE_DAILY_METRICS,
    YouTubeDailyMetricsReader,
)
from .profile import YouTubeProfileReader
from .responses import YouTubeResponseError
from .transport import YouTubeHttpTransport, YouTubeTransportError
from .wire import (
    YOUTUBE_ANALYTICS_REPORTS_URL,
    YOUTUBE_CHANNELS_URL,
    YOUTUBE_PLAYLIST_ITEMS_URL,
    YOUTUBE_VIDEOS_URL,
    channel_query,
    daily_metrics_query,
    playlist_items_query,
    uploads_playlist_query,
    videos_query,
)

__all__ = [
    "MAX_YOUTUBE_DAILY_WINDOW_DAYS",
    "YOUTUBE_ANALYTICS_REPORTS_URL",
    "YOUTUBE_CHANNELS_URL",
    "YOUTUBE_DAILY_METRICS",
    "YOUTUBE_PLAYLIST_ITEMS_URL",
    "YOUTUBE_VIDEOS_URL",
    "YouTubeContentReader",
    "YouTubeDailyMetricsReader",
    "YouTubeHttpTransport",
    "YouTubeProfileReader",
    "YouTubeResponseError",
    "YouTubeTransportError",
    "channel_query",
    "daily_metrics_query",
    "playlist_items_query",
    "uploads_playlist_query",
    "videos_query",
]

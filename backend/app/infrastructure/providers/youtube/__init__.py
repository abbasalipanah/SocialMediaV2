"""YouTube Data and Analytics API adapter boundary."""

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
    channel_query,
    daily_metrics_query,
)

__all__ = [
    "MAX_YOUTUBE_DAILY_WINDOW_DAYS",
    "YOUTUBE_ANALYTICS_REPORTS_URL",
    "YOUTUBE_CHANNELS_URL",
    "YOUTUBE_DAILY_METRICS",
    "YouTubeDailyMetricsReader",
    "YouTubeHttpTransport",
    "YouTubeProfileReader",
    "YouTubeResponseError",
    "YouTubeTransportError",
    "channel_query",
    "daily_metrics_query",
]

"""YouTube Data and Analytics API adapter boundary."""

from .transport import YouTubeHttpTransport, YouTubeTransportError

__all__ = ["YouTubeHttpTransport", "YouTubeTransportError"]

"""External provider adapter boundaries."""

from app.application.ports import OAUTH_CHANNEL_PLATFORMS
from app.domain.platforms import PlatformId


def _oauth_platform(platform: PlatformId) -> PlatformId:
    if platform not in OAUTH_CHANNEL_PLATFORMS:
        raise ValueError("oauth_channel_platform_invalid")
    return platform


__all__ = ["_oauth_platform"]

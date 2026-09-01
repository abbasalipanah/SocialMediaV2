"""YouTube channel profile normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import ProfileSnapshot
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import (
    YouTubeResponseError,
    optional_count,
    optional_text,
    required_mapping,
    required_text,
    single_channel,
)


class YouTubeProfileReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def fetch_profile(self, account: ProviderAccount) -> ProfileSnapshot:
        if account.platform is not PlatformId.YOUTUBE:
            raise ValueError("provider_family_mismatch")
        channel = single_channel(self._fetch(account), channel_id=account.account_id)
        snippet = required_mapping(channel, "snippet")
        statistics = required_mapping(channel, "statistics")
        hidden_subscribers = statistics.get("hiddenSubscriberCount", False)
        if not isinstance(hidden_subscribers, bool):
            raise YouTubeResponseError("response_field_invalid")
        return ProfileSnapshot(
            account_id=account.account_id,
            display_name=required_text(snippet, "title"),
            handle=optional_text(snippet, "customUrl"),
            observed_at=self._clock(),
            metric_values={
                MetricId.FOLLOWERS: (
                    None
                    if hidden_subscribers
                    else optional_count(statistics, "subscriberCount")
                ),
                MetricId.MEDIA_COUNT: optional_count(statistics, "videoCount"),
            },
        )


__all__ = ["YouTubeProfileReader"]

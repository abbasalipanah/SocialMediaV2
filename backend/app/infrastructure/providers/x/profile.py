"""X authenticated-user profile normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import ProfileSnapshot
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import required_mapping, required_text


class XProfileReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def fetch_profile(self, account: ProviderAccount) -> ProfileSnapshot:
        if account.platform is not PlatformId.X:
            raise ValueError("provider_family_mismatch")
        user = required_mapping(self._fetch(account), "data")
        if required_text(user, "id") != account.account_id:
            raise ValueError("x_profile_account_mismatch")
        metrics = required_mapping(user, "public_metrics")
        return ProfileSnapshot(
            account_id=account.account_id,
            display_name=required_text(user, "name"),
            handle=f"@{required_text(user, 'username')}",
            observed_at=self._clock(),
            metric_values={
                MetricId.FOLLOWERS: _count(metrics, "followers_count"),
                MetricId.MEDIA_COUNT: _count(metrics, "tweet_count"),
            },
        )


def _count(payload: Mapping[str, object], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("x_profile_response_invalid")
    return value


__all__ = ["XProfileReader"]

"""TikTok profile fixture reader."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import ProfileSnapshot
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import TikTokResponseError, success_data


class TikTokProfileReader:
    def __init__(
        self,
        fetch: Callable[[str], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def fetch_profile(self, account: ProviderAccount) -> ProfileSnapshot:
        if account.platform is not PlatformId.TIKTOK:
            raise ValueError("provider_family_mismatch")
        data = success_data(self._fetch(account.account_id))
        business_id = _text(data, "business_id")
        if business_id != account.account_id:
            raise TikTokResponseError("provider_account_mismatch")
        handle = _optional_text(data, "username")
        return ProfileSnapshot(
            account_id=business_id,
            display_name=_text(data, "display_name"),
            handle=handle,
            observed_at=self._clock(),
            metric_values={MetricId.FOLLOWERS: _optional_count(data, "followers_count")},
        )


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TikTokResponseError("response_field_invalid")
    return value


def _optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TikTokResponseError("response_field_invalid")
    return value or None


def _optional_count(payload: Mapping[str, Any], key: str) -> int | None:
    value = payload.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TikTokResponseError("response_field_invalid")
    return value


__all__ = ["TikTokProfileReader"]

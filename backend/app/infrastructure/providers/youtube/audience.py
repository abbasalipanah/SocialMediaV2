"""Privacy-thresholded YouTube viewer demographics normalization."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.audience import AudienceSnapshot
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import YouTubeResponseError, report_rows

YOUTUBE_DEMOGRAPHICS_WINDOW_DAYS = 28
_AGE_GROUPS = {
    "age13-17",
    "age18-24",
    "age25-34",
    "age35-44",
    "age45-54",
    "age55-64",
    "age65-",
}
_GENDERS = {"female", "male", "user_specified"}


class YouTubeAudienceReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount, date, date], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def fetch_audience(self, account: ProviderAccount) -> AudienceSnapshot:
        if account.platform is not PlatformId.YOUTUBE:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock().astimezone(UTC)
        until = observed_at.date() - timedelta(days=1)
        since = until - timedelta(days=YOUTUBE_DEMOGRAPHICS_WINDOW_DAYS - 1)
        rows = report_rows(
            self._fetch(account, since, until),
            required_columns=("ageGroup", "gender", "viewerPercentage"),
        )
        ages: dict[str, float] = defaultdict(float)
        genders: dict[str, float] = defaultdict(float)
        combinations: dict[str, float] = {}
        for row in rows:
            age = row.get("ageGroup")
            gender = row.get("gender")
            percentage = _percentage(row.get("viewerPercentage"))
            if age not in _AGE_GROUPS or gender not in _GENDERS:
                raise YouTubeResponseError("analytics_demographics_invalid")
            key = f"{age}|{gender}"
            if key in combinations:
                raise YouTubeResponseError("analytics_demographics_invalid")
            combinations[key] = percentage
            ages[str(age)] += percentage
            genders[str(gender)] += percentage
        return AudienceSnapshot(
            account_id=account.account_id,
            observed_at=observed_at,
            metric_id=MetricId.VIEWER_PERCENTAGE,
            breakdowns=(
                {
                    "youtube_viewer_age": dict(ages),
                    "youtube_viewer_gender": dict(genders),
                    "youtube_viewer_age_gender": combinations,
                }
                if combinations
                else {}
            ),
        )


def _percentage(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise YouTubeResponseError("analytics_demographics_invalid")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise YouTubeResponseError("analytics_demographics_invalid") from exc
    if not 0 <= parsed <= 100:
        raise YouTubeResponseError("analytics_demographics_invalid")
    return parsed


__all__ = ["YOUTUBE_DEMOGRAPHICS_WINDOW_DAYS", "YouTubeAudienceReader"]

"""YouTube Analytics daily channel metric normalization."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import DailyMetricSnapshot
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import YouTubeResponseError, report_rows
from .wire import YOUTUBE_DAILY_METRICS

MAX_YOUTUBE_DAILY_WINDOW_DAYS = 31
_REQUIRED_COLUMNS = ("day", *YOUTUBE_DAILY_METRICS)


class YouTubeDailyMetricsReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount, date, date], Mapping[str, Any]],
    ) -> None:
        self._fetch = fetch

    def fetch_daily_metrics(
        self,
        account: ProviderAccount,
        *,
        since: date,
        until: date,
    ) -> tuple[DailyMetricSnapshot, ...]:
        if account.platform is not PlatformId.YOUTUBE:
            raise ValueError("provider_family_mismatch")
        if until < since or (until - since).days >= MAX_YOUTUBE_DAILY_WINDOW_DAYS:
            raise ValueError("metric_range_invalid")
        rows = report_rows(
            self._fetch(account, since, until),
            required_columns=_REQUIRED_COLUMNS,
        )
        snapshots: list[DailyMetricSnapshot] = []
        observed_days: set[date] = set()
        for row in rows:
            observed_on = _day(row.get("day"))
            if observed_on < since or observed_on > until or observed_on in observed_days:
                raise YouTubeResponseError("analytics_day_invalid")
            observed_days.add(observed_on)
            views = _number(row.get(MetricId.VIEWS.value))
            likes = _number(row.get("likes"))
            comments = _number(row.get("comments"))
            shares = _number(row.get("shares"))
            values: dict[MetricId, float | int | None] = {
                MetricId.VIEWS: views,
                MetricId.FOLLOWS: _number(row.get("subscribersGained")),
                MetricId.UNFOLLOWS: _number(row.get("subscribersLost")),
                MetricId.INTERACTIONS: (
                    likes + comments + shares
                    if likes is not None and comments is not None and shares is not None
                    else None
                ),
            }
            snapshots.append(
                DailyMetricSnapshot(
                    account_id=account.account_id,
                    observed_on=observed_on,
                    metric_values=values,
                )
            )
        return tuple(sorted(snapshots, key=lambda snapshot: snapshot.observed_on))


def _day(value: object) -> date:
    if not isinstance(value, str):
        raise YouTubeResponseError("analytics_day_invalid")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise YouTubeResponseError("analytics_day_invalid") from exc


def _number(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise YouTubeResponseError("analytics_metric_invalid")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise YouTubeResponseError("analytics_metric_invalid") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise YouTubeResponseError("analytics_metric_invalid")
    return parsed


__all__ = [
    "MAX_YOUTUBE_DAILY_WINDOW_DAYS",
    "YOUTUBE_DAILY_METRICS",
    "YouTubeDailyMetricsReader",
]

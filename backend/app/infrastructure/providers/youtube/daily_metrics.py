"""YouTube Analytics daily channel metric normalization."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import DailyMetricSnapshot
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import YouTubeResponseError, report_rows
from .transport import YouTubeTransportError
from .wire import (
    YOUTUBE_BREAKDOWN_DIMENSIONS,
    YOUTUBE_BREAKDOWN_METRICS,
    YOUTUBE_DAILY_METRICS,
)

MAX_YOUTUBE_DAILY_WINDOW_DAYS = 31
_REQUIRED_COLUMNS = ("day", *YOUTUBE_DAILY_METRICS)


class YouTubeDailyMetricsReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount, date, date], Mapping[str, Any]],
        fetch_breakdown: Callable[
            [ProviderAccount, date, date, str], Mapping[str, Any]
        ] | None = None,
    ) -> None:
        self._fetch = fetch
        self._fetch_breakdown = fetch_breakdown

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
        values_by_day: dict[date, dict[MetricId, float | int | None]] = {}
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
                MetricId.ENGAGED_VIEWS: _number(row.get("engagedViews")),
                MetricId.WATCH_TIME_MINUTES: _number(
                    row.get("estimatedMinutesWatched")
                ),
                MetricId.VIDEO_LIKES_DAILY: likes,
                MetricId.VIDEO_COMMENTS_DAILY: comments,
                MetricId.VIDEO_SHARES_DAILY: shares,
                MetricId.FOLLOWS: _number(row.get("subscribersGained")),
                MetricId.UNFOLLOWS: _number(row.get("subscribersLost")),
                MetricId.PLAYLIST_ADDITIONS: _number(
                    row.get("videosAddedToPlaylists")
                ),
                MetricId.PLAYLIST_REMOVALS: _number(
                    row.get("videosRemovedFromPlaylists")
                ),
                MetricId.INTERACTIONS: (
                    likes + comments + shares
                    if likes is not None and comments is not None and shares is not None
                    else None
                ),
            }
            values_by_day[observed_on] = values
        breakdowns_by_day = self._breakdowns(
            account,
            since=since,
            until=until,
            observed_days=observed_days,
        )
        return tuple(
            DailyMetricSnapshot(
                account_id=account.account_id,
                observed_on=observed_on,
                metric_values=values_by_day[observed_on],
                metric_breakdowns=breakdowns_by_day.get(observed_on, {}),
            )
            for observed_on in sorted(values_by_day)
        )

    def _breakdowns(
        self,
        account: ProviderAccount,
        *,
        since: date,
        until: date,
        observed_days: set[date],
    ) -> dict[
        date,
        dict[MetricId, dict[str, dict[str, float | int]]],
    ]:
        by_day: dict[
            date,
            dict[MetricId, dict[str, dict[str, float | int]]],
        ] = defaultdict(dict)
        if self._fetch_breakdown is None:
            return by_day
        for provider_dimension, breakdown_key in YOUTUBE_BREAKDOWN_DIMENSIONS.items():
            try:
                payload = self._fetch_breakdown(
                    account,
                    since,
                    until,
                    provider_dimension,
                )
            except YouTubeTransportError:
                # Optional reports can be withheld or unsupported for a
                # particular channel. Preserve core daily analytics and let
                # the dashboard report only the breakdowns actually returned.
                continue
            rows = report_rows(
                payload,
                required_columns=(
                    "day",
                    provider_dimension,
                    *YOUTUBE_BREAKDOWN_METRICS,
                ),
            )
            seen: set[tuple[date, str]] = set()
            for row in rows:
                observed_on = _day(row.get("day"))
                raw_value = row.get(provider_dimension)
                if (
                    observed_on not in observed_days
                    or not isinstance(raw_value, str)
                    or not raw_value.strip()
                    or (observed_on, raw_value) in seen
                ):
                    raise YouTubeResponseError("analytics_breakdown_invalid")
                seen.add((observed_on, raw_value))
                dimension_value = raw_value.strip()
                for metric_id, source_name in (
                    (MetricId.VIEWS, MetricId.VIEWS.value),
                    (MetricId.WATCH_TIME_MINUTES, "estimatedMinutesWatched"),
                ):
                    value = _number(row.get(source_name))
                    if value is None:
                        continue
                    by_metric = by_day[observed_on].setdefault(metric_id, {})
                    by_dimension = by_metric.setdefault(breakdown_key, {})
                    by_dimension[dimension_value] = value
        return by_day


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

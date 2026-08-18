"""TikTok Business account daily insight normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import DailyMetricSnapshot
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import TikTokResponseError, success_data

TIKTOK_DAILY_FIELDS = (
    "followers_count",
    "video_views",
    "unique_video_views",
    MetricId.PROFILE_VIEWS.value,
    "likes",
    "comments",
    "shares",
)
MAX_TIKTOK_DAILY_WINDOW_DAYS = 30

_ACCOUNT_METRICS = {
    "followers_count": MetricId.FOLLOWERS,
    "video_views": MetricId.VIEWS,
    "unique_video_views": MetricId.REACH,
    MetricId.PROFILE_VIEWS.value: MetricId.PROFILE_VIEWS,
}
TIKTOK_DAILY_METRIC_IDS = (
    *_ACCOUNT_METRICS.values(),
    MetricId.INTERACTIONS,
)


class TikTokDailyMetricsReader:
    def __init__(
        self,
        fetch: Callable[[str, date, date], Mapping[str, Any]],
    ) -> None:
        self._fetch = fetch

    def fetch_daily_metrics(
        self,
        account: ProviderAccount,
        *,
        since: date,
        until: date,
    ) -> tuple[DailyMetricSnapshot, ...]:
        if account.platform is not PlatformId.TIKTOK:
            raise ValueError("provider_family_mismatch")
        if until < since or (until - since).days >= MAX_TIKTOK_DAILY_WINDOW_DAYS:
            raise ValueError("metric_range_invalid")
        data = success_data(self._fetch(account.account_id, since, until))
        daily = _daily_rows(data, since=since, until=until)
        snapshots: list[DailyMetricSnapshot] = []
        for observed_on, fields in sorted(daily.items()):
            values = {
                metric_id: fields.get(source_field)
                for source_field, metric_id in _ACCOUNT_METRICS.items()
                if source_field in fields
            }
            components = tuple(fields.get(field) for field in ("likes", "comments", "shares"))
            if all(value is not None for value in components):
                values[MetricId.INTERACTIONS] = sum(components)  # type: ignore[arg-type]
            if values:
                snapshots.append(
                    DailyMetricSnapshot(
                        account_id=account.account_id,
                        observed_on=observed_on,
                        metric_values=values,
                    )
                )
        return tuple(snapshots)


def _daily_rows(
    payload: Mapping[str, Any],
    *,
    since: date,
    until: date,
) -> dict[date, dict[str, float]]:
    daily: dict[date, dict[str, float]] = {}
    raw_rows = payload.get("metrics")
    if raw_rows is not None:
        if not isinstance(raw_rows, list):
            raise TikTokResponseError("daily_metrics_shape_invalid")
        for row in raw_rows:
            if not isinstance(row, Mapping):
                raise TikTokResponseError("daily_metrics_shape_invalid")
            observed_on = _row_date(row)
            if observed_on is None or observed_on < since or observed_on > until:
                continue
            for field in TIKTOK_DAILY_FIELDS:
                if field in row and (value := _number(row.get(field))) is not None:
                    daily.setdefault(observed_on, {})[field] = value
    for field in TIKTOK_DAILY_FIELDS:
        for observed_on, value in _field_series(
            payload.get(field),
            since=since,
            until=until,
        ):
            daily.setdefault(observed_on, {}).setdefault(field, value)
    return daily


def _field_series(
    raw: object,
    *,
    since: date,
    until: date,
) -> tuple[tuple[date, float], ...]:
    if isinstance(raw, Mapping):
        rows: list[tuple[date, float]] = []
        for raw_day, raw_value in raw.items():
            observed_on = _parse_date(raw_day)
            value = _number(raw_value)
            if observed_on is not None and since <= observed_on <= until and value is not None:
                rows.append((observed_on, value))
        return tuple(rows)
    if isinstance(raw, list):
        rows = []
        for item in raw:
            if not isinstance(item, Mapping):
                raise TikTokResponseError("daily_metrics_shape_invalid")
            observed_on = _row_date(item)
            value = _number(item.get("value"))
            if observed_on is not None and since <= observed_on <= until and value is not None:
                rows.append((observed_on, value))
        return tuple(rows)
    value = _number(raw)
    return ((until, value),) if value is not None and since == until else ()


def _row_date(row: Mapping[str, Any]) -> date | None:
    for field in ("date", "day", "stat_time_day", "timestamp"):
        if field in row and (parsed := _parse_date(row.get(field))) is not None:
            return parsed
    return None


def _parse_date(value: object) -> date | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC).date()
        except (OverflowError, OSError, ValueError):
            return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def _number(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, int | float | str):
        raise TikTokResponseError("daily_metric_value_invalid")
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise TikTokResponseError("daily_metric_value_invalid") from None
    if parsed == -1:
        return None
    if parsed < 0:
        raise TikTokResponseError("daily_metric_value_invalid")
    return parsed


__all__ = [
    "TIKTOK_DAILY_FIELDS",
    "TIKTOK_DAILY_METRIC_IDS",
    "MAX_TIKTOK_DAILY_WINDOW_DAYS",
    "TikTokDailyMetricsReader",
]

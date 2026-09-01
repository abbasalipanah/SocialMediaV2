"""Instagram daily total-value metric reader."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import DailyMetricSnapshot
from app.domain.metrics import (
    INSTAGRAM_DAILY_BREAKDOWNS,
    INSTAGRAM_DAILY_SOURCE_METRICS,
    MetricId,
)
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.fields import nonnegative_int_or_none
from app.infrastructure.providers.meta.transport import MetaTransport, MetaTransportError


class InstagramDailyMetricsReader:
    def __init__(self, transport: MetaTransport) -> None:
        self._transport = transport

    def fetch_daily_metrics(
        self,
        account: ProviderAccount,
        *,
        since: date,
        until: date,
    ) -> tuple[DailyMetricSnapshot, ...]:
        if account.platform is not PlatformId.INSTAGRAM:
            raise ValueError("provider_family_mismatch")
        if until < since:
            raise ValueError("metric_range_invalid")
        rows: list[DailyMetricSnapshot] = []
        for day in _days(since, until):
            values: dict[MetricId, int | None] = {}
            metric_breakdowns: dict[MetricId, dict[str, dict[str, int]]] = {}
            day_until = day + timedelta(days=1)
            source_fields = tuple(
                source_field for source_field, _metric_id in INSTAGRAM_DAILY_SOURCE_METRICS
            )
            try:
                payload = self._transport.get(
                    f"{account.account_id}/insights",
                    {
                        "metric": ",".join(source_fields),
                        "period": "day",
                        "metric_type": "total_value",
                        "since": day.isoformat(),
                        "until": day_until.isoformat(),
                    },
                )
            except MetaTransportError as exc:
                if exc.status_code != 400:
                    raise
                # Metric eligibility can vary by account. Preserve the old
                # one-metric isolation only for a rejected batch; healthy
                # accounts use one request instead of five per day.
                payload = None
            for source_field, metric_id in INSTAGRAM_DAILY_SOURCE_METRICS:
                if payload is not None:
                    values[metric_id] = _total_value(payload, source_field)
                    continue
                try:
                    single_payload = self._transport.get(
                        f"{account.account_id}/insights",
                        {
                            "metric": source_field,
                            "period": "day",
                            "metric_type": "total_value",
                            "since": day.isoformat(),
                            "until": day_until.isoformat(),
                        },
                    )
                except MetaTransportError as exc:
                    if exc.status_code == 400:
                        continue
                    raise
                metric_value = _total_value(single_payload, source_field)
                values[metric_id] = metric_value
            breakdown_metrics = (MetricId.REACH, MetricId.VIEWS)
            for breakdown_key in INSTAGRAM_DAILY_BREAKDOWNS:
                try:
                    breakdown_payload = self._transport.get(
                        f"{account.account_id}/insights",
                        {
                            "metric": ",".join(
                                metric_id.value for metric_id in breakdown_metrics
                            ),
                            "period": "day",
                            "metric_type": "total_value",
                            "breakdown": breakdown_key,
                            "since": day.isoformat(),
                            "until": day_until.isoformat(),
                        },
                    )
                except MetaTransportError as exc:
                    if exc.status_code == 400:
                        continue
                    raise
                for metric_id in breakdown_metrics:
                    breakdown_values = _breakdown_values(
                        breakdown_payload,
                        source_field=metric_id.value,
                        breakdown_key=breakdown_key,
                    )
                    if breakdown_values:
                        metric_breakdowns.setdefault(metric_id, {})[
                            breakdown_key
                        ] = breakdown_values
            try:
                follow_payload = self._transport.get(
                    f"{account.account_id}/insights",
                    {
                        "metric": "follows_and_unfollows",
                        "period": "day",
                        "metric_type": "total_value",
                        "breakdown": "follow_type",
                        "since": day.isoformat(),
                        "until": day_until.isoformat(),
                    },
                )
            except MetaTransportError as exc:
                if exc.status_code != 400:
                    raise
                follow_values: dict[str, int] = {}
            else:
                follow_values = _follow_type_values(follow_payload)
            follows = follow_values.get("FOLLOWER")
            unfollows = follow_values.get("NON_FOLLOWER")
            values[MetricId.FOLLOWS] = follows
            values[MetricId.NEW_FOLLOWERS] = follows
            values[MetricId.UNFOLLOWS] = unfollows
            values[MetricId.FOLLOWERS_NET] = (
                follows - unfollows
                if follows is not None and unfollows is not None
                else None
            )
            rows.append(
                DailyMetricSnapshot(
                    account_id=account.account_id,
                    observed_on=day,
                    metric_values=values,
                    metric_breakdowns=metric_breakdowns,
                )
            )
        return tuple(rows)


def _total_value(payload: Mapping[str, object], source_field: str) -> int | None:
    raw_data = payload.get("data") or []
    if not isinstance(raw_data, list):
        raise ValueError("provider_daily_metric_shape_invalid")
    for item in raw_data:
        if not isinstance(item, Mapping) or item.get("name") != source_field:
            continue
        total = item.get("total_value")
        if not isinstance(total, Mapping):
            return None
        return nonnegative_int_or_none({"value": total.get("value")}, "value")
    return None


def _follow_type_values(payload: Mapping[str, object]) -> dict[str, int]:
    values = _breakdown_values(
        payload,
        source_field="follows_and_unfollows",
        breakdown_key="follow_type",
    )
    if not _breakdown_dimension_reported(
        payload,
        source_field="follows_and_unfollows",
        breakdown_key="follow_type",
    ):
        return values
    # Meta represents a completed day with no follower events as a valid
    # follow_type breakdown without a results array. It can likewise omit the
    # zero-valued side of a sparse breakdown. These are real zeroes, not an
    # unavailable metric; leaving them as None breaks the exact follower-total
    # reconstruction at that day.
    return {
        "FOLLOWER": values.get("FOLLOWER", 0),
        "NON_FOLLOWER": values.get("NON_FOLLOWER", 0),
    }


def _breakdown_dimension_reported(
    payload: Mapping[str, object],
    *,
    source_field: str,
    breakdown_key: str,
) -> bool:
    raw_data = payload.get("data") or []
    if not isinstance(raw_data, list):
        raise ValueError("provider_daily_metric_shape_invalid")
    for item in raw_data:
        if not isinstance(item, Mapping) or item.get("name") != source_field:
            continue
        total = item.get("total_value")
        if not isinstance(total, Mapping):
            return False
        breakdowns = total.get("breakdowns") or []
        if not isinstance(breakdowns, list):
            raise ValueError("provider_daily_metric_shape_invalid")
        return any(
            isinstance(breakdown, Mapping)
            and breakdown.get("dimension_keys") == [breakdown_key]
            for breakdown in breakdowns
        )
    return False


def _breakdown_values(
    payload: Mapping[str, object],
    *,
    source_field: str,
    breakdown_key: str,
) -> dict[str, int]:
    raw_data = payload.get("data") or []
    if not isinstance(raw_data, list):
        raise ValueError("provider_daily_metric_shape_invalid")
    for item in raw_data:
        if not isinstance(item, Mapping) or item.get("name") != source_field:
            continue
        total = item.get("total_value")
        if not isinstance(total, Mapping):
            return {}
        breakdowns = total.get("breakdowns") or []
        if not isinstance(breakdowns, list):
            raise ValueError("provider_daily_metric_shape_invalid")
        for breakdown in breakdowns:
            if not isinstance(breakdown, Mapping):
                continue
            if breakdown.get("dimension_keys") != [breakdown_key]:
                continue
            results = breakdown.get("results") or []
            if not isinstance(results, list):
                raise ValueError("provider_daily_metric_shape_invalid")
            values: dict[str, int] = {}
            for result in results:
                if not isinstance(result, Mapping):
                    continue
                dimensions = result.get("dimension_values") or []
                if not isinstance(dimensions, list) or not dimensions:
                    continue
                parsed = nonnegative_int_or_none(
                    {"value": result.get("value")}, "value"
                )
                if parsed is not None:
                    values[str(dimensions[0])] = parsed
            return values
    return {}


def _days(since: date, until: date):
    cursor = since
    while cursor <= until:
        yield cursor
        cursor += timedelta(days=1)


__all__ = ["InstagramDailyMetricsReader"]

"""Instagram daily total-value metric reader."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import DailyMetricSnapshot
from app.domain.metrics import INSTAGRAM_DAILY_SOURCE_METRICS, MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.fields import nonnegative_int
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
            day_until = day + timedelta(days=1)
            for source_field, metric_id in INSTAGRAM_DAILY_SOURCE_METRICS:
                try:
                    payload = self._transport.get(
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
                metric_value = _total_value(payload, source_field)
                values[metric_id] = metric_value
            rows.append(
                DailyMetricSnapshot(
                    account_id=account.account_id,
                    observed_on=day,
                    metric_values=values,
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
        return nonnegative_int({"value": total.get("value")}, "value")
    return None


def _days(since: date, until: date):
    cursor = since
    while cursor <= until:
        yield cursor
        cursor += timedelta(days=1)


__all__ = ["InstagramDailyMetricsReader"]

"""Facebook daily account metric reader with V1 end-time alignment."""

from __future__ import annotations

from datetime import date, timedelta

from app.application.ports.platforms import ProviderAccount
from app.application.ports.platforms.profile import DailyMetricSnapshot
from app.domain.metrics import FACEBOOK_DAILY_SOURCE_METRICS, MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.fields import nonnegative_int
from app.infrastructure.providers.meta.transport import MetaTransport, MetaTransportError

FACEBOOK_MEDIA_VIEW_BREAKDOWN_METRICS = (
    MetricId.VIEWS_ORGANIC,
    MetricId.VIEWS_PAID,
)


def _metric_refused(error: MetaTransportError) -> bool:
    """True when the provider declined this one metric for this one account.

    Meta refuses an unsupported or ineligible metric either with a 4xx or with a
    200 carrying an error payload. Both mean "not this metric, for this Page" —
    not "this account is broken". Treating anything but a 400 as fatal cost the
    whole account: profile, content, comments and media were all abandoned
    because a single insight was unavailable.

    Rate limiting and server faults still propagate; those are systemic and the
    run must back off rather than record a false empty result.
    """
    if error.retryable:
        return False
    status = error.status_code
    return status is None or 400 <= status < 500 or status == 200


class FacebookDailyMetricsReader:
    def __init__(self, transport: MetaTransport) -> None:
        self._transport = transport

    def fetch_daily_metrics(
        self,
        account: ProviderAccount,
        *,
        since: date,
        until: date,
    ) -> tuple[DailyMetricSnapshot, ...]:
        if account.platform is not PlatformId.FACEBOOK:
            raise ValueError("provider_family_mismatch")
        if until < since:
            raise ValueError("metric_range_invalid")
        rows: list[DailyMetricSnapshot] = []
        for day in _days(since, until):
            values: dict[MetricId, int | None] = {}
            metric_breakdowns: dict[
                MetricId,
                dict[str, dict[str, int]],
            ] = {}
            request_day = day + timedelta(days=1)
            for source_field, metric_id in FACEBOOK_DAILY_SOURCE_METRICS:
                try:
                    page = self._transport.page(
                        f"{account.account_id}/insights",
                        {
                            "metric": source_field,
                            "period": "day",
                            "since": request_day.isoformat(),
                            "until": request_day.isoformat(),
                        },
                    )
                except MetaTransportError as exc:
                    if _metric_refused(exc):
                        continue
                    raise
                metric_value = _first_value(page.items, source_field)
                if metric_id not in values or (
                    values[metric_id] is None and metric_value is not None
                ):
                    values[metric_id] = metric_value
            try:
                source_values = _media_view_source_values(
                    self._transport.page(
                        f"{account.account_id}/insights",
                        {
                            "metric": "page_media_view",
                            "period": "day",
                            "since": request_day.isoformat(),
                            "until": request_day.isoformat(),
                            "breakdown": "is_from_ads",
                        },
                    ).items
                )
            except MetaTransportError as exc:
                if not _metric_refused(exc):
                    raise
                source_values = {}
            if source_values:
                metric_breakdowns[MetricId.VIEWS] = {
                    "is_from_ads": source_values,
                }
                if "Organic" in source_values:
                    values[MetricId.VIEWS_ORGANIC] = source_values["Organic"]
                if "Paid" in source_values:
                    values[MetricId.VIEWS_PAID] = source_values["Paid"]
                if values.get(MetricId.VIEWS) is None:
                    values[MetricId.VIEWS] = sum(source_values.values())
            rows.append(
                DailyMetricSnapshot(
                    account_id=account.account_id,
                    observed_on=day,
                    metric_values=values,
                    metric_breakdowns=metric_breakdowns,
                )
            )
        return tuple(rows)


def _first_value(items, source_field: str) -> int | None:
    for item in items:
        if item.get("name") != source_field:
            continue
        raw_values = item.get("values") or []
        if not isinstance(raw_values, list) or not raw_values:
            return None
        row = raw_values[0]
        if not isinstance(row, dict):
            return None
        raw_value = row.get("value")
        if isinstance(raw_value, dict):
            numeric = [value for value in raw_value.values() if isinstance(value, int | float)]
            raw_value = sum(numeric)
        return nonnegative_int({"value": raw_value}, "value")
    return None


def _media_view_source_values(items) -> dict[str, int]:
    values: dict[str, int] = {}
    for item in items:
        if item.get("name") != "page_media_view":
            continue
        raw_values = item.get("values") or []
        if not isinstance(raw_values, list):
            raise ValueError("provider_daily_metric_shape_invalid")
        for row in raw_values:
            if not isinstance(row, dict):
                raise ValueError("provider_daily_metric_shape_invalid")
            raw_bucket = str(row.get("is_from_ads") or "").strip()
            label = "Paid" if raw_bucket == "1" else "Organic" if raw_bucket == "0" else None
            if label is None:
                continue
            raw_value = row.get("value")
            if isinstance(raw_value, dict):
                raw_value = sum(
                    value for value in raw_value.values() if isinstance(value, int | float)
                )
            parsed = nonnegative_int({"value": raw_value}, "value")
            if parsed is not None:
                values[label] = parsed
        break
    return values


def _days(since: date, until: date):
    cursor = since
    while cursor <= until:
        yield cursor
        cursor += timedelta(days=1)


__all__ = [
    "FACEBOOK_MEDIA_VIEW_BREAKDOWN_METRICS",
    "FacebookDailyMetricsReader",
]

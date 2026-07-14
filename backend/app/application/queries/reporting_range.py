"""Strict dashboard date-range resolution."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from app.domain.reporting import ReportingRange

RANGE_DAYS = {
    "last_7_days": 7,
    "last_30_days": 30,
    "last_90_days": 90,
}


def resolve_reporting_range(
    *,
    range_key: str,
    start_on: date | None,
    end_on: date | None,
    now: datetime | None = None,
) -> ReportingRange:
    if (start_on is None) is not (end_on is None):
        raise ValueError("reporting_range_incomplete")
    if start_on is not None and end_on is not None:
        if end_on < start_on or (end_on - start_on).days > 365:
            raise ValueError("reporting_range_invalid")
        return ReportingRange(start_on=start_on, end_on=end_on, key="custom")
    try:
        days = RANGE_DAYS[range_key]
    except KeyError as exc:
        raise ValueError("reporting_range_unknown") from exc
    today = (now or datetime.now(UTC)).astimezone(UTC).date()
    end = today - timedelta(days=1)
    return ReportingRange(
        start_on=end - timedelta(days=days - 1),
        end_on=end,
        key=range_key,
    )


def previous_reporting_range(value: ReportingRange) -> ReportingRange:
    days = (value.end_on - value.start_on).days + 1
    end = value.start_on - timedelta(days=1)
    return ReportingRange(
        start_on=end - timedelta(days=days - 1),
        end_on=end,
        key="previous_period",
    )


__all__ = ["previous_reporting_range", "resolve_reporting_range"]

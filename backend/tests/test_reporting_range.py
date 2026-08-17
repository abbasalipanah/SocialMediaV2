from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.queries.reporting_range import (
    previous_reporting_range,
    resolve_reporting_range,
)
from app.domain.reporting import ReportingRange


@pytest.mark.parametrize(
    ("range_key", "expected_start", "expected_end"),
    [
        ("last_7_days", date(2026, 7, 8), date(2026, 7, 14)),
        ("last_30_days", date(2026, 6, 15), date(2026, 7, 14)),
        ("last_90_days", date(2026, 4, 16), date(2026, 7, 14)),
        ("last_365_days", date(2025, 7, 15), date(2026, 7, 14)),
    ],
)
def test_resolves_canonical_dashboard_ranges(
    range_key: str,
    expected_start: date,
    expected_end: date,
) -> None:
    resolved = resolve_reporting_range(
        range_key=range_key,
        start_on=None,
        end_on=None,
        now=datetime(2026, 7, 15, 12, tzinfo=UTC),
    )

    assert resolved.start_on == expected_start
    assert resolved.end_on == expected_end
    assert resolved.key == range_key


@pytest.mark.parametrize(
    ("current", "expected_start", "expected_end"),
    [
        (
            ReportingRange(date(2026, 7, 8), date(2026, 7, 14), "last_7_days"),
            date(2026, 7, 1),
            date(2026, 7, 7),
        ),
        (
            ReportingRange(date(2026, 6, 15), date(2026, 7, 14), "last_30_days"),
            date(2026, 5, 16),
            date(2026, 6, 14),
        ),
        (
            ReportingRange(date(2026, 4, 16), date(2026, 7, 14), "last_90_days"),
            date(2026, 1, 16),
            date(2026, 4, 15),
        ),
        (
            ReportingRange(date(2025, 7, 15), date(2026, 7, 14), "last_365_days"),
            date(2024, 7, 15),
            date(2025, 7, 14),
        ),
        (
            ReportingRange(date(2026, 7, 10), date(2026, 7, 14), "custom"),
            date(2026, 7, 5),
            date(2026, 7, 9),
        ),
    ],
)
def test_previous_reporting_range_is_adjacent_and_equal_length(
    current: ReportingRange,
    expected_start: date,
    expected_end: date,
) -> None:
    previous = previous_reporting_range(current)

    assert previous.start_on == expected_start
    assert previous.end_on == expected_end
    assert previous.key == "previous_period"
    assert (previous.end_on - previous.start_on) == (current.end_on - current.start_on)
    assert previous.end_on.toordinal() + 1 == current.start_on.toordinal()

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from app.application.queries.reporting_range import resolve_reporting_range


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

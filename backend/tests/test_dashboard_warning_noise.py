"""A platform the Brand never connected reports one fact, not fifteen."""

from __future__ import annotations

from app.application.queries.dashboards import platform_warnings
from app.domain.reporting import FreshnessStatus

NOISE = tuple(f"metric_unavailable:tiktok_metric_{index}" for index in range(15))


def test_unconnected_platform_reports_only_that() -> None:
    assert (
        platform_warnings(
            has_accounts=False,
            metric_warnings=NOISE,
            freshness_status=FreshnessStatus.NEVER_SYNCED,
        )
        == ["no_accounts"]
    )


def test_connected_platform_keeps_its_real_warnings() -> None:
    warnings = platform_warnings(
        has_accounts=True,
        metric_warnings=("metric_unavailable:reach",),
        freshness_status=FreshnessStatus.OUTDATED,
    )

    assert warnings == ["metric_unavailable:reach", "freshness:outdated"]


def test_fresh_connected_platform_stays_silent() -> None:
    assert (
        platform_warnings(
            has_accounts=True,
            metric_warnings=(),
            freshness_status=FreshnessStatus.FRESH,
        )
        == []
    )

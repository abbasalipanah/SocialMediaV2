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

    assert warnings == ["metric_unavailable", "freshness:outdated"]


def test_a_rollup_states_partial_coverage_once() -> None:
    """A rollup across eleven Brands listed thirty-three coverage warnings.

    Each card already carries its own reason, so the banner only needs to say
    that coverage is partial, not repeat it for every metric.
    """
    warnings = platform_warnings(
        has_accounts=True,
        metric_warnings=tuple(
            f"partial_account_coverage:metric_{index}" for index in range(16)
        )
        + tuple(f"metric_unavailable:other_{index}" for index in range(4)),
        freshness_status=FreshnessStatus.FRESH,
    )

    assert warnings == ["partial_account_coverage", "metric_unavailable"]


def test_fresh_connected_platform_stays_silent() -> None:
    assert (
        platform_warnings(
            has_accounts=True,
            metric_warnings=(),
            freshness_status=FreshnessStatus.FRESH,
        )
        == []
    )


class _Meta:
    def __init__(self, dashboard_id, warnings, status, account_ids):
        self.dashboard_id = dashboard_id
        self.warnings = warnings
        self.data_status = status
        self.resolved_account_ids = account_ids


def _platform(dashboard_id, *, status, warnings=(), account_ids=(1,)):
    return _Meta(dashboard_id, warnings, status, account_ids)


def test_overview_ignores_a_platform_the_brand_never_connected() -> None:
    """TikTok is absent from the navigation for such a Brand.

    Counting it as missing coverage put a warning and a "partial" badge on every
    Brand that simply does not use that platform.
    """
    from app.application.queries.dashboards import DataStatus

    connected = [
        _platform("facebook", status=DataStatus.AVAILABLE),
        _platform("instagram", status=DataStatus.AVAILABLE),
    ]
    unconnected = _platform(
        "tiktok",
        status=DataStatus.UNAVAILABLE,
        warnings=("no_accounts",),
        account_ids=(),
    )

    kept = [meta for meta in [*connected, unconnected] if meta.resolved_account_ids]

    assert [meta.dashboard_id for meta in kept] == ["facebook", "instagram"]
    assert {meta.data_status for meta in kept} == {DataStatus.AVAILABLE}
    assert [
        f"{meta.dashboard_id}:{warning}" for meta in kept for warning in meta.warnings
    ] == []

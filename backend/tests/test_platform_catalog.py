from __future__ import annotations

from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import CapabilityId, PlatformId
from app.domain.platforms.catalog import (
    PLATFORM_CATALOG,
    overview_platforms,
    platform_definition,
)


def test_platform_catalog_owns_every_platform_once() -> None:
    assert tuple(definition.platform for definition in PLATFORM_CATALOG) == tuple(PlatformId)
    assert len({definition.route for definition in PLATFORM_CATALOG}) == len(PlatformId)
    assert all(platform_definition(platform).platform is platform for platform in PlatformId)


def test_unreleased_platforms_do_not_enter_the_overview_early() -> None:
    assert overview_platforms() == (
        PlatformId.FACEBOOK,
        PlatformId.INSTAGRAM,
        PlatformId.TIKTOK,
    )


def test_new_platforms_have_fail_closed_dashboard_metric_contracts() -> None:
    catalog = bootstrap_metric_catalog()
    for platform in (PlatformId.X, PlatformId.LINKEDIN, PlatformId.YOUTUBE):
        assert catalog.require_capability(
            platform, MetricId.FOLLOWERS, CapabilityId.PROFILE
        ).source_field
        assert catalog.require_capability(
            platform, MetricId.VIEWS, CapabilityId.PROFILE
        ).source_field
        assert catalog.get(platform, MetricId.ENGAGEMENT_RATE).numerator_metric_id is (
            MetricId.INTERACTIONS
        )

from __future__ import annotations

from dataclasses import replace

import pytest

from app.application.queries.metrics import MetricQuery
from app.domain.metrics import (
    AggregationPolicy,
    DerivationOperator,
    MetricCatalogError,
    MetricId,
    SemanticType,
    ZeroDenominatorPolicy,
    bootstrap_metric_catalog,
)
from app.domain.platforms import CapabilityId, PlatformId


def test_bootstrap_catalog_covers_required_semantic_types() -> None:
    catalog = bootstrap_metric_catalog()
    semantics = {definition.semantic_type for definition in catalog.definitions()}
    assert semantics == {
        SemanticType.SNAPSHOT,
        SemanticType.FLOW,
        SemanticType.CUMULATIVE,
        SemanticType.RATIO,
    }

    followers = catalog.get(PlatformId.INSTAGRAM, MetricId.FOLLOWERS)
    assert followers.period_aggregation is AggregationPolicy.LAST_VALID

    views_total = catalog.get(PlatformId.TIKTOK, MetricId.VIDEO_VIEWS_TOTAL)
    views_change = catalog.get(PlatformId.TIKTOK, MetricId.VIDEO_VIEWS_CHANGE)
    assert views_total.semantic_type is SemanticType.CUMULATIVE
    assert views_total.period_aggregation is AggregationPolicy.LAST_VALID
    assert views_change.semantic_type is SemanticType.FLOW
    assert views_change.period_aggregation is AggregationPolicy.SUM

    for platform in (PlatformId.FACEBOOK, PlatformId.TIKTOK):
        follower_growth = catalog.get(platform, MetricId.NEW_FOLLOWERS)
        assert follower_growth.semantic_type is SemanticType.FLOW
        assert follower_growth.derived_from_metric_ids == (MetricId.FOLLOWERS,)
        assert follower_growth.derivation_operator is DerivationOperator.CUMULATIVE_DELTA

    rate = catalog.get(PlatformId.TIKTOK, MetricId.VIDEO_ENGAGEMENT_RATE)
    assert rate.period_aggregation is AggregationPolicy.RECOMPUTE
    assert rate.brand_rollup_aggregation is AggregationPolicy.RECOMPUTE
    assert rate.zero_denominator_policy is ZeroDenominatorPolicy.NOT_AVAILABLE


def test_catalog_preserves_missing_values_and_rejects_free_metric_ids() -> None:
    catalog = bootstrap_metric_catalog()
    values = catalog.validate_values(
        platform=PlatformId.FACEBOOK,
        capability=CapabilityId.PROFILE,
        values={MetricId.FOLLOWERS: None},
    )
    assert values[MetricId.FOLLOWERS] is None

    with pytest.raises(MetricCatalogError, match="metric_id_must_be_canonical"):
        catalog.validate_values(
            platform=PlatformId.FACEBOOK,
            capability=CapabilityId.PROFILE,
            values={"unknown_metric": 0},  # type: ignore[dict-item]
        )


def test_catalog_rejects_wrong_platform_or_capability() -> None:
    catalog = bootstrap_metric_catalog()
    with pytest.raises(MetricCatalogError, match="metric_not_registered"):
        catalog.get(PlatformId.FACEBOOK, MetricId.VIDEO_VIEWS_TOTAL)
    with pytest.raises(MetricCatalogError, match="metric_capability_mismatch"):
        catalog.validate_values(
            platform=PlatformId.TIKTOK,
            capability=CapabilityId.PROFILE,
            values={MetricId.VIDEO_VIEWS_TOTAL: 100},
        )


def test_definition_invariants_fail_closed() -> None:
    catalog = bootstrap_metric_catalog()
    snapshot = catalog.get(PlatformId.FACEBOOK, MetricId.FOLLOWERS)
    with pytest.raises(MetricCatalogError, match="total_metric_period_aggregation_invalid"):
        replace(snapshot, period_aggregation=AggregationPolicy.SUM)

    ratio = catalog.get(PlatformId.TIKTOK, MetricId.VIDEO_ENGAGEMENT_RATE)
    with pytest.raises(MetricCatalogError, match="ratio_zero_denominator_policy_missing"):
        replace(ratio, zero_denominator_policy=ZeroDenominatorPolicy.NOT_APPLICABLE)


def test_metric_queries_are_catalog_validated_at_construction() -> None:
    catalog = bootstrap_metric_catalog()
    query = MetricQuery(
        catalog=catalog,
        platform=PlatformId.TIKTOK,
        metric_ids=(MetricId.VIDEO_VIEWS_TOTAL, MetricId.VIDEO_VIEWS_CHANGE),
    )
    assert query.metric_ids == (
        MetricId.VIDEO_VIEWS_TOTAL,
        MetricId.VIDEO_VIEWS_CHANGE,
    )

    with pytest.raises(MetricCatalogError, match="metric_not_registered"):
        MetricQuery(
            catalog=catalog,
            platform=PlatformId.FACEBOOK,
            metric_ids=(MetricId.VIDEO_VIEWS_TOTAL,),
        )
    with pytest.raises(MetricCatalogError, match="metric_id_must_be_canonical"):
        MetricQuery(
            catalog=catalog,
            platform=PlatformId.FACEBOOK,
            metric_ids=("followers",),  # type: ignore[arg-type]
        )

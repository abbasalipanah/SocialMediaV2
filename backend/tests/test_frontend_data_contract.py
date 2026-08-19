from __future__ import annotations

import json
import re
from dataclasses import fields
from pathlib import Path

from app.application.ports.persistence import ContentRecord
from app.application.ports.reporting import ReportingContent
from app.application.queries.dashboard_aggregation import audience_capabilities
from app.application.queries.dashboards import OVERVIEW_METRIC_IDS
from app.domain.metrics import (
    FACEBOOK_DAILY_SOURCE_METRICS,
    INSTAGRAM_DAILY_SOURCE_METRICS,
    MetricId,
    bootstrap_metric_catalog,
)
from app.domain.platforms import PlatformId
from app.domain.reporting import (
    AvailabilityStatus,
    DashboardContent,
    DashboardStoryItem,
    PlatformDashboard,
)
from app.infrastructure.providers.meta.audience import (
    FACEBOOK_AUDIENCE_BREAKDOWN_KEYS,
    INSTAGRAM_AUDIENCE_METRICS,
)
from app.infrastructure.providers.meta.facebook.daily_metrics import (
    FACEBOOK_MEDIA_VIEW_BREAKDOWN_METRICS,
)
from app.infrastructure.providers.meta.instagram.content_insights import map_content_insights
from app.infrastructure.providers.tiktok.accounts import TIKTOK_DAILY_METRIC_IDS
from app.infrastructure.providers.tiktok.accounts.audience import AUDIENCE_FIELDS
from scripts.import_legacy_brand import AUDIENCE_METRIC_MAP, CANONICAL_METRICS

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = REPOSITORY_ROOT / "docs/contracts/social-media-v2-frontend-data-matrix.json"
CAPABILITY_PATH = REPOSITORY_ROOT / "docs/contracts/social-media-v2-provider-capabilities.json"


def _matrix() -> dict[str, object]:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def _capabilities() -> dict[str, object]:
    return json.loads(CAPABILITY_PATH.read_text(encoding="utf-8"))


def _metric_literals(paths: list[str]) -> set[str]:
    canonical = {metric_id.value for metric_id in MetricId}
    literals: set[str] = set()
    for relative_path in paths:
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")
        literals.update(re.findall(r'["\']([a-z][a-z0-9_]*)["\']', source))
    return literals & canonical


def test_every_frontend_metric_literal_has_an_explicit_backend_route() -> None:
    contract = _matrix()
    sources = contract["metric_sources"]
    metrics = contract["metrics"]
    catalog = bootstrap_metric_catalog()

    for platform_name in ("facebook", "instagram", "tiktok"):
        platform = PlatformId(platform_name)
        row = metrics[platform_name]
        consumed = set(row["consumed_metric_ids"])
        assert _metric_literals(sources[platform_name]) == consumed

        routed_groups = (
            set(row["provider_native"]),
            set(row["backend_derived"]),
            set(row["provider_limited_snapshot"]),
            set(row["aliases"]),
        )
        assert set.union(*routed_groups) == consumed
        assert sum(len(group) for group in routed_groups) == len(consumed)

        for metric_id in consumed - set(row["aliases"]):
            catalog.get(platform, MetricId(metric_id))
        for target in row["aliases"].values():
            catalog.get(platform, MetricId(target))
        for metric_id in row["backend_derived"]:
            assert catalog.get(platform, MetricId(metric_id)).derivation_operator is not None

    overview = metrics["overview"]
    assert _metric_literals(sources["overview"]) == set(overview["consumed_metric_ids"])
    assert {metric_id.value for metric_id in OVERVIEW_METRIC_IDS} == set(
        overview["overview_aggregates"]
    )
    for metric_id in overview["nested_platform_metrics"]:
        assert any(
            definition.metric_id is MetricId(metric_id) for definition in catalog.definitions()
        )


def test_metric_collection_statuses_are_evidence_backed() -> None:
    metrics = _matrix()["metrics"]
    native = {
        "facebook": {
            MetricId.FOLLOWERS.value,
            *(metric_id.value for _, metric_id in FACEBOOK_DAILY_SOURCE_METRICS),
            *(metric_id.value for metric_id in FACEBOOK_MEDIA_VIEW_BREAKDOWN_METRICS),
        },
        "instagram": {
            MetricId.FOLLOWERS.value,
            *(metric_id.value for _, metric_id in INSTAGRAM_DAILY_SOURCE_METRICS),
        },
        "tiktok": {
            MetricId.FOLLOWERS.value,
            MetricId.VIDEO_VIEWS_TOTAL.value,
            MetricId.VIDEO_LIKES_TOTAL.value,
            MetricId.VIDEO_COMMENTS_TOTAL.value,
            MetricId.VIDEO_SHARES_TOTAL.value,
            *(metric_id.value for metric_id in TIKTOK_DAILY_METRIC_IDS),
        },
    }
    legacy_importable = set(CANONICAL_METRICS)
    limited = _capabilities()["provider_limited_snapshot_metrics"]

    for platform_name in ("facebook", "instagram", "tiktok"):
        row = metrics[platform_name]
        assert set(row["provider_native"]).issubset(native[platform_name])
        assert set(row["provider_limited_snapshot"]).issubset(legacy_importable)
        assert set(row["provider_limited_snapshot"]) == set(limited[platform_name])


def test_every_frontend_dimension_has_a_declared_producer_or_unavailable_state() -> None:
    dimensions = _matrix()["dimensions"]
    provider_limited = _capabilities()["provider_limited_dimensions"]
    catalog = bootstrap_metric_catalog()
    facebook_allowed = set(catalog.get(PlatformId.FACEBOOK, MetricId.FOLLOWERS).allowed_breakdowns)
    instagram_allowed = set(
        catalog.get(PlatformId.INSTAGRAM, MetricId.FOLLOWERS).allowed_breakdowns
    )
    tiktok_allowed = set(catalog.get(PlatformId.TIKTOK, MetricId.FOLLOWERS).allowed_breakdowns)
    imported_dimensions = {dimension for _, dimension in AUDIENCE_METRIC_MAP.values()}

    for platform_name, rows in dimensions.items():
        consumers = [row["consumer"] for row in rows]
        assert len(consumers) == len(set(consumers))
        for row in rows:
            assert row["support"] in {
                "provider_native",
                "snapshot_compatible",
                "provider_unavailable",
                "demo_only_unavailable_runtime",
            }
            if row["support"] == "provider_native":
                allowed = {
                    "facebook": facebook_allowed,
                    "instagram": instagram_allowed,
                    "tiktok": tiktok_allowed,
                }[platform_name]
                assert set(row["backend_keys"]).issubset(allowed)
                if platform_name == "facebook":
                    assert set(row["backend_keys"]).issubset(FACEBOOK_AUDIENCE_BREAKDOWN_KEYS)
                elif platform_name == "instagram":
                    assert all(
                        any(key.startswith(metric) for metric in INSTAGRAM_AUDIENCE_METRICS)
                        for key in row["backend_keys"]
                    )
                else:
                    assert set(row["backend_keys"]).issubset(AUDIENCE_FIELDS)
            elif row["support"] == "snapshot_compatible":
                assert set(row["backend_keys"]).issubset(imported_dimensions)
            if row["support"] != "provider_native":
                assert row["consumer"] in provider_limited.get(platform_name, {})

    assert set(FACEBOOK_AUDIENCE_BREAKDOWN_KEYS).issubset(facebook_allowed)
    assert set(AUDIENCE_FIELDS).issubset(tiktok_allowed)
    local_demo = (REPOSITORY_ROOT / "backend/app/local_demo.py").read_text(encoding="utf-8")
    assert '"like_type"' in local_demo
    assert "like_type" not in FACEBOOK_AUDIENCE_BREAKDOWN_KEYS
    assert "like_type" not in imported_dimensions
    facebook = audience_capabilities(
        PlatformId.FACEBOOK,
        (),
        accounts_available=True,
    )
    assert facebook.age_gender is AvailabilityStatus.PROVIDER_UNAVAILABLE
    assert facebook.activity is AvailabilityStatus.PROVIDER_UNAVAILABLE
    assert map_content_insights({}, story=True)["sticker_taps"] is None
    assert provider_limited["instagram_story"]["Sticker Taps"] == "provider_unavailable"


def test_typed_content_and_story_fields_cross_every_backend_layer() -> None:
    typed = _matrix()["typed_contracts"]
    platform_fields = {field.name for field in fields(PlatformDashboard)}
    assert set(typed["platform_dashboard_fields"]).issubset(platform_fields)

    api_content_fields = {field.name for field in fields(DashboardContent)}
    api_story_fields = {field.name for field in fields(DashboardStoryItem)}
    persistence_fields = {field.name for field in fields(ContentRecord)}
    reporting_fields = {field.name for field in fields(ReportingContent)}

    for api_field, storage_field in typed["content_field_map"].items():
        assert api_field in api_content_fields
        assert storage_field in persistence_fields
        assert storage_field in reporting_fields
    for api_field, storage_field in typed["story_field_map"].items():
        assert api_field in api_story_fields
        assert storage_field in persistence_fields
        assert storage_field in reporting_fields

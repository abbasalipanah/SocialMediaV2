#!/usr/bin/env python3
"""Validate the Revision 6 / R3 single dashboard response contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
OPENAPI = ROOT / "docs/contracts/social-media-v2-openapi.json"
GENERATED = ROOT / "frontend/src/api/openapi.generated.ts"
ZOD = ROOT / "frontend/src/api/contracts.ts"
INSTAGRAM = ROOT / "frontend/src/features/instagram/InstagramPulseDashboard.tsx"
INSTAGRAM_STORIES = ROOT / "frontend/src/features/instagram/InstagramStoriesWorkspace.tsx"
R1_FIXTURE = ROOT / "docs/revision6/r1/canonical_dashboard_fixture.json"


class ContractError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def main() -> int:
    schema = json.loads(OPENAPI.read_text(encoding="utf-8"))
    components = schema["components"]["schemas"]
    platform_required = set(components["PlatformDashboard"]["required"])
    require(
        {
            "top_hashtags",
            "content_summary",
            "source_breakdown",
            "metric_methodology",
            "audience_capabilities",
            "stories",
        }.issubset(platform_required),
        "platform_dashboard_r3_fields_missing",
    )
    require(
        {"methodology", "availability_reason"}.issubset(
            components["DashboardMetric"]["required"]
        ),
        "metric_methodology_fields_missing",
    )
    require(
        {
            "views",
            "reach",
            "cover_candidates",
            "thumbnail_candidates",
            "media_url_candidates",
            "data_status",
        }.issubset(components["DashboardContent"]["required"]),
        "content_metric_or_media_fields_missing",
    )
    require(
        {
            "summary",
            "previous_summary",
            "trend",
            "navigation",
            "actions",
            "items",
            "data_status",
        } == set(components["DashboardStories"]["required"]),
        "structured_stories_contract_incomplete",
    )
    require(
        set(components["AvailabilityStatus"]["enum"])
        == {"available", "partial", "pending", "provider_unavailable", "unavailable"},
        "availability_status_enum_changed",
    )

    generated = GENERATED.read_text(encoding="utf-8")
    zod = ZOD.read_text(encoding="utf-8")
    instagram = INSTAGRAM.read_text(encoding="utf-8")
    instagram_stories = INSTAGRAM_STORIES.read_text(encoding="utf-8")
    for token in (
        "DashboardStories",
        "DashboardStoryItem",
        "DashboardSourceBreakdown",
        "DashboardAudienceCapabilities",
        "DashboardMetricMethodology",
    ):
        require(token in generated, f"generated_type_missing:{token}")
    for token in (
        "dashboardStoriesSchema",
        "dashboardSourceBreakdownSchema",
        "dashboardAudienceCapabilitiesSchema",
        "dashboardMetricMethodologySchema",
    ):
        require(token in zod, f"zod_schema_missing:{token}")
    require(
        "<InstagramStoriesWorkspace data={data}" in instagram
        and "DashboardStories" in instagram_stories
        and "DashboardStoryItem" in instagram_stories,
        "stories_not_using_typed_contract",
    )
    require(
        "storyRows(data)" not in instagram and "storyRows(data)" not in instagram_stories,
        "legacy_story_content_adapter_still_reachable",
    )

    fixture = json.loads(R1_FIXTURE.read_text(encoding="utf-8"))
    require(
        {item["id"] for item in fixture["consumers"]}
        == {"source_adapter_oracle", "v2_render_test"},
        "r1_fixture_consumers_changed",
    )

    sys.path.insert(0, str(BACKEND))
    from app.domain.metrics import (  # noqa: PLC0415
        DerivationOperator,
        MetricId,
        SemanticType,
        bootstrap_metric_catalog,
    )
    from app.domain.platforms import PlatformId  # noqa: PLC0415

    catalog = bootstrap_metric_catalog()
    for platform in (PlatformId.FACEBOOK, PlatformId.INSTAGRAM, PlatformId.TIKTOK):
        follower_flow = catalog.get(platform, MetricId.NEW_FOLLOWERS)
        require(
            follower_flow.semantic_type is SemanticType.FLOW,
            f"follower_flow_semantic_invalid:{platform.value}",
        )
    for platform in (PlatformId.FACEBOOK, PlatformId.TIKTOK):
        require(
            catalog.get(platform, MetricId.NEW_FOLLOWERS).derivation_operator
            is DerivationOperator.CUMULATIVE_DELTA,
            f"follower_delta_methodology_missing:{platform.value}",
        )

    print("R3 CONTRACT PASS: OpenAPI, generated TypeScript, Zod, Stories and metric semantics agree.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ContractError as exc:
        print(f"R3 CONTRACT FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

from __future__ import annotations

from datetime import date

from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.legacy_metrics import (
    KNOWN_LEGACY_BREAKDOWN_KEYS,
    KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM,
    LegacyMetricDisposition,
    LegacyMetricRow,
    legacy_metric_disposition,
    project_legacy_metrics,
)


def _row(
    platform: PlatformId,
    metric_id: str,
    value: float,
    *,
    account_id: int = 1,
    breakdown_key: str | None = None,
    breakdown_value: str | None = None,
) -> LegacyMetricRow:
    return LegacyMetricRow(
        account_id=account_id,
        brand_id="18",
        platform=platform,
        observed_on=date(2026, 7, 28),
        raw_metric_id=metric_id,
        value=value,
        breakdown_key=breakdown_key,
        breakdown_value=breakdown_value,
    )


def test_full_legacy_inventory_has_an_explicit_policy() -> None:
    pairs = {
        (platform, metric_id)
        for platform, metric_ids in KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM.items()
        for metric_id in metric_ids
    }
    assert len(pairs) == 168
    assert len({metric_id for _, metric_id in pairs}) == 124
    assert len(KNOWN_LEGACY_BREAKDOWN_KEYS) == 15
    for platform, metric_id in pairs:
        assert (
            legacy_metric_disposition(platform, metric_id, None)
            is not LegacyMetricDisposition.UNKNOWN
        )
    assert (
        legacy_metric_disposition(PlatformId.FACEBOOK, "future_provider_field", None)
        is LegacyMetricDisposition.UNKNOWN
    )


def test_unknown_and_dashboard_unused_metrics_do_not_crash_or_leak() -> None:
    projected = project_legacy_metrics(
        (
            _row(PlatformId.FACEBOOK, "frequency", 1.2),
            _row(PlatformId.FACEBOOK, "future_provider_field", 3),
        )
    )
    assert projected == ()


def test_audience_rows_are_normalized_without_mutating_raw_storage() -> None:
    projected = project_legacy_metrics(
        (
            _row(
                PlatformId.INSTAGRAM,
                "audience_country",
                61,
                breakdown_key="country",
                breakdown_value="TR",
            ),
            _row(
                PlatformId.TIKTOK,
                "audience_activity",
                8,
                account_id=2,
                breakdown_key="audience_activity",
                breakdown_value="monday|13",
            ),
        )
    )
    by_dimension = {row.breakdown_key: row for row in projected}
    assert by_dimension["audience_country"].metric_id is MetricId.FOLLOWERS
    assert by_dimension["audience_country"].breakdown_value == "TR"
    assert by_dimension["audience_activity"].metric_id is MetricId.FOLLOWERS
    assert by_dimension["audience_activity"].breakdown_value == "monday|13"


def test_tiktok_content_rows_build_daily_canonical_totals() -> None:
    projected = project_legacy_metrics(
        (
            _row(
                PlatformId.TIKTOK,
                "views",
                100,
                breakdown_key="content_id",
                breakdown_value="video-1",
            ),
            _row(
                PlatformId.TIKTOK,
                "views",
                50,
                breakdown_key="content_id",
                breakdown_value="video-2",
            ),
            _row(PlatformId.TIKTOK, "views", 25),
            _row(
                PlatformId.TIKTOK,
                "likes",
                7,
                breakdown_key="content_id",
                breakdown_value="video-1",
            ),
        )
    )
    by_id = {row.metric_id: row for row in projected}
    assert by_id[MetricId.VIEWS].value == 25
    assert by_id[MetricId.VIDEO_VIEWS_TOTAL].value == 150
    assert by_id[MetricId.VIDEO_LIKES_TOTAL].value == 7
    assert all(row.breakdown_key is None for row in projected)


def test_native_v2_total_wins_over_legacy_tiktok_projection() -> None:
    projected = project_legacy_metrics(
        (
            _row(
                PlatformId.TIKTOK,
                "views",
                100,
                breakdown_key="content_id",
                breakdown_value="video-1",
            ),
            _row(PlatformId.TIKTOK, "video_views_total", 900),
        )
    )
    assert len(projected) == 1
    assert projected[0].metric_id is MetricId.VIDEO_VIEWS_TOTAL
    assert projected[0].value == 900


def test_dashboard_breakdowns_are_typed_and_content_rows_are_not_duplicated() -> None:
    projected = project_legacy_metrics(
        (
            _row(PlatformId.FACEBOOK, "page_like_types_organic", 20),
            _row(PlatformId.FACEBOOK, "post_engagements_love", 4),
            _row(
                PlatformId.INSTAGRAM,
                "profile_activity",
                11,
                breakdown_key="activity_type",
                breakdown_value="profile_visits",
            ),
            _row(PlatformId.INSTAGRAM, "likes", 9),
            _row(
                PlatformId.INSTAGRAM,
                "likes",
                8,
                breakdown_key="content_id",
                breakdown_value="post-1",
            ),
        )
    )
    identities = {
        (row.metric_id, row.breakdown_key, row.breakdown_value): row.value
        for row in projected
    }
    assert identities[(MetricId.FOLLOWERS, "page_like_type", "organic")] == 20
    assert identities[(MetricId.INTERACTIONS, "reaction_type", "love")] == 4
    assert identities[(MetricId.TOTAL_ACTIONS, "profile_action", "profile_visits")] == 11
    assert identities[(MetricId.INTERACTIONS, "interaction_type", "likes")] == 9
    assert all(row.breakdown_value != "post-1" for row in projected)

"""Project the immutable legacy metric snapshot into the canonical dashboard contract.

The full legacy import intentionally preserves every ``metrics_daily`` row byte-for-byte.
The dashboard contract is narrower: metric identifiers are versioned ``MetricId`` values
and content-level values are served from the typed ``content_items`` projection.  This
module is the explicit, read-only boundary between those two representations.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.application.ports.reporting import ReportingMetric
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId


class LegacyMetricDisposition(StrEnum):
    DIRECT = "direct"
    AUDIENCE_BREAKDOWN = "audience_breakdown"
    DASHBOARD_BREAKDOWN = "dashboard_breakdown"
    TIKTOK_CONTENT_TOTAL = "tiktok_content_total"
    MIRRORED_IN_CONTENT = "mirrored_in_content"
    DASHBOARD_UNUSED = "dashboard_unused"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LegacyMetricRow:
    account_id: int
    brand_id: str
    platform: PlatformId
    observed_on: date
    raw_metric_id: str
    value: float
    breakdown_key: str | None
    breakdown_value: str | None


# Audited against the immutable 2026-08-10 full legacy snapshot.  Keeping the
# platform pairs explicit makes source drift visible in tests instead of silently
# dropping a newly introduced provider field.
KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM: dict[PlatformId, frozenset[str]] = {
    PlatformId.FACEBOOK: frozenset(
        {
            "audience_cities", "audience_city", "audience_countries",
            "audience_country", "audience_heatmap", "clicks", "comments",
            "engaged_users", MetricId.ENGAGEMENT_RATE.value, MetricId.FOLLOWERS.value,
            MetricId.FOLLOWERS_NET.value, MetricId.FOLLOWS.value, "frequency",
            "hashtag_comments", "hashtag_engagements",
            "hashtag_engagements_per_post", "hashtag_likes", "hashtag_posts",
            "hashtag_saves", "hashtag_shares", "impressions",
            "impressions_organic", "impressions_paid", MetricId.INTERACTIONS.value,
            "likes", MetricId.NEW_FOLLOWERS.value, "page_like_types",
            "page_like_types_organic", "page_like_types_paid", MetricId.PAGE_VIEWS.value,
            "post_engagements_angry",
            "post_engagements_care", "post_engagements_comment",
            "post_engagements_haha", "post_engagements_like",
            "post_engagements_love", "post_engagements_pride",
            "post_engagements_sad", "post_engagements_share",
            "post_engagements_thankful", "post_engagements_wow", MetricId.REACH.value,
            MetricId.REACH_ORGANIC.value, MetricId.REACH_PAID.value, "reaction_angry",
            "reaction_care",
            "reaction_haha", "reaction_like", "reaction_love", "reaction_pride",
            "reaction_sad", "reaction_thankful", "reaction_wow", MetricId.REACTIONS.value,
            "reactions_total", "replies", "saves", "shares", MetricId.TOTAL_ACTIONS.value,
            MetricId.UNFOLLOWS.value, "video_avg_time_ms", "video_view_time_ms",
            "video_views", MetricId.VIEWS.value, MetricId.VIEWS_ORGANIC.value,
            MetricId.VIEWS_PAID.value,
        }
    ),
    PlatformId.INSTAGRAM: frozenset(
        {
            "audience_city", "audience_country", "audience_gender_age",
            "audience_heatmap", "comments", "completion_rate", "contact_options",
            "content_count", "email_contacts", MetricId.ENGAGEMENT_RATE.value, "exits",
            "external_link_taps", MetricId.FOLLOWERS.value, MetricId.FOLLOWERS_NET.value,
            MetricId.FOLLOWING.value, MetricId.FOLLOWS.value, "frequency",
            "get_directions_clicks", "hashtag_comments",
            "hashtag_engagements", "hashtag_engagements_per_post", "hashtag_likes",
            "hashtag_posts", "hashtag_saves", "hashtag_shares",
            MetricId.INTERACTIONS.value, "likes", MetricId.MEDIA_COUNT.value,
            "navigation", MetricId.NEW_FOLLOWERS.value, "new_following",
            "phone_call_clicks", "post_engagement_rate", "post_frequency",
            "post_interactions", "post_reach", "post_views", "posts_count",
            "profile_activity", "profile_engagements", MetricId.PROFILE_VIEWS.value,
            "profile_visits", MetricId.REACH.value, "reach_non_ad",
            MetricId.REACH_ORGANIC.value, MetricId.REACH_PAID.value,
            MetricId.REACTIONS.value, "reel_engagement_rate", "reel_frequency",
            "reel_interactions", "reel_reach", "reel_views", "reels_count",
            "replies", "saves", "shares", "stories_count",
            "story_completion_rate", "story_engagement_rate", "story_exits",
            "story_follows", "story_frequency", "story_interactions",
            "story_navigation", "story_profile_visits", "story_reach",
            "story_replies", "story_shares", "story_swipe_forward",
            "story_taps_back", "story_taps_forward", "story_views",
            "swipe_forward", "taps_back", "taps_forward", "text_message_clicks",
            MetricId.UNFOLLOWS.value, MetricId.VIEWS.value,
            MetricId.VIEWS_ORGANIC.value, MetricId.VIEWS_PAID.value,
            MetricId.WEBSITE_CLICKS.value,
        }
    ),
    PlatformId.TIKTOK: frozenset(
        {
            "audience_activity", "audience_ages", "audience_countries",
            "audience_genders", "average_time_watched", "comments", "content_total",
            MetricId.FOLLOWERS.value, MetricId.FOLLOWERS_NET.value,
            MetricId.FOLLOWING.value, MetricId.FOLLOWS.value,
            "full_video_watched_rate", MetricId.INTERACTIONS.value, "likes",
            MetricId.NEW_FOLLOWERS.value, MetricId.PROFILE_VIEWS.value,
            MetricId.REACH.value, "shares", "total_time_watched",
            MetricId.UNFOLLOWS.value, MetricId.VIEWS.value,
        }
    ),
}

KNOWN_LEGACY_BREAKDOWN_KEYS = frozenset(
    {
        "activity_type", "audience_activity", "audience_ages", "audience_cities",
        "audience_countries", "audience_genders", "city", "contact_option",
        "content_id", "content_type", "country", "follow_type", "gender_age",
        "hashtag", "heatmap",
    }
)

_AUDIENCE_PROJECTIONS: dict[str, tuple[MetricId, str]] = {
    "audience_country": (MetricId.FOLLOWERS, "audience_country"),
    "audience_countries": (MetricId.FOLLOWERS, "audience_country"),
    "audience_city": (MetricId.FOLLOWERS, "audience_city"),
    "audience_cities": (MetricId.FOLLOWERS, "audience_city"),
    "audience_gender_age": (MetricId.FOLLOWERS, "audience_gender_age"),
    "audience_ages": (MetricId.FOLLOWERS, "audience_age"),
    "audience_genders": (MetricId.FOLLOWERS, "audience_gender"),
    "audience_heatmap": (MetricId.INTERACTIONS, "best_time_to_engage"),
    "audience_activity": (MetricId.FOLLOWERS, "audience_activity"),
}

_TIKTOK_TOTALS: dict[str, MetricId] = {
    MetricId.VIEWS.value: MetricId.VIDEO_VIEWS_TOTAL,
    "likes": MetricId.VIDEO_LIKES_TOTAL,
    "comments": MetricId.VIDEO_COMMENTS_TOTAL,
    "shares": MetricId.VIDEO_SHARES_TOTAL,
}

_FIXED_BREAKDOWNS: dict[tuple[PlatformId, str], tuple[MetricId, str, str]] = {
    (PlatformId.FACEBOOK, "page_like_types_organic"): (
        MetricId.FOLLOWERS, "page_like_type", "organic"
    ),
    (PlatformId.FACEBOOK, "page_like_types_paid"): (
        MetricId.FOLLOWERS, "page_like_type", "paid"
    ),
}

_FACEBOOK_ENGAGEMENT_PREFIX = "post_engagements_"
_INSTAGRAM_INTERACTION_METRICS = frozenset(
    {"comments", "likes", "replies", "saves", "shares"}
)
_CONTENT_BREAKDOWNS = frozenset({"content_id", "content_type", "hashtag"})


def legacy_metric_disposition(
    platform: PlatformId,
    raw_metric_id: str,
    breakdown_key: str | None,
) -> LegacyMetricDisposition:
    if raw_metric_id in _AUDIENCE_PROJECTIONS:
        return LegacyMetricDisposition.AUDIENCE_BREAKDOWN
    if platform is PlatformId.TIKTOK and breakdown_key == "content_id":
        if raw_metric_id in _TIKTOK_TOTALS:
            return LegacyMetricDisposition.TIKTOK_CONTENT_TOTAL
        return LegacyMetricDisposition.MIRRORED_IN_CONTENT
    if breakdown_key in _CONTENT_BREAKDOWNS:
        return LegacyMetricDisposition.MIRRORED_IN_CONTENT
    if (platform, raw_metric_id) in _FIXED_BREAKDOWNS:
        return LegacyMetricDisposition.DASHBOARD_BREAKDOWN
    if platform is PlatformId.FACEBOOK and raw_metric_id.startswith(
        _FACEBOOK_ENGAGEMENT_PREFIX
    ):
        return LegacyMetricDisposition.DASHBOARD_BREAKDOWN
    if (
        platform is PlatformId.INSTAGRAM
        and raw_metric_id in _INSTAGRAM_INTERACTION_METRICS
        and breakdown_key is None
    ):
        return LegacyMetricDisposition.DASHBOARD_BREAKDOWN
    if platform is PlatformId.INSTAGRAM and raw_metric_id in {
        "contact_options", "profile_activity"
    }:
        return LegacyMetricDisposition.DASHBOARD_BREAKDOWN
    try:
        MetricId(raw_metric_id)
    except ValueError:
        known = raw_metric_id in KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM.get(
            platform, frozenset()
        )
        return (
            LegacyMetricDisposition.DASHBOARD_UNUSED
            if known
            else LegacyMetricDisposition.UNKNOWN
        )
    return LegacyMetricDisposition.DIRECT


def project_legacy_metrics(
    rows: Iterable[LegacyMetricRow],
) -> tuple[ReportingMetric, ...]:
    projected: dict[
        tuple[int, date, MetricId, str | None, str | None],
        tuple[int, ReportingMetric],
    ] = {}
    tiktok_totals: dict[tuple[int, str, date, MetricId], float] = defaultdict(float)

    def keep(row: ReportingMetric, *, priority: int) -> None:
        key = (
            row.account_id,
            row.observed_on,
            row.metric_id,
            row.breakdown_key,
            row.breakdown_value,
        )
        current = projected.get(key)
        if current is None or priority > current[0]:
            projected[key] = (priority, row)

    for raw in rows:
        disposition = legacy_metric_disposition(
            raw.platform, raw.raw_metric_id, raw.breakdown_key
        )
        if disposition is LegacyMetricDisposition.TIKTOK_CONTENT_TOTAL:
            target = _TIKTOK_TOTALS[raw.raw_metric_id]
            tiktok_totals[(raw.account_id, raw.brand_id, raw.observed_on, target)] += raw.value
            continue
        if disposition is LegacyMetricDisposition.AUDIENCE_BREAKDOWN:
            if raw.breakdown_value is None:
                continue
            metric_id, dimension = _AUDIENCE_PROJECTIONS[raw.raw_metric_id]
            keep(_reporting_metric(raw, metric_id, dimension, raw.breakdown_value), priority=20)
            continue
        if disposition is LegacyMetricDisposition.DASHBOARD_BREAKDOWN:
            if fixed := _FIXED_BREAKDOWNS.get((raw.platform, raw.raw_metric_id)):
                metric_id, dimension, value = fixed
                keep(_reporting_metric(raw, metric_id, dimension, value), priority=20)
                continue
            if raw.platform is PlatformId.FACEBOOK and raw.raw_metric_id.startswith(
                _FACEBOOK_ENGAGEMENT_PREFIX
            ):
                label = raw.raw_metric_id.removeprefix(_FACEBOOK_ENGAGEMENT_PREFIX)
                dimension = "interaction_type" if label in {"comment", "share"} else "reaction_type"
                keep(
                    _reporting_metric(raw, MetricId.INTERACTIONS, dimension, label),
                    priority=20,
                )
                continue
            if raw.platform is PlatformId.INSTAGRAM and raw.raw_metric_id in {
                "contact_options", "profile_activity"
            }:
                if raw.breakdown_value is None:
                    continue
                keep(
                    _reporting_metric(
                        raw,
                        MetricId.TOTAL_ACTIONS,
                        "profile_action",
                        raw.breakdown_value,
                    ),
                    priority=20,
                )
                continue
            keep(
                _reporting_metric(
                    raw,
                    MetricId.INTERACTIONS,
                    "interaction_type",
                    raw.raw_metric_id,
                ),
                priority=20,
            )
            continue
        if disposition is not LegacyMetricDisposition.DIRECT:
            continue
        metric_id = MetricId(raw.raw_metric_id)
        # Native V2 rows win over compatibility projections with the same identity.
        keep(
            _reporting_metric(
                raw, metric_id, raw.breakdown_key, raw.breakdown_value
            ),
            priority=30,
        )

    for (account_id, brand_id, observed_on, metric_id), value in tiktok_totals.items():
        keep(
            ReportingMetric(
                account_id=account_id,
                brand_id=brand_id,
                platform=PlatformId.TIKTOK,
                observed_on=observed_on,
                metric_id=metric_id,
                value=value,
            ),
            priority=20,
        )

    return tuple(
        item[1]
        for item in sorted(
            projected.values(),
            key=lambda item: (
                item[1].observed_on,
                item[1].metric_id.value,
                item[1].breakdown_key or "",
                item[1].breakdown_value or "",
                item[1].account_id,
            ),
        )
    )


def _reporting_metric(
    raw: LegacyMetricRow,
    metric_id: MetricId,
    breakdown_key: str | None,
    breakdown_value: str | None,
) -> ReportingMetric:
    return ReportingMetric(
        account_id=raw.account_id,
        brand_id=raw.brand_id,
        platform=raw.platform,
        observed_on=raw.observed_on,
        metric_id=metric_id,
        value=raw.value,
        breakdown_key=breakdown_key,
        breakdown_value=breakdown_value,
    )


__all__ = [
    "KNOWN_LEGACY_BREAKDOWN_KEYS",
    "KNOWN_LEGACY_METRIC_IDS_BY_PLATFORM",
    "LegacyMetricDisposition",
    "LegacyMetricRow",
    "legacy_metric_disposition",
    "project_legacy_metrics",
]

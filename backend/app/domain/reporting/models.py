"""Canonical response models for social reporting queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from app.domain.metrics import MetricId, SemanticType, Unit
from app.domain.platforms import PlatformId


class DataStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    OUTDATED = "outdated"
    NEVER_SYNCED = "never_synced"


class AvailabilityStatus(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    PENDING = "pending"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class ReportingRange:
    start_on: date
    end_on: date
    key: str


@dataclass(frozen=True)
class DashboardMetric:
    metric_id: MetricId
    value: float | None
    previous_value: float | None
    delta_pct: float | None
    semantic_type: SemanticType
    unit: Unit
    data_status: DataStatus
    methodology: str
    availability_reason: str | None


@dataclass(frozen=True)
class DashboardPoint:
    observed_on: date
    value: float


@dataclass(frozen=True)
class DashboardSeries:
    metric_id: MetricId
    semantic_type: SemanticType
    points: tuple[DashboardPoint, ...]
    methodology: str


@dataclass(frozen=True)
class DashboardBreakdownItem:
    key: str
    value: float
    percentage: float | None


@dataclass(frozen=True)
class DashboardBreakdown:
    metric_id: MetricId
    dimension: str
    items: tuple[DashboardBreakdownItem, ...]


@dataclass(frozen=True)
class DashboardContent:
    account_id: int
    external_content_id: str
    content_type: str
    permalink: str
    message: str
    media_url: str
    published_at: datetime | None
    likes_count: int | None
    comments_count: int | None
    shares_count: int | None
    interactions: int | None
    views: float | None
    reach: float | None
    cover_url: str | None
    thumbnail_url: str | None
    cover_candidates: tuple[str, ...]
    thumbnail_candidates: tuple[str, ...]
    media_url_candidates: tuple[str, ...]
    full_video_watched_rate: float | None
    total_time_watched: float | None
    average_time_watched: float | None
    saves_count: float | None
    profile_visits: float | None
    reposts_count: int | None
    quotes_count: int | None
    link_clicks: int | None
    profile_clicks: int | None
    video_views_count: int | None
    video_playback_0_count: int | None
    video_playback_25_count: int | None
    video_playback_50_count: int | None
    video_playback_75_count: int | None
    video_playback_100_count: int | None
    completion_rate: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardNamedValue:
    name: str
    value: float


@dataclass(frozen=True)
class DashboardHashtag:
    name: str
    count: int


@dataclass(frozen=True)
class DashboardContentSummary:
    total: int
    by_type: tuple[DashboardNamedValue, ...]
    reach_by_type: tuple[DashboardNamedValue, ...]
    views_by_type: tuple[DashboardNamedValue, ...]
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardComparison:
    value: float | None
    previous_value: float | None
    delta_pct: float | None


@dataclass(frozen=True)
class DashboardContentMetrics:
    views: DashboardComparison
    reach: DashboardComparison
    likes: DashboardComparison
    comments: DashboardComparison
    shares: DashboardComparison
    interactions: DashboardComparison
    engagement_rate: DashboardComparison


@dataclass(frozen=True)
class DashboardSourceValues:
    organic: float | None
    paid: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardSourceBreakdown:
    organic_only: bool
    paid_available: bool
    views: DashboardSourceValues | None
    reach: DashboardSourceValues | None
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardMetricMethodology:
    follower_flow: str
    engagement_rate: str
    reach: str


@dataclass(frozen=True)
class DashboardAudienceCapabilities:
    source: str | None
    geo: AvailabilityStatus
    age_gender: AvailabilityStatus
    activity: AvailabilityStatus


@dataclass(frozen=True)
class DashboardStorySummary:
    count: int
    views: float | None
    reach: float | None
    interactions: float | None
    replies: float | None
    completion_rate: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardStoryTrend:
    labels: tuple[date, ...]
    views: tuple[float | None, ...]
    reach: tuple[float | None, ...]
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardStoryNavigation:
    taps_forward: float | None
    taps_back: float | None
    swipe_forward: float | None
    exits: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardStoryActions:
    replies: float | None
    shares: float | None
    profile_visits: float | None
    follows: float | None
    sticker_taps: float | None
    saves: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardStoryItem:
    content_id: str
    title: str
    cover_url: str
    permalink: str
    created_time: datetime | None
    views: float | None
    reach: float | None
    interactions: float | None
    replies: float | None
    shares: float | None
    profile_visits: float | None
    follows: float | None
    sticker_taps: float | None
    saves: float | None
    taps_forward: float | None
    taps_back: float | None
    swipe_forward: float | None
    exits: float | None
    navigation: float | None
    completion_rate: float | None
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardStories:
    summary: DashboardStorySummary
    previous_summary: DashboardStorySummary
    trend: DashboardStoryTrend
    navigation: DashboardStoryNavigation
    actions: DashboardStoryActions
    items: tuple[DashboardStoryItem, ...]
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardTopCommenter:
    name: str
    comments: int
    likes: int


@dataclass(frozen=True)
class DashboardTopLikedComment:
    name: str
    comment: str
    likes: int
    replies: int


@dataclass(frozen=True)
class CommunitySummary:
    total_comments: int
    answered_comments: int
    unanswered_comments: int
    comment_likes: int
    data_status: DataStatus
    top_commenters: tuple[DashboardTopCommenter, ...]
    top_liked_comments: tuple[DashboardTopLikedComment, ...]


@dataclass(frozen=True)
class DashboardMentionSummary:
    total: int
    unique_authors: int
    daily: tuple[DashboardPoint, ...]
    data_status: DataStatus


@dataclass(frozen=True)
class DashboardMeta:
    dashboard_id: str
    platform: PlatformId | None
    requested_brand_id: str
    rollup: bool
    resolved_brand_ids: tuple[str, ...]
    resolved_account_ids: tuple[int, ...]
    date_range: ReportingRange
    generated_at: datetime
    last_sync_at: datetime | None
    freshness: FreshnessStatus
    observed_days: int
    expected_days: int
    data_status: DataStatus
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PlatformDashboard:
    meta: DashboardMeta
    metrics: tuple[DashboardMetric, ...]
    series: tuple[DashboardSeries, ...]
    breakdowns: tuple[DashboardBreakdown, ...]
    content: tuple[DashboardContent, ...]
    community: CommunitySummary
    top_hashtags: tuple[DashboardHashtag, ...]
    content_summary: DashboardContentSummary
    content_metrics: DashboardContentMetrics
    source_breakdown: DashboardSourceBreakdown | None
    metric_methodology: DashboardMetricMethodology
    audience_capabilities: DashboardAudienceCapabilities
    stories: DashboardStories | None
    mentions: DashboardMentionSummary | None


@dataclass(frozen=True)
class OverviewDashboard:
    meta: DashboardMeta
    metrics: tuple[DashboardMetric, ...]
    platforms: tuple[PlatformDashboard, ...]
    content: tuple[DashboardContent, ...]
    community: CommunitySummary


__all__ = [
    "AvailabilityStatus",
    "CommunitySummary",
    "DashboardAudienceCapabilities",
    "DashboardBreakdown",
    "DashboardBreakdownItem",
    "DashboardComparison",
    "DashboardContent",
    "DashboardContentMetrics",
    "DashboardContentSummary",
    "DashboardHashtag",
    "DashboardMeta",
    "DashboardMetric",
    "DashboardMetricMethodology",
    "DashboardMentionSummary",
    "DashboardNamedValue",
    "DashboardPoint",
    "DashboardSeries",
    "DashboardSourceBreakdown",
    "DashboardSourceValues",
    "DashboardStories",
    "DashboardStoryActions",
    "DashboardStoryItem",
    "DashboardStoryNavigation",
    "DashboardStorySummary",
    "DashboardStoryTrend",
    "DashboardTopCommenter",
    "DashboardTopLikedComment",
    "DataStatus",
    "FreshnessStatus",
    "OverviewDashboard",
    "PlatformDashboard",
    "ReportingRange",
]

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


@dataclass(frozen=True)
class DashboardPoint:
    observed_on: date
    value: float


@dataclass(frozen=True)
class DashboardSeries:
    metric_id: MetricId
    semantic_type: SemanticType
    points: tuple[DashboardPoint, ...]


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
    likes_count: int
    comments_count: int
    shares_count: int
    interactions: int


@dataclass(frozen=True)
class CommunitySummary:
    total_comments: int
    answered_comments: int
    unanswered_comments: int
    comment_likes: int
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


@dataclass(frozen=True)
class OverviewDashboard:
    meta: DashboardMeta
    metrics: tuple[DashboardMetric, ...]
    platforms: tuple[PlatformDashboard, ...]
    content: tuple[DashboardContent, ...]
    community: CommunitySummary


__all__ = [
    "CommunitySummary",
    "DashboardBreakdown",
    "DashboardBreakdownItem",
    "DashboardContent",
    "DashboardMeta",
    "DashboardMetric",
    "DashboardPoint",
    "DashboardSeries",
    "DataStatus",
    "FreshnessStatus",
    "OverviewDashboard",
    "PlatformDashboard",
    "ReportingRange",
]

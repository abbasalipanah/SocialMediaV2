"""Read-only reporting port for dashboard and operations query services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId


@dataclass(frozen=True)
class ReportingAccount:
    account_id: int
    brand_id: str
    platform: PlatformId
    external_id: str
    display_name: str
    status: str
    connection_state: str
    health_status: str
    backfill_status: str
    nightly_enabled: bool
    last_synced_at: datetime | None


@dataclass(frozen=True)
class ReportingMetric:
    account_id: int
    brand_id: str
    platform: PlatformId
    observed_on: date
    metric_id: MetricId
    value: float
    breakdown_key: str | None = None
    breakdown_value: str | None = None


@dataclass(frozen=True)
class ReportingContent:
    account_id: int
    brand_id: str
    platform: PlatformId
    external_content_id: str
    content_type: str
    permalink: str
    message: str
    media_url: str
    published_at: datetime | None
    likes_count: int
    comments_count: int
    shares_count: int


@dataclass(frozen=True)
class ReportingComment:
    account_id: int
    platform: PlatformId
    external_content_id: str
    external_comment_id: str
    author_name: str | None
    text: str
    like_count: int
    reply_count: int
    answered: bool
    commented_at: datetime | None


@dataclass(frozen=True)
class ReportingMedia:
    account_id: int
    brand_id: str
    platform: PlatformId
    external_content_id: str
    media_kind: str
    storage_path: Path
    mime_type: str
    size_bytes: int
    checksum: str


@dataclass(frozen=True)
class ReportingConnection:
    connection_id: int
    brand_id: str
    platform: PlatformId
    state: str
    expires_at: datetime | None
    projected_at: datetime | None


@dataclass(frozen=True)
class ReportingSyncJob:
    job_id: int
    brand_id: str
    account_id: int | None
    platform: PlatformId
    stage: str
    status: str
    scheduled_for: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error_code: str | None


@dataclass(frozen=True)
class ReportingInsight:
    insight_id: int
    brand_id: str
    status: str
    date_from: date | None
    date_to: date | None
    summary: str | None
    recommendations: str | None
    created_at: datetime
    completed_at: datetime | None


class ReportingStore(Protocol):
    def list_accounts(
        self,
        *,
        brand_ids: tuple[str, ...],
        platform: PlatformId | None = None,
    ) -> tuple[ReportingAccount, ...]: ...

    def list_metrics(
        self,
        *,
        account_ids: tuple[int, ...],
        start_on: date,
        end_on: date,
    ) -> tuple[ReportingMetric, ...]: ...

    def list_content(
        self,
        *,
        account_ids: tuple[int, ...],
        start_on: date,
        end_on: date,
        content_type: str | None = None,
    ) -> tuple[ReportingContent, ...]: ...

    def list_comments(
        self,
        *,
        account_ids: tuple[int, ...],
        start_on: date,
        end_on: date,
    ) -> tuple[ReportingComment, ...]: ...

    def find_media(
        self,
        *,
        brand_ids: tuple[str, ...],
        platform: PlatformId,
        external_content_id: str,
        account_id: int | None = None,
    ) -> ReportingMedia | None: ...

    def list_connections(
        self, *, brand_ids: tuple[str, ...]
    ) -> tuple[ReportingConnection, ...]: ...

    def list_sync_jobs(
        self, *, brand_ids: tuple[str, ...]
    ) -> tuple[ReportingSyncJob, ...]: ...

    def list_insights(
        self,
        *,
        brand_ids: tuple[str, ...],
        start_on: date | None = None,
        end_on: date | None = None,
    ) -> tuple[ReportingInsight, ...]: ...


__all__ = [
    "ReportingAccount",
    "ReportingComment",
    "ReportingConnection",
    "ReportingContent",
    "ReportingInsight",
    "ReportingMedia",
    "ReportingMetric",
    "ReportingStore",
    "ReportingSyncJob",
]

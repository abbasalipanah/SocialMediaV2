"""Typed response contracts shared by the Phase 6 API surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.ports.reporting import (
    ReportingAccount,
    ReportingConnection,
    ReportingInsight,
    ReportingSyncJob,
)
from app.capabilities import CapabilityRecord
from app.core import RuntimeMode
from app.domain.authority import BrandScope
from app.domain.platforms import PlatformId


@dataclass(frozen=True)
class PlatformAccountsResponse:
    meta: BrandScope
    platform: PlatformId
    accounts: tuple[ReportingAccount, ...]


@dataclass(frozen=True)
class SettingsBrandItem:
    brand_id: str
    name: str | None
    parent_brand_id: str | None
    visibility: str
    access_mode: str | None
    role: str | None
    linked_account_count: int
    last_sync_at: datetime | None


@dataclass(frozen=True)
class SettingsBrandsResponse:
    meta: BrandScope
    items: tuple[SettingsBrandItem, ...]


@dataclass(frozen=True)
class SocialAccountsResponse:
    meta: BrandScope
    items: tuple[ReportingAccount, ...]


@dataclass(frozen=True)
class BrandLinkItem:
    brand_id: str
    platform: PlatformId
    account_id: int
    external_id: str
    display_name: str
    link_status: str


@dataclass(frozen=True)
class BrandLinksResponse:
    meta: BrandScope
    items: tuple[BrandLinkItem, ...]


@dataclass(frozen=True)
class ConnectionsResponse:
    meta: BrandScope
    items: tuple[ReportingConnection, ...]


@dataclass(frozen=True)
class SyncJobsResponse:
    meta: BrandScope
    items: tuple[ReportingSyncJob, ...]


@dataclass(frozen=True)
class AuditResponse:
    meta: BrandScope
    status: str
    reason: str
    items: tuple[object, ...]


@dataclass(frozen=True)
class TikTokConnectionResponse:
    meta: BrandScope
    state: str
    connection: ReportingConnection | None
    capabilities: tuple[CapabilityRecord, ...]
    checked_at: datetime


@dataclass(frozen=True)
class InsightsResponse:
    meta: BrandScope
    items: tuple[ReportingInsight, ...]


@dataclass(frozen=True)
class CapabilityPlatform:
    platform: PlatformId
    capabilities: tuple[CapabilityRecord, ...]


@dataclass(frozen=True)
class WorkspacePermissions:
    settings_visible: bool
    internal_audit_visible: bool
    rollup_available: bool
    operation_mutation_available: bool


@dataclass(frozen=True)
class RuntimeCapabilities:
    mode: RuntimeMode
    writes_enabled: bool
    automated_schedule_available: bool


@dataclass(frozen=True)
class ReadinessPlatform:
    platform: PlatformId
    account_count: int
    last_sync_at: datetime | None
    pending_job_count: int


@dataclass(frozen=True)
class OperationsReadinessResponse:
    status: str
    runtime_mode: RuntimeMode
    writes_enabled: bool
    database_configured: bool
    scope: BrandScope | None = None
    platforms: tuple[ReadinessPlatform, ...] = ()


@dataclass(frozen=True)
class WorkspaceCapabilitiesResponse:
    scope: BrandScope
    platforms: tuple[CapabilityPlatform, ...]
    permissions: WorkspacePermissions
    runtime: RuntimeCapabilities


__all__ = [
    "AuditResponse",
    "BrandLinkItem",
    "BrandLinksResponse",
    "CapabilityPlatform",
    "ConnectionsResponse",
    "InsightsResponse",
    "OperationsReadinessResponse",
    "PlatformAccountsResponse",
    "RuntimeCapabilities",
    "ReadinessPlatform",
    "SettingsBrandItem",
    "SettingsBrandsResponse",
    "SocialAccountsResponse",
    "SyncJobsResponse",
    "TikTokConnectionResponse",
    "WorkspaceCapabilitiesResponse",
    "WorkspacePermissions",
]

"""Typed response contracts shared by the Phase 6 API surface."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.application.ports.ai_summary import AiSummaryLimitStatus
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
class AuthMeResponse:
    authenticated: bool
    user_id: str
    email: str | None
    source_system: str | None
    brand_id: str
    role: str
    app_role: str | None
    access_mode: str
    settings_visible: bool
    integrations_visible: bool
    is_internal_staff: bool
    expires_at: datetime
    revoked: bool


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
class TikTokActivationReadinessResponse:
    handoff_ready: bool
    brand_id: str
    launch_target: str
    fresh_until: datetime
    runtime_mode: RuntimeMode
    writes_enabled: bool
    connection_state: str
    oauth_start_available: bool
    reason: str
    checked_at: datetime


@dataclass(frozen=True)
class TikTokSelfServiceReadinessResponse:
    brand_id: str
    can_manage: bool
    connection_state: str
    linked_account_count: int
    oauth_start_available: bool
    reason: str
    runtime_mode: RuntimeMode
    writes_enabled: bool
    checked_at: datetime


@dataclass(frozen=True)
class TikTokSelfServiceStartResponse:
    authorization_url: str
    expires_at: datetime


@dataclass(frozen=True)
class MetaDiscoveryItem:
    connection_id: int
    platform: PlatformId
    external_id: str
    display_name: str
    status: str


@dataclass(frozen=True)
class MetaLinkedAccountItem:
    platform: PlatformId
    external_id: str
    display_name: str


@dataclass(frozen=True)
class MetaSelfServiceReadinessResponse:
    brand_id: str
    can_manage: bool
    connection_state: str
    facebook_linked_count: int
    instagram_linked_count: int
    linked_accounts: tuple[MetaLinkedAccountItem, ...]
    discoveries: tuple[MetaDiscoveryItem, ...]
    oauth_start_available: bool
    reason: str
    runtime_mode: RuntimeMode
    writes_enabled: bool
    checked_at: datetime


@dataclass(frozen=True)
class MetaSelfServiceStartResponse:
    authorization_url: str
    expires_at: datetime


@dataclass(frozen=True)
class MetaLinkResponse:
    connection_id: int
    linked_count: int
    connection_state: str


@dataclass(frozen=True)
class MetaRefreshResponse:
    connection_id: int
    facebook_count: int
    instagram_count: int
    discovered_count: int


@dataclass(frozen=True)
class InsightsResponse:
    meta: BrandScope
    items: tuple[ReportingInsight, ...]


@dataclass(frozen=True)
class AiSummaryLimitResponse:
    provider_configured: bool
    can_generate: bool
    reason: str
    weekly_limit: int
    used: int
    remaining: int
    window_days: int
    last_generated_at: datetime | None
    next_available_at: datetime | None
    generation_in_progress: bool

    @classmethod
    def from_status(cls, status: AiSummaryLimitStatus) -> AiSummaryLimitResponse:
        return cls(**status.__dict__)


@dataclass(frozen=True)
class CapabilityPlatform:
    platform: PlatformId
    capabilities: tuple[CapabilityRecord, ...]
    linked_account_count: int
    navigation_available: bool


@dataclass(frozen=True)
class WorkspacePermissions:
    settings_visible: bool
    integrations_visible: bool
    internal_audit_visible: bool
    rollup_available: bool
    operation_mutation_available: bool
    tiktok_connection_manage: bool
    meta_connection_manage: bool


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
class ReportJobResponse:
    job_id: str
    state: Literal["queued", "running", "ready", "failed"]
    progress: int
    stage: str
    filename: str | None
    created_at: datetime
    expires_at: datetime | None
    error_code: str | None


@dataclass(frozen=True)
class WorkspaceCapabilitiesResponse:
    scope: BrandScope
    platforms: tuple[CapabilityPlatform, ...]
    permissions: WorkspacePermissions
    runtime: RuntimeCapabilities


__all__ = [
    "AuditResponse",
    "AuthMeResponse",
    "BrandLinkItem",
    "BrandLinksResponse",
    "CapabilityPlatform",
    "ConnectionsResponse",
    "InsightsResponse",
    "MetaDiscoveryItem",
    "MetaLinkedAccountItem",
    "MetaLinkResponse",
    "MetaRefreshResponse",
    "MetaSelfServiceReadinessResponse",
    "MetaSelfServiceStartResponse",
    "OperationsReadinessResponse",
    "PlatformAccountsResponse",
    "RuntimeCapabilities",
    "ReadinessPlatform",
    "ReportJobResponse",
    "SettingsBrandItem",
    "SettingsBrandsResponse",
    "SocialAccountsResponse",
    "SyncJobsResponse",
    "TikTokConnectionResponse",
    "TikTokActivationReadinessResponse",
    "TikTokSelfServiceReadinessResponse",
    "TikTokSelfServiceStartResponse",
    "WorkspaceCapabilitiesResponse",
    "WorkspacePermissions",
]

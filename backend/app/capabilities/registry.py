"""Backend-owned platform capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from app.domain.platforms import CapabilityId, PlatformId

if TYPE_CHECKING:
    from app.core.config import AppSettings


class CapabilityStatus(StrEnum):
    UNSUPPORTED = "unsupported"
    NOT_APPROVED = "not_approved"
    NOT_CONFIGURED = "not_configured"
    BLOCKED_CONFIGURATION = "blocked_configuration"
    MANUAL_ACTIVATION_REQUIRED = "manual_activation_required"
    PARTIAL = "partial"
    AVAILABLE = "available"


@dataclass(frozen=True)
class CapabilityRecord:
    platform: PlatformId
    capability: CapabilityId
    status: CapabilityStatus
    reason: str


class PlatformCapabilityRegistry:
    def __init__(self, records: tuple[CapabilityRecord, ...]) -> None:
        keys = {(record.platform, record.capability) for record in records}
        if len(keys) != len(records):
            raise ValueError("duplicate_capability_record")
        self._records = records

    def get(self, platform: PlatformId, capability: CapabilityId) -> CapabilityRecord:
        for record in self._records:
            if record.platform is platform and record.capability is capability:
                return record
        return CapabilityRecord(
            platform=platform,
            capability=capability,
            status=CapabilityStatus.UNSUPPORTED,
            reason="capability_not_registered",
        )

    def records(self) -> tuple[CapabilityRecord, ...]:
        return self._records


def bootstrap_registry(settings: AppSettings | None = None) -> PlatformCapabilityRegistry:
    records: list[CapabilityRecord] = []
    for platform in (PlatformId.FACEBOOK, PlatformId.INSTAGRAM):
        records.extend(
            CapabilityRecord(
                platform=platform,
                capability=capability,
                status=(
                    CapabilityStatus.AVAILABLE
                    if settings is not None and settings.meta.collection_enabled
                    else CapabilityStatus.NOT_CONFIGURED
                ),
                reason=(
                    "standalone_collector_available"
                    if settings is not None and settings.meta.collection_enabled
                    else "provider_not_configured"
                ),
            )
            for capability in CapabilityId
        )
    tiktok_collection = (
        settings is not None and settings.tiktok.collection_enabled
    )
    records.extend(
        (
            CapabilityRecord(
                platform=PlatformId.TIKTOK,
                capability=CapabilityId.PROFILE,
                status=(
                    CapabilityStatus.AVAILABLE
                    if tiktok_collection
                    else CapabilityStatus.MANUAL_ACTIVATION_REQUIRED
                ),
                reason=(
                    "standalone_collector_available"
                    if tiktok_collection
                    else "owner_activation_required"
                ),
            ),
            CapabilityRecord(
                platform=PlatformId.TIKTOK,
                capability=CapabilityId.CONTENT,
                status=(
                    CapabilityStatus.AVAILABLE
                    if tiktok_collection
                    else CapabilityStatus.MANUAL_ACTIVATION_REQUIRED
                ),
                reason=(
                    "standalone_collector_available"
                    if tiktok_collection
                    else "owner_activation_required"
                ),
            ),
            CapabilityRecord(
                platform=PlatformId.TIKTOK,
                capability=CapabilityId.COMMENTS,
                status=CapabilityStatus.NOT_APPROVED,
                reason="optional_scope_not_approved",
            ),
            CapabilityRecord(
                platform=PlatformId.TIKTOK,
                capability=CapabilityId.AUDIENCE,
                status=(
                    CapabilityStatus.PARTIAL
                    if tiktok_collection
                    else CapabilityStatus.MANUAL_ACTIVATION_REQUIRED
                ),
                reason=(
                    "profile_totals_only"
                    if tiktok_collection
                    else "owner_activation_required"
                ),
            ),
        )
    )
    x_collection = settings is not None and settings.x.collection_enabled
    for capability in CapabilityId:
        if not x_collection:
            status = CapabilityStatus.NOT_CONFIGURED
            reason = "provider_not_configured"
        elif capability in {CapabilityId.PROFILE, CapabilityId.CONTENT}:
            status = CapabilityStatus.AVAILABLE
            reason = "standalone_collector_available"
        elif capability is CapabilityId.COMMENTS:
            status = CapabilityStatus.PARTIAL
            reason = "account_mentions_only"
        else:
            status = CapabilityStatus.UNSUPPORTED
            reason = f"x_{capability.value}_not_implemented"
        records.append(
            CapabilityRecord(
                platform=PlatformId.X,
                capability=capability,
                status=status,
                reason=reason,
            )
        )
    linkedin_collection = settings is not None and settings.linkedin.collection_enabled
    for capability in CapabilityId:
        if not linkedin_collection:
            status = CapabilityStatus.NOT_CONFIGURED
            reason = "provider_not_configured"
        elif capability in {CapabilityId.PROFILE, CapabilityId.CONTENT}:
            status = CapabilityStatus.AVAILABLE
            reason = "company_page_collector_available"
        elif capability is CapabilityId.AUDIENCE:
            status = CapabilityStatus.PARTIAL
            reason = "staff_count_and_association_type_available"
        else:
            status = CapabilityStatus.UNSUPPORTED
            reason = "linkedin_comments_not_implemented"
        records.append(
            CapabilityRecord(
                platform=PlatformId.LINKEDIN,
                capability=capability,
                status=status,
                reason=reason,
            )
        )
    youtube_collection = settings is not None and settings.youtube.collection_enabled
    for capability in CapabilityId:
        if not youtube_collection:
            status = CapabilityStatus.NOT_CONFIGURED
            reason = "provider_not_configured"
        elif capability is CapabilityId.AUDIENCE:
            status = CapabilityStatus.UNSUPPORTED
            reason = "youtube_audience_not_implemented"
        else:
            status = CapabilityStatus.AVAILABLE
            reason = "standalone_collector_available"
        records.append(
            CapabilityRecord(
                platform=PlatformId.YOUTUBE,
                capability=capability,
                status=status,
                reason=reason,
            )
        )
    return PlatformCapabilityRegistry(tuple(records))


def supported_capabilities() -> tuple[str, ...]:
    return tuple(capability.value for capability in CapabilityId)


__all__ = [
    "CapabilityId",
    "CapabilityRecord",
    "CapabilityStatus",
    "PlatformCapabilityRegistry",
    "bootstrap_registry",
    "supported_capabilities",
]

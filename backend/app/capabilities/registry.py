"""Backend-owned platform capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.domain.platforms import CapabilityId, PlatformId


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


def bootstrap_registry() -> PlatformCapabilityRegistry:
    records: list[CapabilityRecord] = []
    for platform in (PlatformId.FACEBOOK, PlatformId.INSTAGRAM):
        records.extend(
            CapabilityRecord(
                platform=platform,
                capability=capability,
                status=CapabilityStatus.NOT_CONFIGURED,
                reason="provider_not_configured",
            )
            for capability in CapabilityId
        )
    records.extend(
        (
            CapabilityRecord(
                platform=PlatformId.TIKTOK,
                capability=CapabilityId.PROFILE,
                status=CapabilityStatus.MANUAL_ACTIVATION_REQUIRED,
                reason="owner_activation_required",
            ),
            CapabilityRecord(
                platform=PlatformId.TIKTOK,
                capability=CapabilityId.CONTENT,
                status=CapabilityStatus.MANUAL_ACTIVATION_REQUIRED,
                reason="owner_activation_required",
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
                status=CapabilityStatus.MANUAL_ACTIVATION_REQUIRED,
                reason="owner_activation_required",
            ),
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

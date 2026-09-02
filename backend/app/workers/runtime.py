"""Fail-closed worker runtime and explicit provider-egress gates."""

from __future__ import annotations

from dataclasses import dataclass

from app.capabilities.registry import (
    CapabilityStatus,
    PlatformCapabilityRegistry,
)
from app.core.config import AppSettings, ConfigurationError, RuntimeMode
from app.core.write_policy import WritePolicy
from app.domain.platforms import CapabilityId, PlatformId


@dataclass(frozen=True)
class WorkerRuntimeConfig:
    runtime_mode: RuntimeMode
    writes_enabled: bool
    provider_egress_enabled: bool
    automated_schedule_enabled: bool = False

    def __post_init__(self) -> None:
        if self.provider_egress_enabled and (
            self.runtime_mode
            not in {RuntimeMode.DEVELOPMENT, RuntimeMode.STAGING, RuntimeMode.ACTIVE}
            or not self.writes_enabled
        ):
            raise ConfigurationError("worker_egress_requires_writable_v2_runtime")
        if self.automated_schedule_enabled and not self.provider_egress_enabled:
            raise ConfigurationError("worker_schedule_requires_provider_egress")


@dataclass(frozen=True)
class ManualWorkerSelection:
    platform: PlatformId
    capability: CapabilityId
    account_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.account_ids or len(set(self.account_ids)) != len(self.account_ids):
            raise ValueError("worker_account_selection_invalid")
        if any(not account_id.strip() for account_id in self.account_ids):
            raise ValueError("worker_account_selection_invalid")


def dormant_worker_config(settings: AppSettings) -> WorkerRuntimeConfig:
    return WorkerRuntimeConfig(
        runtime_mode=settings.runtime_mode,
        writes_enabled=settings.social_writes_enabled,
        provider_egress_enabled=False,
        automated_schedule_enabled=False,
    )


def settings_worker_config(settings: AppSettings) -> WorkerRuntimeConfig:
    provider_enabled = (
        settings.meta.collection_enabled
        or settings.tiktok.collection_enabled
        or settings.x.collection_enabled
        or settings.linkedin.collection_enabled
        or settings.youtube.collection_enabled
    )
    return WorkerRuntimeConfig(
        runtime_mode=settings.runtime_mode,
        writes_enabled=settings.social_writes_enabled,
        provider_egress_enabled=provider_enabled,
        automated_schedule_enabled=settings.worker_schedule_enabled,
    )


def local_fixture_worker_config(write_policy: WritePolicy) -> WorkerRuntimeConfig:
    return WorkerRuntimeConfig(
        runtime_mode=write_policy.runtime_mode,
        writes_enabled=write_policy.writes_enabled,
        provider_egress_enabled=True,
        automated_schedule_enabled=False,
    )


def assert_manual_worker_allowed(
    config: WorkerRuntimeConfig,
    registry: PlatformCapabilityRegistry,
    selection: ManualWorkerSelection,
) -> None:
    if not config.provider_egress_enabled:
        raise PermissionError("worker_provider_egress_disabled")
    capability = registry.get(selection.platform, selection.capability)
    if capability.status is not CapabilityStatus.AVAILABLE:
        raise PermissionError("worker_capability_unavailable")


__all__ = [
    "ManualWorkerSelection",
    "WorkerRuntimeConfig",
    "assert_manual_worker_allowed",
    "dormant_worker_config",
    "local_fixture_worker_config",
    "settings_worker_config",
]

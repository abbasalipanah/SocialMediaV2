"""Canonical platform capability registry."""

from .registry import (
    CapabilityRecord,
    CapabilityStatus,
    PlatformCapabilityRegistry,
    bootstrap_registry,
    supported_capabilities,
)

__all__ = [
    "CapabilityRecord",
    "CapabilityStatus",
    "PlatformCapabilityRegistry",
    "bootstrap_registry",
    "supported_capabilities",
]

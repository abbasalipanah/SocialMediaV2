"""Canonical application ports."""

from typing import Protocol

from .meta_activation import (
    MetaActivationError,
    MetaActivationProvider,
    MetaConnectionResult,
    MetaConnectionStore,
    MetaCredentialBinding,
    MetaDiscovery,
    MetaLinkResult,
    MetaLinkSelection,
    MetaProviderAccount,
    MetaProviderGrant,
)
from .provisioning_store import ProjectionReplacement, ProjectionWrite, ProvisioningStore
from .reporting import ReportingStore
from .session_store import SessionStore
from .tiktok_activation import (
    ActivationAuthority,
    ActivationContext,
    ActivationIntent,
    ActivationIntentStore,
    ActivationLink,
    ActivationLinkStore,
    ActivationResult,
    ActivationStart,
    ActivationStateClaims,
    ActivationStatePort,
    ProviderAccountGrant,
    ProviderPayloadTransport,
    ProviderTokenGrant,
    TikTokActivationError,
    TikTokActivationProvider,
)


class AuthorityStore(SessionStore, ProvisioningStore, Protocol):
    """Combined schema-compatible store used by the first local adapter."""


__all__ = [
    "AuthorityStore",
    "ActivationAuthority",
    "ActivationContext",
    "ActivationIntent",
    "ActivationIntentStore",
    "ActivationLink",
    "ActivationLinkStore",
    "ActivationResult",
    "ActivationStart",
    "ActivationStateClaims",
    "ActivationStatePort",
    "MetaActivationError",
    "MetaActivationProvider",
    "MetaConnectionResult",
    "MetaConnectionStore",
    "MetaCredentialBinding",
    "MetaDiscovery",
    "MetaLinkResult",
    "MetaLinkSelection",
    "MetaProviderAccount",
    "MetaProviderGrant",
    "ProjectionReplacement",
    "ProjectionWrite",
    "ProvisioningStore",
    "ReportingStore",
    "SessionStore",
    "ProviderAccountGrant",
    "ProviderPayloadTransport",
    "ProviderTokenGrant",
    "TikTokActivationError",
    "TikTokActivationProvider",
]

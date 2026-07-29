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


class AuthorityStore(SessionStore, Protocol):
    """V2-owned local session store used by the SSO boundary."""


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
    "ReportingStore",
    "SessionStore",
    "ProviderAccountGrant",
    "ProviderPayloadTransport",
    "ProviderTokenGrant",
    "TikTokActivationError",
    "TikTokActivationProvider",
]

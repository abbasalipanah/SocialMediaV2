"""Canonical application ports."""

from typing import Protocol

from .ai_summary import (
    AiSummaryError,
    AiSummaryLimitStatus,
    AiSummaryOutput,
    AiSummaryProvider,
    AiSummaryRepository,
    AiSummaryService,
)
from .comment_sentiment import (
    ClassifiedCommentSentiment,
    CommentSentimentBatch,
    CommentSentimentProvider,
    CommentSentimentRepository,
    PendingCommentSentiment,
)
from .meta_activation import (
    MetaActivationError,
    MetaActivationProvider,
    MetaCatalogAccount,
    MetaConnectionResult,
    MetaConnectionStore,
    MetaCredentialBinding,
    MetaDiscovery,
    MetaLinkResult,
    MetaLinkSelection,
    MetaProviderAccount,
    MetaProviderGrant,
    MetaRefreshConnection,
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
    TikTokActivationStatePort,
)


class AuthorityStore(SessionStore, Protocol):
    """V2-owned local session store used by the SSO boundary."""


__all__ = [
    "AiSummaryError",
    "AiSummaryLimitStatus",
    "AiSummaryOutput",
    "AiSummaryProvider",
    "AiSummaryRepository",
    "AiSummaryService",
    "AuthorityStore",
    "ClassifiedCommentSentiment",
    "CommentSentimentBatch",
    "CommentSentimentProvider",
    "CommentSentimentRepository",
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
    "TikTokActivationStatePort",
    "MetaActivationError",
    "MetaActivationProvider",
    "MetaCatalogAccount",
    "MetaConnectionResult",
    "MetaConnectionStore",
    "MetaCredentialBinding",
    "MetaDiscovery",
    "MetaLinkResult",
    "MetaLinkSelection",
    "MetaProviderAccount",
    "MetaProviderGrant",
    "MetaRefreshConnection",
    "PendingCommentSentiment",
    "ReportingStore",
    "SessionStore",
    "ProviderAccountGrant",
    "ProviderPayloadTransport",
    "ProviderTokenGrant",
    "TikTokActivationError",
    "TikTokActivationProvider",
]

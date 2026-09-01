"""V2-owned persistence adapters for social reporting and connection state."""

from .ai_summary import SocialAiSummaryRepository
from .collection_targets import SocialCollectionTargetStore
from .comments import SocialCommentStore
from .content import SocialContentStore
from .media import SocialMediaStore
from .meta_activation import ProjectionMetaConnectionStore
from .metrics import SocialMetricStore
from .oauth_channels import ProjectionOAuthConnectionStore
from .oauth_intents import ProjectionOAuthIntentStore
from .reporting import SocialReportingStore

__all__ = [
    "SocialAiSummaryRepository",
    "SocialCommentStore",
    "SocialCollectionTargetStore",
    "SocialContentStore",
    "SocialMediaStore",
    "SocialMetricStore",
    "SocialReportingStore",
    "ProjectionMetaConnectionStore",
    "ProjectionOAuthConnectionStore",
    "ProjectionOAuthIntentStore",
]

"""V2-owned persistence adapters for social reporting and connection state."""

from .collection_targets import SocialCollectionTargetStore
from .comments import SocialCommentStore
from .content import SocialContentStore
from .media import SocialMediaStore
from .meta_activation import ProjectionMetaConnectionStore
from .metrics import SocialMetricStore
from .reporting import SocialReportingStore

__all__ = [
    "SocialCommentStore",
    "SocialCollectionTargetStore",
    "SocialContentStore",
    "SocialMediaStore",
    "SocialMetricStore",
    "SocialReportingStore",
    "ProjectionMetaConnectionStore",
]

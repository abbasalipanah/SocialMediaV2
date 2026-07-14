"""Schema-compatible adapters isolated from canonical domain vocabulary."""

from .comments import LegacyCommentStore
from .content import LegacyContentStore
from .media import LegacyMediaStore
from .metrics import LegacyMetricStore

__all__ = [
    "LegacyCommentStore",
    "LegacyContentStore",
    "LegacyMediaStore",
    "LegacyMetricStore",
]

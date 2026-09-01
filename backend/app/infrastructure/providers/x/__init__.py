"""X OAuth and API adapters."""

from .content import XContentReader
from .mentions import XMentionPage, XMentionsReader
from .oauth import XOAuthError, XOAuthProvider
from .oauth_transport import XOAuthTransport, XOAuthTransportError
from .profile import XProfileReader
from .runtime import create_x_activation_runtime
from .transport import XHttpTransport, XTransportError
from .wire import (
    X_MENTIONS_PAGE_SIZE,
    X_POSTS_PAGE_SIZE,
    authenticated_user_query,
    user_mentions_query,
    user_mentions_url,
    user_posts_query,
    user_posts_url,
)

__all__ = [
    "XOAuthError",
    "XOAuthProvider",
    "XOAuthTransport",
    "XOAuthTransportError",
    "XContentReader",
    "XMentionPage",
    "XMentionsReader",
    "XHttpTransport",
    "XProfileReader",
    "X_POSTS_PAGE_SIZE",
    "X_MENTIONS_PAGE_SIZE",
    "XTransportError",
    "authenticated_user_query",
    "create_x_activation_runtime",
    "user_posts_query",
    "user_posts_url",
    "user_mentions_query",
    "user_mentions_url",
]

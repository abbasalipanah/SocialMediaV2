"""TikTok Business Accounts adapter boundary."""

from .activation import (
    TikTokAccountsActivationProvider,
    TikTokActivationStateAdapter,
    activation_config_version,
)
from .content import TikTokContentReader
from .oauth_state import (
    TikTokStateBinding,
    TikTokStateCodec,
    TikTokStateError,
    validate_callback,
)
from .profile import TikTokProfileReader
from .responses import (
    TikTokResponseError,
    TikTokTokenGrant,
    TikTokTokenInfo,
    parse_revoke,
    parse_token,
    parse_token_info,
)
from .scopes import ScopeDecision, evaluate_scopes
from .transport import TikTokHttpTransport, TikTokTransportError
from .wire import TikTokAccountsWireMapper, TikTokWireError

__all__ = [
    "TikTokAccountsActivationProvider",
    "TikTokActivationStateAdapter",
    "activation_config_version",
    "ScopeDecision",
    "TikTokAccountsWireMapper",
    "TikTokContentReader",
    "TikTokProfileReader",
    "TikTokHttpTransport",
    "TikTokResponseError",
    "TikTokStateBinding",
    "TikTokStateCodec",
    "TikTokStateError",
    "TikTokTokenGrant",
    "TikTokTokenInfo",
    "TikTokTransportError",
    "TikTokWireError",
    "evaluate_scopes",
    "parse_revoke",
    "parse_token",
    "parse_token_info",
    "validate_callback",
]

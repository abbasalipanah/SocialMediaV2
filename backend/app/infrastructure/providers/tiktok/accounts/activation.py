"""Business Accounts activation adapters with no built-in network transport."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime
from urllib.parse import urlencode

from app.application.ports import (
    ActivationContext,
    ActivationStateClaims,
    ProviderAccountGrant,
    ProviderPayloadTransport,
    ProviderTokenGrant,
)
from app.core.config import (
    TIKTOK_APP_ID,
    TIKTOK_PROVIDER_PROFILE,
    TikTokConfig,
)

from .oauth_state import TikTokStateBinding, TikTokStateCodec
from .responses import parse_revoke, parse_token, parse_token_info
from .wire import TikTokAccountsWireMapper


def activation_config_version(config: TikTokConfig) -> str:
    payload = {
        "app_id": config.app_id,
        "authorization_url": config.authorization_url,
        "optional_scopes": config.optional_scopes,
        "provider_profile": config.provider_profile,
        "redirect_uri": config.redirect_uri,
        "required_scopes": config.required_scopes,
        "revoke_url": config.revoke_url,
        "secret_rotated_at": (
            config.secret_rotated_at.isoformat()
            if config.secret_rotated_at is not None
            else None
        ),
        "token_info_url": config.token_info_url,
        "token_url": config.token_url,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


class TikTokActivationStateAdapter:
    def __init__(self, codec: TikTokStateCodec) -> None:
        self._codec = codec

    def issue(
        self,
        *,
        intent_hash: str,
        context: ActivationContext,
        expires_at: datetime,
    ) -> str:
        return self._codec.issue(
            TikTokStateBinding(
                nonce=secrets.token_urlsafe(24),
                intent_hash=intent_hash,
                user_id=context.user_id,
                brand_id=context.brand_id,
                session_binding=context.session_binding,
                expires_at=expires_at,
            )
        )

    def consume(
        self,
        token: str,
        *,
        expected_context: ActivationContext,
    ) -> ActivationStateClaims:
        binding = self._codec.consume(
            token,
            expected_user_id=expected_context.user_id,
            expected_brand_id=expected_context.brand_id,
            expected_session_binding=expected_context.session_binding,
        )
        return ActivationStateClaims(
            intent_hash=binding.intent_hash,
            context=expected_context,
            expires_at=binding.expires_at,
        )


class TikTokAccountsActivationProvider:
    def __init__(
        self,
        *,
        config: TikTokConfig,
        transport: ProviderPayloadTransport,
    ) -> None:
        self._config = config
        self._transport = transport
        self._wire = TikTokAccountsWireMapper(config)

    @property
    def activation_enabled(self) -> bool:
        return (
            self._config.account_enabled
            and self._config.oauth_mode == "manual_intent_only"
            and not self._config.advertiser_enabled
            and bool(self._config.app_secret)
            and self._config.provider_profile == TIKTOK_PROVIDER_PROFILE
            and self._config.app_id == TIKTOK_APP_ID
        )

    @property
    def redirect_uri(self) -> str:
        return self._config.redirect_uri

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str:
        fields = self._wire.authorization_fields(state=state, requested_scopes=scopes)
        return f"{self._config.authorization_url}?{urlencode(fields)}"

    def exchange(self, *, auth_code: str) -> ProviderTokenGrant:
        payload = self._transport.post(
            self._config.token_url,
            data=self._wire.token_fields(auth_code=auth_code),
        )
        grant = parse_token(payload)
        return ProviderTokenGrant(
            access_token=grant.access_token,
            refresh_token=grant.refresh_token,
            expires_in=grant.expires_in,
            refresh_expires_in=grant.refresh_expires_in,
            scopes=grant.scopes,
        )

    def inspect(self, *, access_token: str) -> ProviderAccountGrant:
        payload = self._transport.get(
            self._config.token_info_url,
            headers=self._wire.token_info_headers(access_token=access_token),
        )
        info = parse_token_info(payload)
        return ProviderAccountGrant(business_id=info.business_id, scopes=info.scopes)

    def revoke(self, *, access_token: str) -> None:
        payload = self._transport.post(
            self._config.revoke_url,
            data=self._wire.revoke_fields(access_token=access_token),
        )
        parse_revoke(payload)


__all__ = [
    "TikTokAccountsActivationProvider",
    "TikTokActivationStateAdapter",
    "activation_config_version",
]

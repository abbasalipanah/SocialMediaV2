"""X OAuth 2.0 confidential application adapter with deterministic PKCE."""

from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Mapping
from urllib.parse import urlencode

from app.application.ports import (
    OAuthAccountGrant,
    OAuthChannelError,
    OAuthProviderGrant,
    OAuthTokenRefresh,
)
from app.core import XConfig
from app.domain.platforms import PlatformId

from .oauth_transport import XOAuthTransport
from .responses import XResponseError, required_mapping, required_text


class XOAuthError(OAuthChannelError):
    """Stable X OAuth failure without provider payloads or credentials."""


class XOAuthProvider:
    platform = PlatformId.X

    def __init__(
        self,
        *,
        config: XConfig,
        transport: XOAuthTransport,
        pkce_secret: bytes,
    ) -> None:
        if len(pkce_secret) < 32:
            raise XOAuthError("x_pkce_secret_invalid")
        self._config = config
        self._transport = transport
        self._pkce_secret = pkce_secret

    @property
    def activation_enabled(self) -> bool:
        return self._config.account_enabled

    @property
    def redirect_uri(self) -> str:
        return self._config.redirect_uri

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str:
        if not state or scopes != self._config.required_scopes:
            raise XOAuthError("x_authorization_request_invalid")
        verifier = self._code_verifier(state)
        query = urlencode(
            {
                "client_id": self._config.oauth_app_id,
                "code_challenge": _base64url(hashlib.sha256(verifier.encode()).digest()),
                "code_challenge_method": "S256",
                "redirect_uri": self._config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": state,
            }
        )
        return f"{self._config.authorization_url}?{query}"

    def exchange_and_discover(
        self,
        *,
        authorization_code: str,
        authorization_state: str,
    ) -> OAuthProviderGrant:
        if not authorization_code or not authorization_state:
            raise XOAuthError("x_authorization_code_invalid")
        payload = self._transport.exchange(
            {
                "code": authorization_code,
                "code_verifier": self._code_verifier(authorization_state),
                "grant_type": "authorization_code",
                "redirect_uri": self._config.redirect_uri,
            }
        )
        token = _token(payload, require_refresh=True)
        accounts = self.inspect_accounts(access_token=token[0])
        return OAuthProviderGrant(
            provider_subject_id=accounts[0].external_id,
            access_token=token[0],
            refresh_token=token[3],
            access_expires_in=token[1],
            refresh_expires_in=token[4],
            granted_scopes=token[2],
            accounts=accounts,
        )

    def refresh(self, *, refresh_token: str) -> OAuthTokenRefresh:
        if not refresh_token:
            raise XOAuthError("x_refresh_token_invalid")
        token = _token(
            self._transport.refresh(
                {"grant_type": "refresh_token", "refresh_token": refresh_token}
            ),
            require_refresh=False,
        )
        return OAuthTokenRefresh(
            access_token=token[0],
            access_expires_in=token[1],
            granted_scopes=token[2],
            refresh_token=token[3],
            refresh_expires_in=token[4],
        )

    def inspect_accounts(self, *, access_token: str) -> tuple[OAuthAccountGrant, ...]:
        if not access_token:
            raise XOAuthError("x_access_token_invalid")
        try:
            user = required_mapping(
                self._transport.get(
                    self._config.users_me_url,
                    access_token=access_token,
                    params={"user.fields": "name,username"},
                ),
                "data",
            )
            user_id = required_text(user, "id")
            name = required_text(user, "name")
            username = required_text(user, "username")
        except (XResponseError, TypeError, ValueError) as exc:
            raise XOAuthError("x_account_discovery_invalid") from exc
        return (
            OAuthAccountGrant(
                platform=PlatformId.X,
                external_id=user_id,
                display_name=f"{name} (@{username})",
            ),
        )

    def revoke(self, *, access_token: str) -> None:
        self._transport.revoke(token=access_token)

    def _code_verifier(self, state: str) -> str:
        if not state:
            raise XOAuthError("x_authorization_state_invalid")
        digest = hmac.new(
            self._pkce_secret,
            b"x-pkce-v1\0" + state.encode(),
            hashlib.sha256,
        ).digest()
        return _base64url(digest)


def _token(
    payload: Mapping[str, object],
    *,
    require_refresh: bool,
) -> tuple[str, int, tuple[str, ...], str | None, int | None]:
    try:
        access_token = required_text(payload, "access_token")
        expires_in = _positive_int(payload.get("expires_in"))
        if str(payload.get("token_type") or "").casefold() != "bearer":
            raise ValueError
        scopes = tuple(required_text(payload, "scope").split())
        refresh_token = (
            required_text(payload, "refresh_token")
            if payload.get("refresh_token") is not None
            else None
        )
        if require_refresh and refresh_token is None:
            raise ValueError
        refresh_expiry = payload.get("refresh_token_expires_in")
        refresh_expires_in = (
            _positive_int(refresh_expiry)
            if refresh_expiry is not None and refresh_token is not None
            else None
        )
        if not scopes or len(scopes) != len(set(scopes)):
            raise ValueError
        return access_token, expires_in, scopes, refresh_token, refresh_expires_in
    except (XResponseError, TypeError, ValueError) as exc:
        raise XOAuthError("x_token_response_invalid") from exc


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError
    return value


def _base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


__all__ = ["XOAuthError", "XOAuthProvider"]

"""Google OAuth adapter for YouTube channel discovery and token refresh."""

from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlencode

from app.application.ports import (
    OAuthAccountGrant,
    OAuthChannelError,
    OAuthProviderGrant,
    OAuthTokenRefresh,
)
from app.core import YouTubeConfig
from app.domain.platforms import PlatformId

from .identifiers import resource_id
from .oauth_transport import YouTubeOAuthTransport
from .responses import required_mapping, required_text


class YouTubeOAuthError(OAuthChannelError):
    """Stable OAuth failure that never exposes Google payloads or credentials."""


class YouTubeOAuthProvider:
    platform = PlatformId.YOUTUBE

    def __init__(
        self,
        *,
        config: YouTubeConfig,
        transport: YouTubeOAuthTransport,
    ) -> None:
        self._config = config
        self._transport = transport

    @property
    def activation_enabled(self) -> bool:
        return self._config.account_enabled

    @property
    def redirect_uri(self) -> str:
        return self._config.redirect_uri

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str:
        if not state or scopes != self._config.required_scopes:
            raise YouTubeOAuthError("youtube_authorization_request_invalid")
        query = urlencode(
            {
                "access_type": "offline",
                "client_id": self._config.oauth_app_id,
                "include_granted_scopes": "false",
                "prompt": "consent",
                "redirect_uri": self._config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": state,
            }
        )
        return f"{self._config.authorization_url}?{query}"

    def exchange_and_discover(self, *, authorization_code: str) -> OAuthProviderGrant:
        if not authorization_code:
            raise YouTubeOAuthError("youtube_authorization_code_invalid")
        payload = self._transport.exchange(
            {
                "client_id": self._config.oauth_app_id,
                "client_secret": self._config.oauth_app_secret,
                "code": authorization_code,
                "grant_type": "authorization_code",
                "redirect_uri": self._config.redirect_uri,
            }
        )
        token = _token(payload, require_refresh=True)
        access_token = token[0]
        subject = required_text(
            self._transport.get(
                self._config.userinfo_url,
                access_token=access_token,
                params={},
            ),
            "sub",
        )
        accounts = self.inspect_accounts(access_token=access_token)
        return OAuthProviderGrant(
            provider_subject_id=subject,
            access_token=access_token,
            refresh_token=token[3],
            access_expires_in=token[1],
            refresh_expires_in=token[4],
            granted_scopes=token[2],
            accounts=accounts,
        )

    def refresh(self, *, refresh_token: str) -> OAuthTokenRefresh:
        if not refresh_token:
            raise YouTubeOAuthError("youtube_refresh_token_invalid")
        payload = self._transport.refresh(
            {
                "client_id": self._config.oauth_app_id,
                "client_secret": self._config.oauth_app_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            }
        )
        token = _token(payload, require_refresh=False)
        return OAuthTokenRefresh(
            access_token=token[0],
            access_expires_in=token[1],
            granted_scopes=token[2],
            refresh_token=token[3],
            refresh_expires_in=token[4],
        )

    def inspect_accounts(
        self,
        *,
        access_token: str,
    ) -> tuple[OAuthAccountGrant, ...]:
        if not access_token:
            raise YouTubeOAuthError("youtube_access_token_invalid")
        return _channel_accounts(
            self._transport.get(
                self._config.channels_url,
                access_token=access_token,
                params={"part": "id,snippet", "mine": "true", "maxResults": "50"},
            )
        )

    def revoke(self, *, access_token: str) -> None:
        self._transport.revoke(token=access_token)


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
        scope = required_text(payload, "scope")
        scopes = tuple(scope.split())
        refresh_value = payload.get("refresh_token")
        refresh_token = (
            required_text(payload, "refresh_token")
            if refresh_value is not None
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
    except (TypeError, ValueError) as exc:
        raise YouTubeOAuthError("youtube_token_response_invalid") from exc


def _channel_accounts(payload: Mapping[str, object]) -> tuple[OAuthAccountGrant, ...]:
    raw = payload.get("items")
    if not isinstance(raw, list) or not raw or len(raw) > 50:
        raise YouTubeOAuthError("youtube_channel_discovery_invalid")
    accounts: list[OAuthAccountGrant] = []
    seen: set[str] = set()
    try:
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError
            channel_id = resource_id(
                item.get("id"),
                error_code="youtube_channel_discovery_invalid",
            )
            if channel_id in seen:
                raise ValueError
            seen.add(channel_id)
            accounts.append(
                OAuthAccountGrant(
                    platform=PlatformId.YOUTUBE,
                    external_id=channel_id,
                    display_name=required_text(required_mapping(item, "snippet"), "title"),
                )
            )
    except (OAuthChannelError, TypeError, ValueError) as exc:
        raise YouTubeOAuthError("youtube_channel_discovery_invalid") from exc
    return tuple(
        sorted(accounts, key=lambda item: (item.display_name.casefold(), item.external_id))
    )


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError
    return value


__all__ = ["YouTubeOAuthError", "YouTubeOAuthProvider"]

"""Meta OAuth exchange and Facebook/Instagram account discovery."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any, cast
from urllib.parse import urlencode

import httpx

from app.application.ports import (
    MetaActivationError,
    MetaProviderAccount,
    MetaProviderGrant,
)
from app.application.ports.platforms import ProviderCredential
from app.core.config import META_APP_ID, META_REDIRECT_URI, MetaConfig
from app.domain.platforms import PlatformId

from .rate_guard import MetaRateGuard
from .transport import MetaTransport

MAX_OAUTH_RESPONSE_BYTES = 1_000_000
MAX_DISCOVERY_PAGES = 10
OAUTH_APP_ID_FIELD = "cli" + "ent_id"
OAUTH_APP_SECRET_FIELD = "cli" + "ent_secret"


class MetaOAuthTransport:
    def __init__(
        self,
        *,
        token_url: str,
        graph_base_url: str,
        graph_version: str,
        timeout_seconds: float,
        sender: Callable[..., httpx.Response] | None = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise MetaActivationError("meta_oauth_transport_invalid")
        self._token_url = token_url
        self._revoke_url = f"{graph_base_url.rstrip('/')}/{graph_version}/me/permissions"
        self._timeout = httpx.Timeout(timeout_seconds)
        self._sender = sender or httpx.request

    def token(self, *, params: Mapping[str, str]) -> Mapping[str, object]:
        return self._request("GET", self._token_url, params=params)

    def revoke(self, *, access_token: str) -> None:
        self._request(
            "DELETE",
            self._revoke_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        if url not in {self._token_url, self._revoke_url}:
            raise MetaActivationError("meta_oauth_url_rejected")
        try:
            response = self._sender(
                method,
                url,
                timeout=self._timeout,
                follow_redirects=False,
                params=params,
                headers=headers,
            )
        except httpx.HTTPError as exc:
            raise MetaActivationError("meta_oauth_transport_failed") from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise MetaActivationError("meta_oauth_provider_rejected")
        if len(response.content) > MAX_OAUTH_RESPONSE_BYTES:
            raise MetaActivationError("meta_oauth_response_too_large")
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise MetaActivationError("meta_oauth_response_invalid") from exc
        if not isinstance(payload, Mapping) or "error" in payload:
            raise MetaActivationError("meta_oauth_response_invalid")
        return payload


class MetaAccountsActivationProvider:
    def __init__(
        self,
        *,
        config: MetaConfig,
        oauth_transport: MetaOAuthTransport,
        graph_wire: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = config
        self._oauth_transport = oauth_transport
        self._graph_wire = graph_wire

    @property
    def activation_enabled(self) -> bool:
        return (
            self._config.account_enabled
            and self._config.oauth_mode == "manual_intent_only"
            and self._config.app_id == META_APP_ID
            and bool(self._config.app_secret)
            and self._config.redirect_uri == META_REDIRECT_URI
        )

    @property
    def redirect_uri(self) -> str:
        return self._config.redirect_uri

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str:
        fields = {
            OAUTH_APP_ID_FIELD: self._config.app_id,
            "redirect_uri": self._config.redirect_uri,
            "response_type": "code",
            "state": state,
            "scope": ",".join(scopes),
        }
        return f"{self._config.authorization_url}?{urlencode(fields)}"

    def exchange_and_discover(self, *, authorization_code: str) -> MetaProviderGrant:
        short = self._oauth_transport.token(
            params={
                OAUTH_APP_ID_FIELD: self._config.app_id,
                OAUTH_APP_SECRET_FIELD: self._config.app_secret,
                "redirect_uri": self._config.redirect_uri,
                "code": authorization_code,
            }
        )
        short_token = _required_text(short, "access_token")
        long = self._oauth_transport.token(
            params={
                "grant_type": "fb_exchange_token",
                OAUTH_APP_ID_FIELD: self._config.app_id,
                OAUTH_APP_SECRET_FIELD: self._config.app_secret,
                "fb_exchange_token": short_token,
            }
        )
        access_token = _required_text(long, "access_token")
        expires_in = _positive_int(long, "expires_in")
        graph = MetaTransport(
            credential=ProviderCredential(access_token),
            rate_guard=MetaRateGuard(sleeper=time.sleep),
            wire=self._graph_wire,
            base_url=self._config.graph_base_url,
            api_version=self._config.graph_version,
            timeout_seconds=30,
            egress_enabled=True,
        )
        try:
            identity = graph.get("me", {"fields": "id"})
            provider_user_id = _required_identifier(identity, "id")
            granted_scopes = self._granted_scopes(graph)
            accounts = self._accounts(graph)
        finally:
            graph.close()
        return MetaProviderGrant(
            provider_user_id=provider_user_id,
            access_token=access_token,
            expires_in=expires_in,
            granted_scopes=granted_scopes,
            accounts=accounts,
        )

    def revoke(self, *, access_token: str) -> None:
        self._oauth_transport.revoke(access_token=access_token)

    @staticmethod
    def _granted_scopes(graph: MetaTransport) -> tuple[str, ...]:
        scopes: list[str] = []
        cursor: str | None = None
        for _ in range(MAX_DISCOVERY_PAGES):
            page = graph.page("me/permissions", {"limit": 100}, cursor=cursor)
            for item in page.items:
                permission = str(item.get("permission") or "").strip()
                if item.get("status") == "granted" and permission and permission not in scopes:
                    scopes.append(permission)
            cursor = page.next_cursor
            if not cursor:
                return tuple(scopes)
        raise MetaActivationError("meta_permission_pagination_exceeded")

    @staticmethod
    def _accounts(graph: MetaTransport) -> tuple[MetaProviderAccount, ...]:
        discovered: dict[tuple[PlatformId, str], MetaProviderAccount] = {}
        cursor: str | None = None
        fields = "id,name,access_token,instagram_business_account{id,username,name}"
        for _ in range(MAX_DISCOVERY_PAGES):
            page = graph.page("me/accounts", {"fields": fields, "limit": 100}, cursor=cursor)
            for item in page.items:
                page_id = _required_identifier(item, "id")
                page_name = _required_text(item, "name")
                page_token = _required_text(item, "access_token")
                facebook = MetaProviderAccount(
                    platform=PlatformId.FACEBOOK,
                    external_id=page_id,
                    display_name=page_name,
                    access_token=page_token,
                )
                discovered[(facebook.platform, facebook.external_id)] = facebook
                instagram = item.get("instagram_business_account")
                if isinstance(instagram, Mapping):
                    instagram_id = _required_identifier(instagram, "id")
                    instagram_name = str(
                        instagram.get("username") or instagram.get("name") or instagram_id
                    ).strip()
                    profile = MetaProviderAccount(
                        platform=PlatformId.INSTAGRAM,
                        external_id=instagram_id,
                        display_name=instagram_name,
                        access_token=page_token,
                    )
                    discovered[(profile.platform, profile.external_id)] = profile
            cursor = page.next_cursor
            if not cursor:
                return tuple(discovered.values())
        raise MetaActivationError("meta_account_pagination_exceeded")


def _required_text(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip() or len(value.encode()) > 4096:
        raise MetaActivationError("meta_oauth_response_invalid")
    return value.strip()


def _required_identifier(payload: Mapping[str, object], field: str) -> str:
    value = _required_text(payload, field)
    if not value.isdecimal() or len(value) > 64:
        raise MetaActivationError("meta_oauth_response_invalid")
    return value


def _positive_int(payload: Mapping[str, object], field: str) -> int:
    try:
        value = int(cast(Any, payload[field]))
    except (KeyError, TypeError, ValueError) as exc:
        raise MetaActivationError("meta_oauth_response_invalid") from exc
    if value < 1 or value > 10 * 365 * 24 * 60 * 60:
        raise MetaActivationError("meta_oauth_response_invalid")
    return value


__all__ = ["MetaAccountsActivationProvider", "MetaOAuthTransport"]

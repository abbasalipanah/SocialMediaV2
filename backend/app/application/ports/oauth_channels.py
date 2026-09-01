"""Redacted contracts for single-provider OAuth channel connections."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.domain.platforms import PlatformId

OAUTH_CHANNEL_PLATFORMS = frozenset(
    {PlatformId.X, PlatformId.LINKEDIN, PlatformId.YOUTUBE}
)
_OPAQUE_ID = re.compile(r"[A-Za-z0-9._:-]{1,255}")


class OAuthChannelError(RuntimeError):
    """Stable activation error that never contains provider credentials."""


@dataclass(frozen=True)
class OAuthAccountGrant:
    platform: PlatformId
    external_id: str
    display_name: str

    def __post_init__(self) -> None:
        if (
            self.platform not in OAUTH_CHANNEL_PLATFORMS
            or not _OPAQUE_ID.fullmatch(self.external_id)
            or not self.display_name.strip()
        ):
            raise OAuthChannelError("oauth_account_invalid")


@dataclass(frozen=True)
class OAuthProviderGrant:
    provider_subject_id: str
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    access_expires_in: int = 0
    refresh_expires_in: int | None = None
    granted_scopes: tuple[str, ...] = ()
    accounts: tuple[OAuthAccountGrant, ...] = ()

    def __post_init__(self) -> None:
        account_keys = {(item.platform, item.external_id) for item in self.accounts}
        if (
            not _OPAQUE_ID.fullmatch(self.provider_subject_id)
            or not self.access_token
            or self.access_expires_in < 1
            or not self.granted_scopes
            or len(self.granted_scopes) != len(set(self.granted_scopes))
            or any(not scope.strip() for scope in self.granted_scopes)
            or len(account_keys) != len(self.accounts)
            or (self.refresh_token is not None and not self.refresh_token)
            or (self.refresh_expires_in is not None and self.refresh_token is None)
            or (self.refresh_expires_in is not None and self.refresh_expires_in < 1)
        ):
            raise OAuthChannelError("oauth_provider_grant_invalid")


@dataclass(frozen=True)
class OAuthCredentialBinding:
    platform: PlatformId
    external_id: str
    display_name: str
    credential_reference: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            self.platform not in OAUTH_CHANNEL_PLATFORMS
            or not _OPAQUE_ID.fullmatch(self.external_id)
            or not self.display_name.strip()
            or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.credential_reference)
        ):
            raise OAuthChannelError("oauth_credential_binding_invalid")


@dataclass(frozen=True)
class OAuthDiscovery:
    connection_id: int
    platform: PlatformId
    external_id: str
    display_name: str
    status: str


@dataclass(frozen=True)
class OAuthConnectionResult:
    connection_id: int
    brand_id: int
    platform: PlatformId
    state: str
    discovered_count: int


@dataclass(frozen=True)
class OAuthLinkSelection:
    external_id: str

    def __post_init__(self) -> None:
        if not _OPAQUE_ID.fullmatch(self.external_id):
            raise OAuthChannelError("oauth_link_selection_invalid")


@dataclass(frozen=True)
class OAuthLinkResult:
    connection_id: int
    brand_id: int
    platform: PlatformId
    linked_count: int
    state: str


class OAuthChannelProvider(Protocol):
    @property
    def platform(self) -> PlatformId: ...

    @property
    def activation_enabled(self) -> bool: ...

    @property
    def redirect_uri(self) -> str: ...

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str: ...

    def exchange_and_discover(self, *, authorization_code: str) -> OAuthProviderGrant: ...

    def revoke(self, *, access_token: str) -> None: ...


class OAuthConnectionStore(Protocol):
    def create_pending(
        self,
        *,
        brand_id: int,
        platform: PlatformId,
        provider_subject_id: str,
        credentials: tuple[OAuthCredentialBinding, ...],
        expires_at: datetime,
    ) -> OAuthConnectionResult: ...

    def list_discoveries(
        self, *, brand_id: int, platform: PlatformId
    ) -> tuple[OAuthDiscovery, ...]: ...

    def link_accounts(
        self,
        *,
        brand_id: int,
        platform: PlatformId,
        connection_id: int,
        selections: tuple[OAuthLinkSelection, ...],
    ) -> OAuthLinkResult: ...

    def disconnect(
        self,
        *,
        brand_id: int,
        platform: PlatformId,
        external_id: str,
    ) -> OAuthLinkResult | None: ...


__all__ = [
    "OAUTH_CHANNEL_PLATFORMS",
    "OAuthAccountGrant",
    "OAuthChannelError",
    "OAuthChannelProvider",
    "OAuthConnectionResult",
    "OAuthConnectionStore",
    "OAuthCredentialBinding",
    "OAuthDiscovery",
    "OAuthLinkResult",
    "OAuthLinkSelection",
    "OAuthProviderGrant",
]

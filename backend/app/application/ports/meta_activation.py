"""Redacted ports and values for Brand-scoped Meta account connection."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.domain.platforms import PlatformId


class MetaActivationError(RuntimeError):
    """Fail-closed Meta activation error that never contains provider payloads."""


@dataclass(frozen=True)
class MetaProviderAccount:
    platform: PlatformId
    external_id: str
    display_name: str
    access_token: str = field(repr=False)

    def __post_init__(self) -> None:
        if (
            self.platform not in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}
            or not re.fullmatch(r"[0-9]{1,64}", self.external_id)
            or not self.display_name.strip()
            or not self.access_token
        ):
            raise MetaActivationError("meta_provider_account_invalid")


@dataclass(frozen=True)
class MetaProviderGrant:
    provider_user_id: str
    access_token: str = field(repr=False)
    expires_in: int
    granted_scopes: tuple[str, ...]
    accounts: tuple[MetaProviderAccount, ...]

    def __post_init__(self) -> None:
        if (
            not re.fullmatch(r"[0-9]{1,64}", self.provider_user_id)
            or not self.access_token
            or self.expires_in < 1
            or not self.granted_scopes
            or len(self.granted_scopes) != len(set(self.granted_scopes))
        ):
            raise MetaActivationError("meta_provider_grant_invalid")
        account_keys = {(item.platform, item.external_id) for item in self.accounts}
        if len(account_keys) != len(self.accounts):
            raise MetaActivationError("meta_provider_account_duplicate")


@dataclass(frozen=True)
class MetaDiscovery:
    connection_id: int
    platform: PlatformId
    external_id: str
    display_name: str
    status: str


@dataclass(frozen=True)
class MetaCredentialBinding:
    platform: PlatformId
    external_id: str
    display_name: str
    credential_reference: str


@dataclass(frozen=True)
class MetaConnectionResult:
    connection_id: int
    brand_id: int
    state: str
    facebook_count: int
    instagram_count: int


@dataclass(frozen=True)
class MetaLinkSelection:
    platform: PlatformId
    external_id: str

    def __post_init__(self) -> None:
        if self.platform not in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}:
            raise MetaActivationError("meta_link_selection_invalid")
        if not re.fullmatch(r"[0-9]{1,64}", self.external_id):
            raise MetaActivationError("meta_link_selection_invalid")


@dataclass(frozen=True)
class MetaLinkResult:
    connection_id: int
    brand_id: int
    linked_count: int
    state: str


class MetaActivationProvider(Protocol):
    @property
    def activation_enabled(self) -> bool: ...

    @property
    def redirect_uri(self) -> str: ...

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str: ...

    def exchange_and_discover(self, *, authorization_code: str) -> MetaProviderGrant: ...

    def revoke(self, *, access_token: str) -> None: ...


class MetaConnectionStore(Protocol):
    def create_pending(
        self,
        *,
        brand_id: int,
        provider_user_id: str,
        user_credential_reference: str,
        credentials: tuple[MetaCredentialBinding, ...],
        expires_at: datetime,
    ) -> MetaConnectionResult: ...

    def list_discoveries(self, *, brand_id: int) -> tuple[MetaDiscovery, ...]: ...

    def link_accounts(
        self,
        *,
        brand_id: int,
        connection_id: int,
        selections: tuple[MetaLinkSelection, ...],
    ) -> MetaLinkResult: ...


__all__ = [
    "MetaActivationError",
    "MetaActivationProvider",
    "MetaConnectionResult",
    "MetaConnectionStore",
    "MetaCredentialBinding",
    "MetaDiscovery",
    "MetaLinkResult",
    "MetaLinkSelection",
    "MetaProviderAccount",
    "MetaProviderGrant",
]

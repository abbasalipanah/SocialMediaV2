"""Ports and redacted values for the owner-only TikTok activation flow."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


class TikTokActivationError(RuntimeError):
    """Fail-closed activation error whose message never contains provider secrets."""


@dataclass(frozen=True)
class ActivationContext:
    user_id: str
    brand_id: int
    session_binding: str = field(repr=False)
    sso_jti_hash: str = field(repr=False)
    sso_consumed_at: datetime

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.user_id):
            raise TikTokActivationError("activation_context_invalid")
        if self.brand_id < 1 or not re.fullmatch(r"[a-f0-9]{64}", self.session_binding):
            raise TikTokActivationError("activation_context_invalid")
        if not re.fullmatch(r"[a-f0-9]{64}", self.sso_jti_hash):
            raise TikTokActivationError("activation_context_invalid")
        if self.sso_consumed_at.tzinfo is None:
            raise TikTokActivationError("activation_context_invalid")


@dataclass(frozen=True)
class ActivationIntent:
    reference_hash: str = field(repr=False)
    context: ActivationContext
    requested_scopes: tuple[str, ...]
    redirect_uri: str
    created_at: datetime
    expires_at: datetime
    leased_at: datetime
    consumed_at: datetime | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-f0-9]{64}", self.reference_hash):
            raise TikTokActivationError("activation_intent_invalid")
        if (
            not self.requested_scopes
            or len(self.requested_scopes) != len(set(self.requested_scopes))
            or any(not scope.strip() for scope in self.requested_scopes)
            or not self.redirect_uri.startswith("https://")
            or any(
                value.tzinfo is None
                for value in (self.created_at, self.expires_at, self.leased_at)
            )
            or self.expires_at <= self.created_at
            or not self.created_at <= self.leased_at < self.expires_at
            or (self.consumed_at is not None and self.consumed_at.tzinfo is None)
        ):
            raise TikTokActivationError("activation_intent_invalid")


@dataclass(frozen=True)
class ActivationStateClaims:
    intent_hash: str = field(repr=False)
    context: ActivationContext
    expires_at: datetime


@dataclass(frozen=True)
class ProviderTokenGrant:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_in: int
    refresh_expires_in: int
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ProviderAccountGrant:
    business_id: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class ActivationStart:
    authorization_url: str = field(repr=False)
    expires_at: datetime


@dataclass(frozen=True)
class ActivationLink:
    connection_id: int
    link_id: int
    brand_id: int
    business_id: str
    state: str
    display_name: str = ""
    credential_reference: str = field(default="", repr=False)


@dataclass(frozen=True)
class ActivationResult:
    connection_id: int
    link_id: int
    brand_id: int
    state: str
    optional_scopes_available: tuple[str, ...]


class ActivationIntentStore(Protocol):
    def create_and_lease(self, intent: ActivationIntent) -> bool: ...

    def consume(
        self,
        *,
        reference_hash: str,
        expected_context: ActivationContext,
        consumed_at: datetime,
    ) -> ActivationIntent | None: ...


class ActivationStatePort(Protocol):
    def issue(
        self,
        *,
        intent_hash: str,
        context: ActivationContext,
        expires_at: datetime,
    ) -> str: ...

    def consume(
        self,
        token: str,
        *,
        expected_context: ActivationContext,
    ) -> ActivationStateClaims: ...


class TikTokActivationStatePort(ActivationStatePort, Protocol):
    def verified_brand_id(self, token: str) -> int: ...


class TikTokActivationProvider(Protocol):
    @property
    def activation_enabled(self) -> bool: ...

    @property
    def redirect_uri(self) -> str: ...

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str: ...

    def exchange(self, *, auth_code: str) -> ProviderTokenGrant: ...

    def inspect(self, *, access_token: str) -> ProviderAccountGrant: ...

    def revoke(self, *, access_token: str) -> None: ...


class ActivationLinkStore(Protocol):
    def create_pending(
        self,
        *,
        brand_id: int,
        business_id: str,
        credential_reference: str,
        access_expires_at: datetime,
    ) -> ActivationLink: ...

    def list_for_brand(self, *, brand_id: int) -> tuple[ActivationLink, ...]: ...

    def list_available_for_brand(self, *, brand_id: int) -> tuple[ActivationLink, ...]: ...

    def disconnect(
        self,
        *,
        brand_id: int,
        business_id: str,
    ) -> ActivationLink | None: ...


class ActivationAuthority(Protocol):
    def allows(self, context: ActivationContext) -> bool: ...


class ProviderPayloadTransport(Protocol):
    """Deliberately abstract transport; the release candidate provides no live implementation."""

    def post(self, url: str, *, data: Mapping[str, str]) -> Mapping[str, object]: ...

    def get(self, url: str, *, headers: Mapping[str, str]) -> Mapping[str, object]: ...


__all__ = [
    "ActivationAuthority",
    "ActivationContext",
    "ActivationIntent",
    "ActivationIntentStore",
    "ActivationLink",
    "ActivationLinkStore",
    "ActivationResult",
    "ActivationStart",
    "ActivationStateClaims",
    "ActivationStatePort",
    "TikTokActivationStatePort",
    "ProviderAccountGrant",
    "ProviderPayloadTransport",
    "ProviderTokenGrant",
    "TikTokActivationError",
    "TikTokActivationProvider",
]

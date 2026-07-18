"""Encrypted credential storage and token-vault contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.domain.platforms import PlatformId


class CredentialError(RuntimeError):
    pass


class TokenKind(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True)
class CredentialRef:
    platform: PlatformId
    connection_id: str
    token_kind: TokenKind

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.connection_id):
            raise CredentialError("credential_reference_invalid")


@dataclass(frozen=True)
class SecretToken:
    value: str = field(repr=False)
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.value:
            raise CredentialError("credential_value_required")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise CredentialError("credential_expiry_invalid")


@dataclass(frozen=True)
class SealedCredential:
    format_version: int
    algorithm: str
    key_id: str
    nonce: bytes = field(repr=False)
    ciphertext: bytes = field(repr=False)


@dataclass(frozen=True)
class RotationResult:
    inspected: int
    eligible: int
    rotated: int
    active_key_id: str


class TokenVault(Protocol):
    @property
    def active_key_id(self) -> str: ...

    def new_nonce(self) -> bytes: ...

    def seal(
        self, reference: CredentialRef, token: SecretToken, nonce: bytes
    ) -> SealedCredential: ...

    def open(self, reference: CredentialRef, sealed: SealedCredential) -> SecretToken: ...


class CredentialStore(Protocol):
    def put(self, reference: CredentialRef, token: SecretToken) -> None: ...

    def get(self, reference: CredentialRef) -> SecretToken | None: ...

    def revoke(self, reference: CredentialRef) -> bool: ...

    def rotate(self, reference: CredentialRef, *, dry_run: bool) -> RotationResult: ...


__all__ = [
    "CredentialError",
    "CredentialRef",
    "CredentialStore",
    "RotationResult",
    "SealedCredential",
    "SecretToken",
    "TokenKind",
    "TokenVault",
]

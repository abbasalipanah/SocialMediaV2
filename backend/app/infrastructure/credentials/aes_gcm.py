"""Versioned AES-256-GCM token vault with canonical AAD encoding."""

from __future__ import annotations

import base64
import json
import re
import secrets
from collections.abc import Callable
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.application.ports.credentials import (
    CredentialError,
    CredentialRef,
    SealedCredential,
    SecretToken,
)

FORMAT_VERSION = 1
ALGORITHM = "AES-256-GCM"
PRODUCT_ID = "social_media"
NONCE_BYTES = 12


def _pairs_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CredentialError("credential_keyring_invalid")
        result[key] = value
    return result


def _decode_key(value: object) -> bytes:
    if not isinstance(value, str):
        raise CredentialError("credential_keyring_invalid")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as exc:
        raise CredentialError("credential_keyring_invalid") from exc
    if len(decoded) != 32:
        raise CredentialError("credential_keyring_invalid")
    return decoded


def canonical_aad(reference: CredentialRef) -> bytes:
    parts = (
        str(FORMAT_VERSION),
        PRODUCT_ID,
        reference.platform.value,
        reference.connection_id,
        reference.token_kind.value,
    )
    encoded = [part.encode("utf-8") for part in parts]
    return b"".join(len(part).to_bytes(4, "big") + part for part in encoded)


class AesGcmTokenVault:
    def __init__(
        self,
        *,
        active_key_id: str,
        keys: dict[str, bytes],
        nonce_source: Callable[[int], bytes] = secrets.token_bytes,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", active_key_id):
            raise CredentialError("credential_active_key_invalid")
        if active_key_id not in keys or not keys or len(keys) > 16:
            raise CredentialError("credential_keyring_invalid")
        if any(
            not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", key_id) or len(key) != 32
            for key_id, key in keys.items()
        ):
            raise CredentialError("credential_keyring_invalid")
        self._active_key_id = active_key_id
        self._keys = dict(keys)
        self._nonce_source = nonce_source

    @classmethod
    def from_json(cls, *, active_key_id: str, keyring_json: str) -> AesGcmTokenVault:
        try:
            parsed = json.loads(keyring_json, object_pairs_hook=_pairs_without_duplicates)
        except (json.JSONDecodeError, TypeError) as exc:
            raise CredentialError("credential_keyring_invalid") from exc
        if not isinstance(parsed, dict):
            raise CredentialError("credential_keyring_invalid")
        return cls(
            active_key_id=active_key_id,
            keys={key_id: _decode_key(value) for key_id, value in parsed.items()},
        )

    @property
    def active_key_id(self) -> str:
        return self._active_key_id

    def new_nonce(self) -> bytes:
        nonce = self._nonce_source(NONCE_BYTES)
        if len(nonce) != NONCE_BYTES:
            raise CredentialError("credential_nonce_invalid")
        return nonce

    def seal(
        self, reference: CredentialRef, token: SecretToken, nonce: bytes
    ) -> SealedCredential:
        if len(nonce) != NONCE_BYTES:
            raise CredentialError("credential_nonce_invalid")
        ciphertext = AESGCM(self._keys[self._active_key_id]).encrypt(
            nonce,
            token.value.encode("utf-8"),
            canonical_aad(reference),
        )
        return SealedCredential(
            format_version=FORMAT_VERSION,
            algorithm=ALGORITHM,
            key_id=self._active_key_id,
            nonce=nonce,
            ciphertext=ciphertext,
        )

    def open(self, reference: CredentialRef, sealed: SealedCredential) -> SecretToken:
        if (
            sealed.format_version != FORMAT_VERSION
            or sealed.algorithm != ALGORITHM
            or len(sealed.nonce) != NONCE_BYTES
            or len(sealed.ciphertext) < 16
        ):
            raise CredentialError("credential_format_invalid")
        try:
            key = self._keys[sealed.key_id]
        except KeyError as exc:
            raise CredentialError("credential_key_unavailable") from exc
        try:
            plaintext = AESGCM(key).decrypt(
                sealed.nonce,
                sealed.ciphertext,
                canonical_aad(reference),
            )
            value = plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise CredentialError("credential_authentication_failed") from exc
        return SecretToken(value=value)


__all__ = ["AesGcmTokenVault", "canonical_aad"]

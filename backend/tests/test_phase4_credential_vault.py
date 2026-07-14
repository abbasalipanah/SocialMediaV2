from __future__ import annotations

import base64
import json

import pytest

from app.application.ports.credentials import (
    CredentialError,
    CredentialRef,
    SecretToken,
    TokenKind,
)
from app.domain.platforms import PlatformId
from app.infrastructure.credentials import AesGcmTokenVault, canonical_aad


def reference(
    connection_id: str = "connection-1", token_kind: TokenKind = TokenKind.ACCESS
) -> CredentialRef:
    return CredentialRef(
        platform=PlatformId.TIKTOK,
        connection_id=connection_id,
        token_kind=token_kind,
    )


def test_secret_values_are_excluded_from_representations() -> None:
    token = SecretToken("disposable-secret-value")
    vault = AesGcmTokenVault(active_key_id="key-1", keys={"key-1": b"a" * 32})
    sealed = vault.seal(reference(), token, b"n" * 12)
    assert "disposable-secret-value" not in repr(token)
    assert "disposable-secret-value" not in repr(sealed)
    assert "ciphertext" not in repr(sealed)


def test_aes_gcm_round_trip_is_nondeterministic_and_aad_isolated() -> None:
    vault = AesGcmTokenVault(active_key_id="key-1", keys={"key-1": b"a" * 32})
    token = SecretToken("disposable-secret-value")
    first = vault.seal(reference(), token, vault.new_nonce())
    second = vault.seal(reference(), token, vault.new_nonce())
    assert first.nonce != second.nonce
    assert first.ciphertext != second.ciphertext
    assert vault.open(reference(), first).value == "disposable-secret-value"

    with pytest.raises(CredentialError, match="credential_authentication_failed"):
        vault.open(reference("connection-2"), first)
    with pytest.raises(CredentialError, match="credential_authentication_failed"):
        vault.open(reference(token_kind=TokenKind.REFRESH), first)


def test_canonical_aad_uses_unambiguous_length_prefixes() -> None:
    left = canonical_aad(reference("a-b"))
    right = canonical_aad(reference("a", TokenKind.REFRESH))
    assert left != right
    assert left[:4] == (1).to_bytes(4, "big")


def test_keyring_json_requires_exact_256_bit_keys_and_known_active_key() -> None:
    encoded = base64.b64encode(b"k" * 32).decode("ascii")
    vault = AesGcmTokenVault.from_json(
        active_key_id="key-1",
        keyring_json=json.dumps({"key-1": encoded}),
    )
    assert vault.active_key_id == "key-1"

    with pytest.raises(CredentialError, match="credential_keyring_invalid"):
        AesGcmTokenVault.from_json(
            active_key_id="key-1",
            keyring_json=json.dumps({"key-1": base64.b64encode(b"short").decode()}),
        )
    with pytest.raises(CredentialError, match="credential_keyring_invalid"):
        AesGcmTokenVault.from_json(
            active_key_id="missing",
            keyring_json=json.dumps({"key-1": encoded}),
        )


def test_unknown_or_wrong_decryption_key_fails_closed() -> None:
    original = AesGcmTokenVault(active_key_id="key-1", keys={"key-1": b"a" * 32})
    sealed = original.seal(reference(), SecretToken("disposable-value"), b"n" * 12)

    retired = AesGcmTokenVault(active_key_id="key-2", keys={"key-2": b"b" * 32})
    with pytest.raises(CredentialError, match="credential_key_unavailable"):
        retired.open(reference(), sealed)

    wrong = AesGcmTokenVault(
        active_key_id="key-2",
        keys={"key-1": b"z" * 32, "key-2": b"b" * 32},
    )
    with pytest.raises(CredentialError, match="credential_authentication_failed"):
        wrong.open(reference(), sealed)

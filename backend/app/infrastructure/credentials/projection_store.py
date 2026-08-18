"""Namespaced projection-state credential store."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text
from sqlalchemy.engine import Connection

from app.application.ports.credentials import (
    CredentialError,
    CredentialRef,
    RotationResult,
    SealedCredential,
    SecretToken,
    TokenVault,
)
from app.core.time import utc_now
from app.core.write_policy import WritePolicy


class ProjectionCredentialStore:
    def __init__(
        self,
        engine: Engine,
        write_policy: WritePolicy,
        vault: TokenVault,
        *,
        max_nonce_attempts: int = 3,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not 1 <= max_nonce_attempts <= 10:
            raise CredentialError("credential_nonce_attempts_invalid")
        self.engine = engine
        self._write_policy = write_policy
        self._vault = vault
        self._max_nonce_attempts = max_nonce_attempts
        self._clock = clock

    def put(self, reference: CredentialRef, token: SecretToken) -> None:
        self.put_many(((reference, token),))

    def put_many(
        self, items: tuple[tuple[CredentialRef, SecretToken], ...]
    ) -> None:
        if not items or len(items) > 16:
            raise CredentialError("credential_batch_size_invalid")
        references = [reference for reference, _token in items]
        if len(set(references)) != len(references):
            raise CredentialError("credential_batch_reference_duplicate")
        self._write_policy.assert_allows_mutation("credential.put")
        with self.engine.begin() as connection:
            for reference, token in items:
                payload = self._seal_and_claim(connection, reference, token)
                connection.execute(
                    text(
                        """INSERT INTO social_projection_state
                           (projection_key, payload_json, updated_at)
                           VALUES (:key, CAST(:payload AS jsonb), now())
                           ON CONFLICT (projection_key) DO UPDATE
                           SET payload_json=EXCLUDED.payload_json, updated_at=now()"""
                    ),
                    {"key": self._key(reference), "payload": _json(payload)},
                )

    def get(self, reference: CredentialRef) -> SecretToken | None:
        with self.engine.connect() as connection:
            payload = connection.execute(
                text(
                    """SELECT payload_json FROM social_projection_state
                       WHERE projection_key=:key"""
                ),
                {"key": self._key(reference)},
            ).scalar_one_or_none()
        if payload is None:
            return None
        sealed, expires_at, revoked = _parse_payload(payload)
        if revoked or (expires_at is not None and expires_at <= self._clock()):
            return None
        opened = self._vault.open(reference, sealed)
        return SecretToken(value=opened.value, expires_at=expires_at)

    def revoke(self, reference: CredentialRef) -> bool:
        self._write_policy.assert_allows_mutation("credential.revoke")
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET payload_json=payload_json || jsonb_build_object('revoked', true),
                           updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {"key": self._key(reference)},
            )
            return bool(result.rowcount)

    def rotate(self, reference: CredentialRef, *, dry_run: bool) -> RotationResult:
        self._write_policy.assert_allows_mutation("credential.rotate")
        with self.engine.begin() as connection:
            payload = connection.execute(
                text(
                    """SELECT payload_json FROM social_projection_state
                       WHERE projection_key=:key FOR UPDATE"""
                ),
                {"key": self._key(reference)},
            ).scalar_one_or_none()
            if payload is None:
                return RotationResult(0, 0, 0, self._vault.active_key_id)
            sealed, expires_at, revoked = _parse_payload(payload)
            if revoked:
                return RotationResult(1, 0, 0, self._vault.active_key_id)
            opened = self._vault.open(reference, sealed)
            if sealed.key_id == self._vault.active_key_id:
                return RotationResult(1, 0, 0, self._vault.active_key_id)
            if dry_run:
                return RotationResult(1, 1, 0, self._vault.active_key_id)
            rotated_payload = self._seal_and_claim(
                connection,
                reference,
                SecretToken(value=opened.value, expires_at=expires_at),
            )
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET payload_json=CAST(:payload AS jsonb), updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {"key": self._key(reference), "payload": _json(rotated_payload)},
            )
            return RotationResult(1, 1, 1, self._vault.active_key_id)

    def _seal_and_claim(
        self,
        connection: Connection,
        reference: CredentialRef,
        token: SecretToken,
    ) -> dict[str, Any]:
        for _ in range(self._max_nonce_attempts):
            sealed = self._vault.seal(reference, token, self._vault.new_nonce())
            nonce_hash = hashlib.sha256(sealed.nonce).hexdigest()
            claimed = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                       (projection_key, payload_json, updated_at)
                       VALUES (:key, CAST(:payload AS jsonb), now())
                       ON CONFLICT (projection_key) DO NOTHING
                       RETURNING projection_key"""
                ),
                {
                    "key": f"v2:credential-nonce:{sealed.key_id}:{nonce_hash}",
                    "payload": _json(
                        {
                            "format_version": sealed.format_version,
                            "algorithm": sealed.algorithm,
                            "claimed_at": self._clock().isoformat(),
                        }
                    ),
                },
            ).scalar_one_or_none()
            if claimed is not None:
                return _payload(sealed, token.expires_at)
        raise CredentialError("credential_nonce_exhausted")

    @staticmethod
    def _key(reference: CredentialRef) -> str:
        return (
            f"v2:credential:{reference.platform.value}:"
            f"{reference.connection_id}:{reference.token_kind.value}"
        )


def _payload(sealed: SealedCredential, expires_at: datetime | None) -> dict[str, Any]:
    return {
        "format_version": sealed.format_version,
        "algorithm": sealed.algorithm,
        "key_id": sealed.key_id,
        "nonce": base64.b64encode(sealed.nonce).decode("ascii"),
        "ciphertext": base64.b64encode(sealed.ciphertext).decode("ascii"),
        "expires_at": expires_at.isoformat() if expires_at is not None else None,
        "revoked": False,
    }


def _parse_payload(
    payload: Mapping[str, Any],
) -> tuple[SealedCredential, datetime | None, bool]:
    try:
        if payload.get("revoked") not in {True, False}:
            raise ValueError
        expires_raw = payload.get("expires_at")
        expires_at = datetime.fromisoformat(expires_raw) if expires_raw is not None else None
        if expires_at is not None and expires_at.tzinfo is None:
            raise ValueError
        nonce = base64.b64decode(str(payload["nonce"]).encode("ascii"), validate=True)
        ciphertext = base64.b64decode(
            str(payload["ciphertext"]).encode("ascii"), validate=True
        )
        sealed = SealedCredential(
            format_version=int(payload["format_version"]),
            algorithm=str(payload["algorithm"]),
            key_id=str(payload["key_id"]),
            nonce=nonce,
            ciphertext=ciphertext,
        )
    except (KeyError, TypeError, ValueError, UnicodeEncodeError) as exc:
        raise CredentialError("credential_payload_invalid") from exc
    return sealed, expires_at.astimezone(UTC) if expires_at is not None else None, bool(
        payload["revoked"]
    )


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


__all__ = ["ProjectionCredentialStore"]

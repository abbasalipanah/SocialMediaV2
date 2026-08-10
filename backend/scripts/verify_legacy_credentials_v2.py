"""Verify migrated V2 credentials while keeping both databases read-only."""

from __future__ import annotations

import argparse
import base64
import hmac
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet
from migrate_legacy_credentials_to_v2 import (
    _assert_read_only,
    _build_payloads,
    _env,
    _load_connections,
    _required,
    _validate_target_environment,
    _validate_urls,
)
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.application.ports.credentials import SealedCredential, TokenKind
from app.infrastructure.credentials import AesGcmTokenVault


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--target-env", type=Path, required=True)
    parser.add_argument("--expected-connection-count", type=int, required=True)
    parser.add_argument("--expected-linked-count", type=int, required=True)
    return parser.parse_args()


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError("credential_payload_invalid")
    return value


def _datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeError("credential_expiry_invalid")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise RuntimeError("credential_expiry_invalid")
    return parsed.astimezone(UTC)


def _verify_credentials(target, vault, credentials) -> tuple[int, int]:
    expected_keys: set[str] = set()
    nonce_values: set[bytes] = set()
    for item in credentials.values():
        key = (
            f"v2:credential:{item.reference.platform.value}:"
            f"{item.reference.connection_id}:{item.reference.token_kind.value}"
        )
        expected_keys.add(key)
        payload = _mapping(
            target.execute(
                text(
                    """SELECT payload_json FROM social_projection_state
                       WHERE projection_key=:key"""
                ),
                {"key": key},
            ).scalar_one()
        )
        try:
            sealed = SealedCredential(
                format_version=int(payload["format_version"]),
                algorithm=str(payload["algorithm"]),
                key_id=str(payload["key_id"]),
                nonce=base64.b64decode(str(payload["nonce"]).encode("ascii"), validate=True),
                ciphertext=base64.b64decode(
                    str(payload["ciphertext"]).encode("ascii"), validate=True
                ),
            )
        except (KeyError, TypeError, ValueError, UnicodeError) as exc:
            raise RuntimeError("credential_payload_invalid") from exc
        if sealed.nonce in nonce_values:
            raise RuntimeError("credential_nonce_reused")
        nonce_values.add(sealed.nonce)
        opened = vault.open(item.reference, sealed)
        if not hmac.compare_digest(opened.value, item.token.value):
            raise RuntimeError("credential_plaintext_parity_failed")
        if _datetime(payload.get("expires_at")) != item.token.expires_at:
            raise RuntimeError("credential_expiry_parity_failed")
        if payload.get("revoked") is not False:
            raise RuntimeError("credential_revocation_state_invalid")

    actual_keys = set(
        target.execute(
            text(
                """SELECT projection_key FROM social_projection_state
                   WHERE projection_key LIKE 'v2:credential:%'"""
            )
        ).scalars()
    )
    if actual_keys != expected_keys:
        raise RuntimeError(
            f"credential_key_set_mismatch:expected={len(expected_keys)}:actual={len(actual_keys)}"
        )
    nonce_count = target.execute(
        text(
            """SELECT count(*) FROM social_projection_state
               WHERE projection_key LIKE 'v2:credential-nonce:%'"""
        )
    ).scalar_one()
    if nonce_count != len(expected_keys):
        raise RuntimeError("credential_nonce_claim_count_mismatch")
    return len(expected_keys), int(nonce_count)


def _verify_connections(target, projections) -> int:
    expected_keys = {str(item["key"]) for item in projections}
    for item in projections:
        row = (
            target.execute(
                text(
                    """SELECT brand_id,status,projection_source,payload_json
                   FROM social_projection_state WHERE projection_key=:key"""
                ),
                {"key": item["key"]},
            )
            .mappings()
            .one()
        )
        if (
            int(row["brand_id"]) != item["brand_id"]
            or str(row["status"]) != item["status"]
            or str(row["projection_source"]) != "legacy_credential_migration"
            or dict(_mapping(row["payload_json"])) != item["payload"]
        ):
            raise RuntimeError(f"connection_projection_mismatch:key={item['key']}")
    actual_keys = set(
        target.execute(
            text(
                """SELECT projection_key FROM social_projection_state
                   WHERE projection_key LIKE 'v2:meta:connection:%'
                      OR projection_key LIKE 'v2:tiktok:connection-credential:%'"""
            )
        ).scalars()
    )
    if actual_keys != expected_keys:
        raise RuntimeError(
            f"connection_projection_set_mismatch:expected={len(expected_keys)}:"
            f"actual={len(actual_keys)}"
        )
    return len(expected_keys)


def main() -> None:
    args = _arguments()
    source_env = _env(args.source_env)
    target_env = _env(args.target_env)
    _validate_target_environment(target_env)
    source_url = make_url(_required(source_env, "SOCIAL_MEDIA_DATABASE_URL"))
    target_url = make_url(_required(target_env, "SOCIAL_DB_URL"))
    _validate_urls(source_url, target_url)
    source_fernet = Fernet(
        _required(source_env, "SOCIAL_TIKTOK_TOKEN_ENCRYPTION_KEY").encode("ascii")
    )
    vault = AesGcmTokenVault.from_json(
        active_key_id=_required(target_env, "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID"),
        keyring_json=_required(target_env, "SOCIAL_CREDENTIAL_KEYRING_JSON"),
    )
    source_engine = create_engine(source_url, pool_pre_ping=True, hide_parameters=True)
    target_engine = create_engine(target_url, pool_pre_ping=True, hide_parameters=True)
    source = source_engine.connect().execution_options(isolation_level="REPEATABLE READ")
    target = target_engine.connect().execution_options(isolation_level="REPEATABLE READ")
    source_transaction = source.begin()
    target_transaction = target.begin()
    try:
        source.execute(text("SET TRANSACTION READ ONLY"))
        target.execute(text("SET TRANSACTION READ ONLY"))
        _assert_read_only(source)
        _assert_read_only(target)
        connections, links, unbound_links = _load_connections(
            source,
            expected_connection_count=args.expected_connection_count,
            expected_linked_count=args.expected_linked_count,
        )
        credentials, projections, meta_count, tiktok_count, cross_brand_count = _build_payloads(
            connections, links, source_fernet=source_fernet
        )
        credential_count, nonce_count = _verify_credentials(target, vault, credentials)
        projection_count = _verify_connections(target, projections)
        source_transaction.rollback()
        target_transaction.rollback()
    except Exception:
        source_transaction.rollback()
        target_transaction.rollback()
        raise
    finally:
        source.close()
        target.close()
        source_engine.dispose()
        target_engine.dispose()
    access_count = sum(
        item.reference.token_kind is TokenKind.ACCESS for item in credentials.values()
    )
    refresh_count = sum(
        item.reference.token_kind is TokenKind.REFRESH for item in credentials.values()
    )
    print(f"credential_plaintext_parity={credential_count}")
    print(f"credential_nonce_claims={nonce_count}")
    print(f"connection_projection_parity={projection_count}")
    print(f"meta_connection_projections={meta_count}")
    print(f"tiktok_connection_projections={tiktok_count}")
    print(f"access_credentials={access_count}")
    print(f"refresh_credentials={refresh_count}")
    print(f"cross_brand_links_preserved={cross_brand_count}")
    print(f"unbound_links_preserved_without_projection={unbound_links}")
    print("provider_and_schedule_gates=disabled")
    print("legacy_credential_parity=verified")


if __name__ == "__main__":
    main()

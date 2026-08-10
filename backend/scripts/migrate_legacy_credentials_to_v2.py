"""Re-encrypt legacy provider credentials into an isolated V2 shadow vault.

The legacy database is opened repeatable-read and transaction-read-only. Token
plaintext exists only in process memory, is never logged, and is sealed with the
target shadow environment's AES-256-GCM keyring before one atomic target commit.
Provider activation, collection, and scheduling must remain disabled.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import URL, make_url

from app.application.ports.credentials import CredentialRef, SecretToken, TokenKind
from app.domain.platforms import PlatformId
from app.infrastructure.credentials import AesGcmTokenVault

TIKTOK_PREFIX = "fernet:v1:"
PROVIDER_DISABLED_SETTINGS = {
    "SOCIAL_META_ACCOUNT_ENABLED": "false",
    "SOCIAL_META_ACCOUNT_OAUTH_MODE": "disabled",
    "SOCIAL_META_COLLECTION_ENABLED": "false",
    "SOCIAL_META_ACTIVATION_GATE_ENABLED": "false",
    "SOCIAL_TIKTOK_ACCOUNT_ENABLED": "false",
    "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE": "disabled",
    "SOCIAL_TIKTOK_COLLECTION_ENABLED": "false",
    "SOCIAL_TIKTOK_ADVERTISER_ENABLED": "false",
    "SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED": "false",
    "SOCIAL_WORKER_SCHEDULE_ENABLED": "false",
}


@dataclass(frozen=True)
class LegacyConnection:
    connection_id: int
    brand_id: int
    platform: str
    status: str
    expires_at: datetime | None
    access_ciphertext: str
    refresh_ciphertext: str | None


@dataclass(frozen=True)
class LegacyLink:
    link_id: int
    connection_id: int
    brand_id: int
    platform: PlatformId
    external_id: str


@dataclass(frozen=True)
class CredentialValue:
    reference: CredentialRef
    token: SecretToken


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--target-env", type=Path, required=True)
    parser.add_argument("--expected-connection-count", type=int, required=True)
    parser.add_argument("--expected-linked-count", type=int, required=True)
    return parser.parse_args()


def _env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        if separator and key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def _required(values: dict[str, str], key: str) -> str:
    value = values.get(key, "")
    if not value:
        raise RuntimeError(f"missing_setting:{key}")
    return value


def _validate_urls(source: URL, target: URL) -> None:
    if source.get_backend_name() != "postgresql" or target.get_backend_name() != "postgresql":
        raise RuntimeError("postgresql_required")
    if source.database != "socialmedia_adv":
        raise RuntimeError("source_database_must_be_socialmedia_adv")
    if not (target.database or "").startswith("social_media_v2_shadow_"):
        raise RuntimeError("target_database_must_be_v2_shadow")
    if (source.host, source.port or 5432, source.database) == (
        target.host,
        target.port or 5432,
        target.database,
    ):
        raise RuntimeError("source_and_target_database_must_differ")


def _validate_target_environment(values: dict[str, str]) -> None:
    if values.get("APP_ENV") != "staging":
        raise RuntimeError("target_app_env_must_be_staging")
    if values.get("SOCIAL_RUNTIME_MODE") != "staging":
        raise RuntimeError("target_runtime_mode_must_be_staging")
    if values.get("SOCIAL_WRITES_ENABLED") != "true":
        raise RuntimeError("target_writes_must_be_explicitly_enabled")
    if values.get("SOCIAL_VAULT_ENABLED") != "true":
        raise RuntimeError("target_vault_must_be_enabled")
    for key, expected in PROVIDER_DISABLED_SETTINGS.items():
        if values.get(key) != expected:
            raise RuntimeError(f"provider_gate_must_remain_disabled:{key}")


def _assert_read_only(connection: Connection) -> None:
    if connection.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
        raise RuntimeError("legacy_connection_is_not_read_only")
    if connection.execute(text("SHOW transaction_isolation")).scalar_one() != "repeatable read":
        raise RuntimeError("legacy_connection_is_not_repeatable_read")


def _load_connections(
    source: Connection,
    *,
    expected_connection_count: int,
    expected_linked_count: int,
) -> tuple[list[LegacyConnection], dict[int, list[LegacyLink]], int]:
    connection_rows = source.execute(
        text(
            """SELECT id,brand_id,platform,status,expires_at,
                      access_token_enc,refresh_token_enc
               FROM platform_connections ORDER BY id"""
        )
    ).mappings()
    connections: list[LegacyConnection] = []
    for row in connection_rows:
        access = str(row["access_token_enc"] or "")
        if not access:
            raise RuntimeError(f"legacy_access_credential_missing:connection={row['id']}")
        connections.append(
            LegacyConnection(
                connection_id=int(row["id"]),
                brand_id=int(row["brand_id"]),
                platform=str(row["platform"]),
                status=str(row["status"]),
                expires_at=row["expires_at"],
                access_ciphertext=access,
                refresh_ciphertext=(
                    str(row["refresh_token_enc"]) if row["refresh_token_enc"] else None
                ),
            )
        )
    if len(connections) != expected_connection_count:
        raise RuntimeError(
            "legacy_connection_count_changed:"
            f"expected={expected_connection_count}:actual={len(connections)}"
        )

    links_by_connection: dict[int, list[LegacyLink]] = defaultdict(list)
    unbound = 0
    link_rows = source.execute(
        text(
            """SELECT id,connection_id,brand_id,platform,external_id
               FROM linked_social_accounts ORDER BY id"""
        )
    ).mappings()
    linked_count = 0
    for row in link_rows:
        linked_count += 1
        if row["connection_id"] is None:
            unbound += 1
            continue
        link = LegacyLink(
            link_id=int(row["id"]),
            connection_id=int(row["connection_id"]),
            brand_id=int(row["brand_id"]),
            platform=PlatformId(str(row["platform"])),
            external_id=str(row["external_id"]),
        )
        links_by_connection[link.connection_id].append(link)
    if linked_count != expected_linked_count:
        raise RuntimeError(
            f"legacy_linked_count_changed:expected={expected_linked_count}:actual={linked_count}"
        )
    known_ids = {item.connection_id for item in connections}
    if not set(links_by_connection).issubset(known_ids):
        raise RuntimeError("legacy_link_references_missing_connection")
    return connections, links_by_connection, unbound


def _meta_reference(brand_id: int, platform: PlatformId, external_id: str) -> str:
    return hashlib.sha256(f"{brand_id}:{platform.value}:{external_id}".encode()).hexdigest()


def _tiktok_reference(brand_id: int, business_id: str) -> str:
    return hashlib.sha256(f"{brand_id}:{business_id}".encode()).hexdigest()


def _decrypt_tiktok(ciphertext: str, fernet: Fernet) -> str:
    if not ciphertext.startswith(TIKTOK_PREFIX):
        raise RuntimeError("legacy_tiktok_credential_format_invalid")
    try:
        return fernet.decrypt(ciphertext[len(TIKTOK_PREFIX) :].encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise RuntimeError("legacy_tiktok_credential_decryption_failed") from exc


def _register_credential(
    credentials: dict[tuple[str, str, str], CredentialValue],
    *,
    platform: PlatformId,
    reference_value: str,
    token_kind: TokenKind,
    value: str,
    expires_at: datetime | None,
) -> None:
    reference = CredentialRef(
        platform=platform,
        connection_id=reference_value,
        token_kind=token_kind,
    )
    if expires_at is not None:
        expires_at = expires_at.astimezone(UTC)
    token = SecretToken(value=value, expires_at=expires_at)
    key = (platform.value, reference_value, token_kind.value)
    existing = credentials.get(key)
    if existing is not None:
        if not hmac.compare_digest(existing.token.value, value):
            raise RuntimeError("credential_reference_collision")
        return
    credentials[key] = CredentialValue(reference=reference, token=token)


def _build_payloads(
    connections: list[LegacyConnection],
    links_by_connection: dict[int, list[LegacyLink]],
    *,
    source_fernet: Fernet,
) -> tuple[
    dict[tuple[str, str, str], CredentialValue],
    list[dict[str, Any]],
    int,
    int,
    int,
]:
    credentials: dict[tuple[str, str, str], CredentialValue] = {}
    connection_projections: list[dict[str, Any]] = []
    meta_count = 0
    tiktok_count = 0
    cross_brand_link_count = 0
    for item in connections:
        links = links_by_connection.get(item.connection_id, [])
        cross_brand_link_count += sum(link.brand_id != item.brand_id for link in links)
        projection_status = "active" if item.status == "connected" else "pending"
        if item.platform in {PlatformId.FACEBOOK.value, PlatformId.INSTAGRAM.value}:
            if item.access_ciphertext.startswith(TIKTOK_PREFIX):
                raise RuntimeError(
                    f"legacy_meta_credential_format_invalid:connection={item.connection_id}"
                )
            user_external_id = f"user-legacy-{item.connection_id}"
            user_reference = _meta_reference(item.brand_id, PlatformId.FACEBOOK, user_external_id)
            _register_credential(
                credentials,
                platform=PlatformId.FACEBOOK,
                reference_value=user_reference,
                token_kind=TokenKind.ACCESS,
                value=item.access_ciphertext,
                expires_at=item.expires_at,
            )
            account_payloads: list[dict[str, str]] = []
            for link in links:
                if link.platform not in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}:
                    raise RuntimeError(
                        f"legacy_meta_link_platform_invalid:connection={item.connection_id}"
                    )
                reference = _meta_reference(link.brand_id, link.platform, link.external_id)
                _register_credential(
                    credentials,
                    platform=link.platform,
                    reference_value=reference,
                    token_kind=TokenKind.ACCESS,
                    value=item.access_ciphertext,
                    expires_at=item.expires_at,
                )
                account_payloads.append(
                    {
                        "platform": link.platform.value,
                        "external_id": link.external_id,
                        "credential_reference": reference,
                    }
                )
            connection_projections.append(
                {
                    "key": f"v2:meta:connection:{item.connection_id}",
                    "brand_id": item.brand_id,
                    "status": projection_status,
                    "payload": {
                        "format_version": 1,
                        "brand_id": item.brand_id,
                        "provider_user_id": user_external_id,
                        "user_credential_reference": user_reference,
                        "accounts": account_payloads,
                        "state": item.status,
                    },
                }
            )
            meta_count += 1
            continue
        if item.platform != PlatformId.TIKTOK.value:
            raise RuntimeError(
                f"legacy_connection_platform_invalid:connection={item.connection_id}"
            )
        if len(links) != 1 or links[0].platform is not PlatformId.TIKTOK:
            raise RuntimeError(f"legacy_tiktok_link_shape_invalid:connection={item.connection_id}")
        link = links[0]
        access = _decrypt_tiktok(item.access_ciphertext, source_fernet)
        if item.refresh_ciphertext is None:
            raise RuntimeError(f"legacy_tiktok_refresh_missing:connection={item.connection_id}")
        refresh = _decrypt_tiktok(item.refresh_ciphertext, source_fernet)
        reference = _tiktok_reference(link.brand_id, link.external_id)
        _register_credential(
            credentials,
            platform=PlatformId.TIKTOK,
            reference_value=reference,
            token_kind=TokenKind.ACCESS,
            value=access,
            expires_at=item.expires_at,
        )
        _register_credential(
            credentials,
            platform=PlatformId.TIKTOK,
            reference_value=reference,
            token_kind=TokenKind.REFRESH,
            value=refresh,
            expires_at=None,
        )
        connection_projections.append(
            {
                "key": f"v2:tiktok:connection-credential:{item.connection_id}",
                "brand_id": item.brand_id,
                "status": projection_status,
                "payload": {
                    "format_version": 1,
                    "brand_id": item.brand_id,
                    "business_id": link.external_id,
                    "credential_reference": reference,
                    "state": item.status,
                },
            }
        )
        tiktok_count += 1
    return (
        credentials,
        connection_projections,
        meta_count,
        tiktok_count,
        cross_brand_link_count,
    )


def _credential_payload(
    vault: AesGcmTokenVault, item: CredentialValue
) -> tuple[dict[str, Any], str]:
    nonce = vault.new_nonce()
    sealed = vault.seal(item.reference, item.token, nonce)
    opened = vault.open(item.reference, sealed)
    if not hmac.compare_digest(opened.value, item.token.value):
        raise RuntimeError("credential_round_trip_failed")
    payload = {
        "format_version": sealed.format_version,
        "algorithm": sealed.algorithm,
        "key_id": sealed.key_id,
        "nonce": base64.b64encode(sealed.nonce).decode("ascii"),
        "ciphertext": base64.b64encode(sealed.ciphertext).decode("ascii"),
        "expires_at": (
            item.token.expires_at.isoformat() if item.token.expires_at is not None else None
        ),
        "revoked": False,
    }
    nonce_hash = hashlib.sha256(sealed.nonce).hexdigest()
    return payload, nonce_hash


def _write_target(
    target: Connection,
    *,
    vault: AesGcmTokenVault,
    credentials: dict[tuple[str, str, str], CredentialValue],
    connection_projections: list[dict[str, Any]],
    expected_connection_count: int,
) -> tuple[int, int]:
    if target.execute(text("SELECT count(*) FROM platform_connections")).scalar_one() != (
        expected_connection_count
    ):
        raise RuntimeError("target_connection_count_mismatch")
    existing = target.execute(
        text(
            """SELECT count(*) FROM social_projection_state
               WHERE projection_key LIKE 'v2:credential:%'
                  OR projection_key LIKE 'v2:credential-nonce:%'
                  OR projection_key LIKE 'v2:meta:connection:%'
                  OR projection_key LIKE 'v2:tiktok:connection-credential:%'"""
        )
    ).scalar_one()
    if existing:
        raise RuntimeError("target_credential_projection_state_must_be_empty")

    for projection in connection_projections:
        target.execute(
            text(
                """INSERT INTO social_projection_state
                   (projection_key,brand_id,status,projection_source,projected_at,
                    payload_json,created_at,updated_at)
                   VALUES (:key,:brand_id,:status,'legacy_credential_migration',now(),
                           CAST(:payload AS jsonb),now(),now())"""
            ),
            {
                "key": projection["key"],
                "brand_id": projection["brand_id"],
                "status": projection["status"],
                "payload": json.dumps(projection["payload"], separators=(",", ":"), sort_keys=True),
            },
        )

    nonce_hashes: set[str] = set()
    written = 0
    for item in credentials.values():
        payload, nonce_hash = _credential_payload(vault, item)
        if nonce_hash in nonce_hashes:
            raise RuntimeError("credential_nonce_collision")
        nonce_hashes.add(nonce_hash)
        target.execute(
            text(
                """INSERT INTO social_projection_state
                   (projection_key,payload_json,created_at,updated_at)
                   VALUES (:key,CAST(:payload AS jsonb),now(),now())"""
            ),
            {
                "key": f"v2:credential-nonce:{vault.active_key_id}:{nonce_hash}",
                "payload": json.dumps(
                    {
                        "format_version": 1,
                        "algorithm": "AES-256-GCM",
                        "claimed_at": datetime.now(UTC).isoformat(),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            },
        )
        target.execute(
            text(
                """INSERT INTO social_projection_state
                   (projection_key,payload_json,created_at,updated_at)
                   VALUES (:key,CAST(:payload AS jsonb),now(),now())"""
            ),
            {
                "key": (
                    f"v2:credential:{item.reference.platform.value}:"
                    f"{item.reference.connection_id}:{item.reference.token_kind.value}"
                ),
                "payload": json.dumps(payload, separators=(",", ":"), sort_keys=True),
            },
        )
        written += 1
    credential_count = target.execute(
        text(
            """SELECT count(*) FROM social_projection_state
               WHERE projection_key LIKE 'v2:credential:%'"""
        )
    ).scalar_one()
    nonce_count = target.execute(
        text(
            """SELECT count(*) FROM social_projection_state
               WHERE projection_key LIKE 'v2:credential-nonce:%'"""
        )
    ).scalar_one()
    if credential_count != written or nonce_count != written:
        raise RuntimeError("target_credential_projection_count_mismatch")
    return written, nonce_count


def main() -> None:
    args = _arguments()
    if args.expected_connection_count < 1 or args.expected_linked_count < 1:
        raise RuntimeError("expected_counts_must_be_positive")
    source_env = _env(args.source_env)
    target_env = _env(args.target_env)
    _validate_target_environment(target_env)
    source_url = make_url(_required(source_env, "SOCIAL_MEDIA_DATABASE_URL"))
    target_url = make_url(_required(target_env, "SOCIAL_DB_URL"))
    _validate_urls(source_url, target_url)
    try:
        source_fernet = Fernet(
            _required(source_env, "SOCIAL_TIKTOK_TOKEN_ENCRYPTION_KEY").encode("ascii")
        )
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError("legacy_tiktok_encryption_key_invalid") from exc
    vault = AesGcmTokenVault.from_json(
        active_key_id=_required(target_env, "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID"),
        keyring_json=_required(target_env, "SOCIAL_CREDENTIAL_KEYRING_JSON"),
    )
    source_engine = create_engine(source_url, pool_pre_ping=True, hide_parameters=True)
    target_engine = create_engine(target_url, pool_pre_ping=True, hide_parameters=True)
    source = source_engine.connect().execution_options(isolation_level="REPEATABLE READ")
    source_transaction = source.begin()
    try:
        source.execute(text("SET TRANSACTION READ ONLY"))
        _assert_read_only(source)
        connections, links_by_connection, unbound_links = _load_connections(
            source,
            expected_connection_count=args.expected_connection_count,
            expected_linked_count=args.expected_linked_count,
        )
        (
            credentials,
            projections,
            meta_count,
            tiktok_count,
            cross_brand_link_count,
        ) = _build_payloads(connections, links_by_connection, source_fernet=source_fernet)
        with target_engine.begin() as target:
            written, nonce_count = _write_target(
                target,
                vault=vault,
                credentials=credentials,
                connection_projections=projections,
                expected_connection_count=args.expected_connection_count,
            )
        source_transaction.rollback()
    except Exception:
        source_transaction.rollback()
        raise
    finally:
        source.close()
        source_engine.dispose()
        target_engine.dispose()
    access_count = sum(
        item.reference.token_kind is TokenKind.ACCESS for item in credentials.values()
    )
    refresh_count = sum(
        item.reference.token_kind is TokenKind.REFRESH for item in credentials.values()
    )
    print(f"legacy_connections={len(connections)}")
    print(f"meta_connection_projections={meta_count}")
    print(f"tiktok_connection_projections={tiktok_count}")
    print(f"cross_brand_link_credentials_preserved={cross_brand_link_count}")
    print(f"unbound_links_without_credential_projection={unbound_links}")
    print(f"access_credentials_reencrypted={access_count}")
    print(f"refresh_credentials_reencrypted={refresh_count}")
    print(f"credential_rows={written}")
    print(f"nonce_claims={nonce_count}")
    print("provider_and_schedule_gates=disabled")
    print("legacy_credential_migration=verified")


if __name__ == "__main__":
    main()

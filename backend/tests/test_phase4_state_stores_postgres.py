from __future__ import annotations

import base64
import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, create_engine, text

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.credentials import (
    CredentialError,
    CredentialRef,
    SecretToken,
    TokenKind,
)
from app.core.config import RuntimeMode
from app.core.write_policy import WritePolicy
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")
NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)


@pytest.fixture()
def engine() -> Iterator[Engine]:
    assert DATABASE_URL
    result = create_engine(DATABASE_URL)
    with result.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS social_projection_state"))
        connection.execute(
            text(
                """CREATE TABLE social_projection_state (
                    projection_key varchar(255) PRIMARY KEY,
                    brand_id integer NULL,
                    status varchar(32) NOT NULL DEFAULT 'pending',
                    projection_source varchar(64) NOT NULL DEFAULT 'accumulate',
                    source_updated_at timestamptz NULL,
                    projected_at timestamptz NULL,
                    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz DEFAULT now(),
                    updated_at timestamptz DEFAULT now()
                )"""
            )
        )
    yield result
    with result.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS social_projection_state"))
    result.dispose()


def policy(enabled: bool = True) -> WritePolicy:
    return WritePolicy(
        runtime_mode=RuntimeMode.DEVELOPMENT if enabled else RuntimeMode.DORMANT,
        writes_enabled=enabled,
    )


def credential_ref(
    connection_id: str = "connection-1", token_kind: TokenKind = TokenKind.ACCESS
) -> CredentialRef:
    return CredentialRef(PlatformId.TIKTOK, connection_id, token_kind)


def test_projection_credential_round_trip_is_encrypted_and_nondeterministic(
    engine: Engine,
) -> None:
    vault = AesGcmTokenVault(active_key_id="key-1", keys={"key-1": b"a" * 32})
    store = ProjectionCredentialStore(engine, policy(), vault, clock=lambda: NOW)
    reference = credential_ref()
    token = SecretToken("disposable-access-value", expires_at=NOW + timedelta(hours=1))

    store.put(reference, token)
    first = _credential_payload(engine, reference)
    assert set(first) == {
        "format_version",
        "algorithm",
        "key_id",
        "nonce",
        "ciphertext",
        "expires_at",
        "revoked",
    }
    assert first["algorithm"] == "AES-256-GCM"
    assert "disposable-access-value" not in str(first)
    assert len(base64.b64decode(first["nonce"])) == 12
    assert len(base64.b64decode(first["ciphertext"])) >= 16
    assert store.get(reference).value == "disposable-access-value"  # type: ignore[union-attr]

    store.put(reference, token)
    second = _credential_payload(engine, reference)
    assert first["nonce"] != second["nonce"]
    assert first["ciphertext"] != second["ciphertext"]
    with engine.connect() as connection:
        nonce_claims = connection.execute(
            text(
                """SELECT count(*) FROM social_projection_state
                   WHERE projection_key LIKE 'v2:credential-nonce:%'"""
            )
        ).scalar_one()
    assert nonce_claims == 2


def test_credential_aad_isolation_revoke_and_expiry(engine: Engine) -> None:
    vault = AesGcmTokenVault(active_key_id="key-1", keys={"key-1": b"a" * 32})
    store = ProjectionCredentialStore(engine, policy(), vault, clock=lambda: NOW)
    original = credential_ref("connection-1")
    moved = credential_ref("connection-2")
    store.put(original, SecretToken("disposable-value", NOW + timedelta(hours=1)))
    with engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO social_projection_state (projection_key, payload_json)
                   SELECT :new_key, payload_json FROM social_projection_state
                   WHERE projection_key=:old_key"""
            ),
            {"new_key": _credential_key(moved), "old_key": _credential_key(original)},
        )
    with pytest.raises(CredentialError, match="credential_authentication_failed"):
        store.get(moved)

    assert store.revoke(original) is True
    assert store.get(original) is None

    expired = credential_ref("expired")
    store.put(expired, SecretToken("expired-value", NOW - timedelta(seconds=1)))
    assert store.get(expired) is None


def test_duplicate_nonce_retries_then_fails_without_credential_write(engine: Engine) -> None:
    vault = AesGcmTokenVault(
        active_key_id="key-1",
        keys={"key-1": b"a" * 32},
        nonce_source=lambda size: b"x" * size,
    )
    store = ProjectionCredentialStore(
        engine,
        policy(),
        vault,
        max_nonce_attempts=2,
        clock=lambda: NOW,
    )
    store.put(credential_ref("first"), SecretToken("first-value"))
    with pytest.raises(CredentialError, match="credential_nonce_exhausted"):
        store.put(credential_ref("second"), SecretToken("second-value"))
    assert store.get(credential_ref("second")) is None
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT count(*) FROM social_projection_state")
        ).scalar_one()
    assert rows == 2


def test_key_rotation_dry_run_real_update_and_failed_update_rollback(engine: Engine) -> None:
    old_vault = AesGcmTokenVault(active_key_id="key-1", keys={"key-1": b"a" * 32})
    old_store = ProjectionCredentialStore(engine, policy(), old_vault, clock=lambda: NOW)
    reference = credential_ref("rotate")
    old_store.put(reference, SecretToken("rotation-value"))

    rotating_vault = AesGcmTokenVault(
        active_key_id="key-2",
        keys={"key-1": b"a" * 32, "key-2": b"b" * 32},
    )
    rotating_store = ProjectionCredentialStore(
        engine, policy(), rotating_vault, clock=lambda: NOW
    )
    dry_run = rotating_store.rotate(reference, dry_run=True)
    assert (dry_run.inspected, dry_run.eligible, dry_run.rotated) == (1, 1, 0)
    assert _credential_payload(engine, reference)["key_id"] == "key-1"

    rotated = rotating_store.rotate(reference, dry_run=False)
    assert (rotated.inspected, rotated.eligible, rotated.rotated) == (1, 1, 1)
    assert _credential_payload(engine, reference)["key_id"] == "key-2"
    retired_store = ProjectionCredentialStore(
        engine,
        policy(),
        AesGcmTokenVault(active_key_id="key-2", keys={"key-2": b"b" * 32}),
        clock=lambda: NOW,
    )
    assert retired_store.get(reference).value == "rotation-value"  # type: ignore[union-attr]

    rollback_ref = credential_ref("rollback")
    old_store.put(rollback_ref, SecretToken("rollback-value"))
    fixed_vault = AesGcmTokenVault(
        active_key_id="key-2",
        keys={"key-1": b"a" * 32, "key-2": b"b" * 32},
        nonce_source=lambda size: b"z" * size,
    )
    fixed_store = ProjectionCredentialStore(
        engine,
        policy(),
        fixed_vault,
        max_nonce_attempts=2,
        clock=lambda: NOW,
    )
    fixed_store.put(credential_ref("nonce-owner"), SecretToken("owner-value"))
    with pytest.raises(CredentialError, match="credential_nonce_exhausted"):
        fixed_store.rotate(rollback_ref, dry_run=False)
    assert _credential_payload(engine, rollback_ref)["key_id"] == "key-1"
    assert old_store.get(rollback_ref).value == "rollback-value"  # type: ignore[union-attr]


def test_checkpoint_versioning_atomic_claim_and_query_side_effects(engine: Engine) -> None:
    store = ProjectionCheckpointStore(engine, policy(), clock=lambda: NOW)
    key = CheckpointKey(PlatformId.INSTAGRAM, CapabilityId.CONTENT, "account-1")
    first = ProviderCheckpoint(
        key=key,
        version=1,
        cursor="cursor-1",
        watermark="post-1",
        observed_through=NOW,
    )
    assert store.put(first, expected_version=None) is True
    assert store.put(first, expected_version=None) is False

    second = ProviderCheckpoint(
        key=key,
        version=2,
        cursor="cursor-2",
        watermark="post-2",
        observed_through=NOW + timedelta(minutes=1),
    )
    with pytest.raises(ValueError, match="checkpoint_version_transition_invalid"):
        store.put(second, expected_version=9)
    stale = ProviderCheckpoint(
        key=key,
        version=10,
        cursor="stale-cursor",
        watermark="stale-watermark",
        observed_through=NOW,
    )
    assert store.put(stale, expected_version=9) is False
    assert store.put(second, expected_version=1) is True
    before = _projection_count(engine)
    assert store.get(key) == second
    assert _projection_count(engine) == before

    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda _: store.claim_once(key, "run-1", expires_at),
                range(4),
            )
        )
    assert results.count(True) == 1
    assert results.count(False) == 3

    with engine.begin() as connection:
        connection.execute(
            text(
                """UPDATE social_projection_state
                       SET payload_json=jsonb_set(
                           payload_json,
                           '{expires_at}',
                           to_jsonb(CAST(:expired_at AS text))
                       )
                   WHERE projection_key LIKE 'v2:checkpoint-once:%'"""
            ),
            {"expired_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()},
        )
    assert store.claim_once(key, "run-1", expires_at) is True


def test_dormant_policy_blocks_checkpoint_and_credential_mutations(engine: Engine) -> None:
    blocked = policy(False)
    reference = credential_ref()
    credential_store = ProjectionCredentialStore(
        engine,
        blocked,
        AesGcmTokenVault(active_key_id="key-1", keys={"key-1": b"a" * 32}),
    )
    with pytest.raises(PermissionError, match="Mutation is disabled"):
        credential_store.put(reference, SecretToken("blocked-value"))

    checkpoint_store = ProjectionCheckpointStore(engine, blocked)
    checkpoint = ProviderCheckpoint(
        key=CheckpointKey(PlatformId.FACEBOOK, CapabilityId.PROFILE, "account-1"),
        version=1,
        cursor=None,
        watermark=None,
        observed_through=None,
    )
    with pytest.raises(PermissionError, match="Mutation is disabled"):
        checkpoint_store.put(checkpoint, expected_version=None)
    assert _projection_count(engine) == 0


def _credential_key(reference: CredentialRef) -> str:
    return (
        f"v2:credential:{reference.platform.value}:"
        f"{reference.connection_id}:{reference.token_kind.value}"
    )


def _credential_payload(engine: Engine, reference: CredentialRef) -> dict[str, object]:
    with engine.connect() as connection:
        return dict(
            connection.execute(
                text(
                    """SELECT payload_json FROM social_projection_state
                       WHERE projection_key=:key"""
                ),
                {"key": _credential_key(reference)},
            ).scalar_one()
        )


def _projection_count(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(text("SELECT count(*) FROM social_projection_state")).scalar_one()
        )

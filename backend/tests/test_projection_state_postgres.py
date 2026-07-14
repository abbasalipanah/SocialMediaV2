from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.infrastructure.persistence.projection_state import ProjectionStateStore

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")


@pytest.fixture()
def store() -> ProjectionStateStore:
    assert DATABASE_URL
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS social_projection_state"))
        connection.execute(text("DROP TABLE IF EXISTS brands"))
        connection.execute(text("CREATE TABLE brands (id integer PRIMARY KEY)"))
        connection.execute(
            text(
                """CREATE TABLE social_projection_state (
                    projection_key varchar(255) PRIMARY KEY,
                    brand_id integer NULL REFERENCES brands(id),
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
    return ProjectionStateStore(DATABASE_URL)


def test_session_jti_claim_is_atomic_and_session_is_revocable(store: ProjectionStateStore) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    payload = {"user_id": "u1", "brand_id": "b1", "revoked": False}
    assert store.create_from_jti(
        jti_hash="j1", session_hash="s1", payload=payload, expires_at=expires_at
    )
    assert not store.create_from_jti(
        jti_hash="j1", session_hash="s2", payload=payload, expires_at=expires_at
    )
    assert store.get_session("s1")["user_id"] == "u1"
    assert store.revoke_authority_sessions(user_id="u1", brand_id=None) == 1
    assert store.get_session("s1")["revoked"] is True


def test_session_expiry_uses_schema_compatible_payload_json(store: ProjectionStateStore) -> None:
    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    assert store.create_from_jti(
        jti_hash="expired-jti",
        session_hash="expired-session",
        payload={"user_id": "u1", "brand_id": "b1", "revoked": False},
        expires_at=expired_at,
    )
    assert store.get_session("expired-session") is None

    with store.engine.connect() as connection:
        columns = set(
            connection.execute(
                text(
                    """SELECT column_name FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='social_projection_state'"""
                )
            ).scalars()
        )
        stored_expiry = connection.execute(
            text(
                """SELECT payload_json->>'expires_at' FROM social_projection_state
                WHERE projection_key='v2:session:expired-session'"""
            )
        ).scalar_one()

    assert "payload_json" in columns
    assert "payload" not in columns
    assert "expires_at" not in columns
    assert stored_expiry == expired_at.isoformat()


def test_event_nonce_duplicate_and_version_ordering_are_atomic(store: ProjectionStateStore) -> None:
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    arguments = {
        "nonce_hash": "n1",
        "nonce_expires_at": expires_at,
        "event_id": "e1",
        "event_type": "brand.upserted",
        "entity_key": "v2:brand:b1",
        "version": 2,
        "payload": {"entity_id": "b1", "version": 2},
    }
    assert store.apply_event(**arguments) == "applied"
    assert store.apply_event(**{**arguments, "event_id": "e2"}) == "nonce_replayed"
    assert (
        store.apply_event(**{**arguments, "nonce_hash": "n2", "event_id": "e1"})
        == "duplicate_ignored"
    )
    assert (
        store.apply_event(
            **{
                **arguments,
                "nonce_hash": "n3",
                "event_id": "e3",
                "version": 1,
                "payload": {"entity_id": "b1", "version": 1},
            }
        )
        == "stale_ignored"
    )
    assert store.get_projection("v2:brand:b1")["version"] == 2

    expired_nonce = {
        **arguments,
        "nonce_hash": "n4",
        "nonce_expires_at": datetime.now(UTC) - timedelta(seconds=1),
        "event_id": "e4",
        "version": 3,
        "payload": {"entity_id": "b1", "version": 3},
    }
    assert store.apply_event(**expired_nonce) == "applied"
    assert (
        store.apply_event(
            **{
                **expired_nonce,
                "nonce_expires_at": expires_at,
                "event_id": "e5",
                "version": 4,
                "payload": {"entity_id": "b1", "version": 4},
            }
        )
        == "applied"
    )

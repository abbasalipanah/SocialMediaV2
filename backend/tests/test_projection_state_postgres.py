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
        connection.execute(
            text(
                """CREATE TABLE IF NOT EXISTS social_projection_state (
                    projection_key text PRIMARY KEY,
                    payload jsonb NOT NULL,
                    expires_at timestamptz NULL,
                    updated_at timestamptz NOT NULL DEFAULT now()
                )"""
            )
        )
        connection.execute(text("TRUNCATE social_projection_state"))
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

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
        connection.execute(text("DROP TABLE IF EXISTS tenants"))
        connection.execute(text("CREATE TABLE tenants (id bigint PRIMARY KEY)"))
        connection.execute(text("INSERT INTO tenants VALUES (1)"))
        connection.execute(
            text(
                """CREATE TABLE brands (
                    id bigint PRIMARY KEY,
                    tenant_id bigint NOT NULL REFERENCES tenants(id),
                    name varchar(255),
                    parent_brand_id bigint REFERENCES brands(id),
                    active boolean NOT NULL DEFAULT true,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE social_projection_state (
                    projection_key varchar(255) PRIMARY KEY,
                    payload_json jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now()
                )"""
            )
        )
    return ProjectionStateStore(DATABASE_URL)


def test_session_jti_claim_is_atomic_and_session_is_revocable(
    store: ProjectionStateStore,
) -> None:
    expires_at = datetime.now(UTC) + timedelta(hours=1)
    payload = {
        "user_id": "u1",
        "brand_id": "1",
        "brand_scope": {
            "version": "v1",
            "default_brand_id": "1",
            "brands": [
                {
                    "brand_id": "1",
                    "name": None,
                    "parent_brand_id": None,
                    "visibility": "active",
                    "access_mode": "write",
                    "role": "agency_admin",
                }
            ],
        },
        "revoked": False,
    }
    assert store.create_from_jti(
        jti_hash="j1", session_hash="s1", payload=payload, expires_at=expires_at
    )
    assert not store.create_from_jti(
        jti_hash="j1", session_hash="s2", payload=payload, expires_at=expires_at
    )
    assert store.get_session("s1")["user_id"] == "u1"
    store.revoke_session("s1")
    assert store.get_session("s1")["revoked"] is True


def test_session_expiry_uses_v2_owned_payload_json(store: ProjectionStateStore) -> None:
    expired_at = datetime.now(UTC) - timedelta(seconds=1)
    assert store.create_from_jti(
        jti_hash="expired-jti",
        session_hash="expired-session",
        payload={"user_id": "u1", "brand_id": "b1", "revoked": False},
        expires_at=expired_at,
    )
    assert store.get_session("expired-session") is None

    with store.engine.connect() as connection:
        stored_expiry = connection.execute(
            text(
                """SELECT payload_json->>'expires_at' FROM social_projection_state
                WHERE projection_key='v2:session:expired-session'"""
            )
        ).scalar_one()

    assert stored_expiry == expired_at.isoformat()

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text

from app.application.services.provisioning import SignedRequest, apply_signed_event, sign_request
from app.infrastructure.persistence.projection_state import ProjectionStateStore

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")
PROVISIONING_SECRET = "phase3-local-provisioning-secret"
PROVISIONING_PATH = "/internal/provisioning/events"


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


def _apply_snapshot(
    store: ProjectionStateStore,
    *,
    event_id: str,
    nonce: str,
    version: int,
    brand_ids: tuple[str, ...],
) -> str:
    body = json.dumps(
        {
            "event_id": event_id,
            "event_type": "brand_access.sync",
            "entity_id": "user-1",
            "version": version,
            "payload": {
                "user": {"id": "user-1", "role": "viewer", "access_mode": "read"},
                "brands": [
                    {
                        "id": brand_id,
                        "name": f"Brand {brand_id}",
                        "parent_brand_id": "parent-1",
                        "status": "active",
                    }
                    for brand_id in brand_ids
                ],
                "default_brand_id": brand_ids[0] if brand_ids else None,
            },
        },
        separators=(",", ":"),
    ).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    return apply_signed_event(
        secret=PROVISIONING_SECRET,
        method="POST",
        path=PROVISIONING_PATH,
        body=body,
        signed=SignedRequest(
            timestamp=timestamp,
            nonce=nonce,
            signature=sign_request(
                PROVISIONING_SECRET,
                "POST",
                PROVISIONING_PATH,
                timestamp,
                nonce,
                body,
            ),
        ),
        store=store,
    )


def test_full_snapshot_atomically_replaces_brand_access_rows(store: ProjectionStateStore) -> None:
    assert (
        store.apply_event(
            nonce_hash="parent-shell-nonce",
            nonce_expires_at=datetime.now(UTC) + timedelta(minutes=10),
            event_id="parent-shell-event",
            event_type="brand.upserted",
            entity_key="v2:brand-shell:parent-1",
            version=0,
            payload={
                "active": True,
                "brand_id": "parent-1",
                "name": "Existing Parent",
                "parent_brand_id": None,
                "placeholder": False,
                "version": 0,
            },
        )
        == "applied"
    )
    assert _apply_snapshot(
        store,
        event_id="snapshot-1",
        nonce="snapshot-nonce-1",
        version=1,
        brand_ids=("child-a", "child-b"),
    ) == "applied"
    assert {
        row["brand_id"]
        for row in store.list_projections("v2:brand-access:user-1:")
        if row["active"]
    } == {"child-a", "child-b"}
    parent_shell = store.get_projection("v2:brand-shell:parent-1")
    assert parent_shell["placeholder"] is False
    assert parent_shell["name"] == "Existing Parent"

    assert _apply_snapshot(
        store,
        event_id="snapshot-2",
        nonce="snapshot-nonce-2",
        version=2,
        brand_ids=("child-b",),
    ) == "applied"
    removed = store.get_projection("v2:brand-access:user-1:child-a")
    retained = store.get_projection("v2:brand-access:user-1:child-b")
    assert removed["active"] is False
    assert removed["snapshot_removed"] is True
    assert retained["active"] is True
    assert retained["version"] == 2

    assert _apply_snapshot(
        store,
        event_id="snapshot-stale",
        nonce="snapshot-nonce-3",
        version=1,
        brand_ids=("child-a",),
    ) == "stale_ignored"
    assert store.get_projection("v2:brand-access:user-1:child-a")["active"] is False

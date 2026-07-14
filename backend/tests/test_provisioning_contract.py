from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import pytest

from app.application.services.provisioning import (
    ProvisioningError,
    SignedRequest,
    apply_signed_event,
    sign_request,
)

SECRET = "local-provisioning-secret-with-sufficient-entropy"
PATH = "/internal/provisioning/events"


class MemoryProvisioningStore:
    def __init__(self) -> None:
        self.nonces: set[str] = set()
        self.events: set[str] = set()
        self.projections: dict[str, dict[str, Any]] = {}
        self.revoked_users: list[str] = []
        self.revoked_brands: list[str] = []

    def apply_event(
        self,
        *,
        nonce_hash: str,
        nonce_expires_at: datetime,
        event_id: str,
        event_type: str,
        entity_key: str,
        version: int,
        payload: Mapping[str, Any],
    ) -> str:
        del nonce_expires_at, event_type
        if nonce_hash in self.nonces:
            return "nonce_replayed"
        self.nonces.add(nonce_hash)
        if event_id in self.events:
            return "duplicate_ignored"
        self.events.add(event_id)
        current = self.projections.get(entity_key)
        if current and current["version"] >= version:
            return "stale_ignored"
        self.projections[entity_key] = dict(payload)
        return "applied"

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None:
        return self.projections.get(entity_key)

    def revoke_authority_sessions(self, *, user_id: str | None, brand_id: str | None) -> int:
        if user_id:
            self.revoked_users.append(user_id)
        if brand_id:
            self.revoked_brands.append(brand_id)
        return 1


def body(event_id: str = "event-1", version: int = 1) -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": "brand.upserted",
            "entity_id": "brand-1",
            "version": version,
            "payload": {"name": "Example Brand", "status": "active"},
        },
        separators=(",", ":"),
    ).encode()


def signed(payload: bytes, nonce: str) -> SignedRequest:
    timestamp = str(int(datetime.now(UTC).timestamp()))
    return SignedRequest(
        timestamp=timestamp,
        nonce=nonce,
        signature=sign_request(SECRET, "POST", PATH, timestamp, nonce, payload),
    )


def test_valid_event_applies_and_replays_are_idempotent() -> None:
    store = MemoryProvisioningStore()
    payload = body()
    assert (
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=payload,
            signed=signed(payload, "n-1"),
            store=store,
        )
        == "applied"
    )
    assert (
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=payload,
            signed=signed(payload, "n-2"),
            store=store,
        )
        == "duplicate_ignored"
    )


def test_nonce_replay_and_stale_version_are_rejected() -> None:
    store = MemoryProvisioningStore()
    first = body("event-1", 2)
    request = signed(first, "same-nonce")
    assert (
        apply_signed_event(
            secret=SECRET, method="POST", path=PATH, body=first, signed=request, store=store
        )
        == "applied"
    )
    with pytest.raises(ProvisioningError, match="nonce_replayed"):
        apply_signed_event(
            secret=SECRET, method="POST", path=PATH, body=first, signed=request, store=store
        )
    stale = body("event-3", 1)
    assert (
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=stale,
            signed=signed(stale, "n-3"),
            store=store,
        )
        == "stale_ignored"
    )


def test_signature_is_checked_before_json_parse() -> None:
    with pytest.raises(ProvisioningError, match="invalid_signature"):
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=b"not-json",
            signed=SignedRequest(
                timestamp=str(int(datetime.now(UTC).timestamp())),
                nonce="n",
                signature="0" * 64,
            ),
            store=MemoryProvisioningStore(),
        )


def test_authority_deletion_revokes_related_sessions() -> None:
    store = MemoryProvisioningStore()
    payload = json.dumps(
        {
            "event_id": "delete-1",
            "event_type": "user.deleted",
            "entity_id": "user-1",
            "version": 1,
            "payload": {},
        },
        separators=(",", ":"),
    ).encode()
    assert (
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=payload,
            signed=signed(payload, "delete-nonce"),
            store=store,
            session_store=store,
        )
        == "applied"
    )
    assert store.revoked_users == ["user-1"]


def test_nested_entitlement_status_is_normalized_and_revokes_brand_sessions() -> None:
    store = MemoryProvisioningStore()
    payload = json.dumps(
        {
            "event_id": "entitlement-1",
            "event_type": "entitlement.updated",
            "entity_id": "brand-1",
            "version": 4,
            "payload": {"after": {"status": "disabled"}},
        },
        separators=(",", ":"),
    ).encode()
    assert (
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=payload,
            signed=signed(payload, "entitlement-nonce"),
            store=store,
            session_store=store,
        )
        == "applied"
    )
    assert store.revoked_brands == ["brand-1"]
    assert store.projections["v2:entitlement:brand-1"]["active"] is False


def test_membership_role_and_empty_full_snapshot_are_fail_closed_and_revoking() -> None:
    store = MemoryProvisioningStore()
    invalid_membership = json.dumps(
        {
            "event_id": "membership-1",
            "event_type": "membership.upserted",
            "entity_id": "membership-1",
            "version": 1,
            "payload": {
                "user_id": "user-1",
                "brand_id": "brand-1",
                "role": "owner",
                "is_active": True,
            },
        },
        separators=(",", ":"),
    ).encode()
    with pytest.raises(ProvisioningError, match="invalid_membership_role"):
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=invalid_membership,
            signed=signed(invalid_membership, "membership-nonce"),
            store=store,
        )

    snapshot = json.dumps(
        {
            "event_id": "snapshot-1",
            "event_type": "brand_access.sync",
            "entity_id": "user-1",
            "version": 1,
            "payload": {
                "user": {"id": "user-1", "role": "viewer"},
                "brands": [],
                "default_brand_id": None,
            },
        },
        separators=(",", ":"),
    ).encode()
    assert (
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=snapshot,
            signed=signed(snapshot, "snapshot-nonce"),
            store=store,
            session_store=store,
        )
        == "applied"
    )
    assert store.revoked_users == ["user-1"]


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("event_id", "e" * 247),
        ("entity_id", "b" * 236),
    ),
)
def test_projection_keys_must_fit_the_existing_schema(field: str, value: str) -> None:
    store = MemoryProvisioningStore()
    event = {
        "event_id": "event-1",
        "event_type": "brand.app_access.changed",
        "entity_id": "brand-1",
        "version": 1,
        "payload": {"status": "enabled"},
    }
    event[field] = value
    payload = json.dumps(event, separators=(",", ":")).encode()

    with pytest.raises(ProvisioningError, match="invalid_event"):
        apply_signed_event(
            secret=SECRET,
            method="POST",
            path=PATH,
            body=payload,
            signed=signed(payload, f"long-{field}"),
            store=store,
        )

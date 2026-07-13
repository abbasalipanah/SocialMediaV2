"""HMAC verification and replay-safe provisioning event application."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.application.ports import ProvisioningStore, SessionStore
from app.core.security import sha256_text

SUPPORTED_EVENTS = {
    "brand.upserted",
    "brand.deleted",
    "entitlement.updated",
    "brand.app_access.changed",
    "membership.upserted",
    "brand_access.sync",
    "user.deleted",
}
CANONICAL_ROLES = {"super_admin", "agency_admin", "agency_operator", "viewer"}
ENTITY_KINDS = {
    "brand.upserted": "brand",
    "brand.deleted": "brand",
    "entitlement.updated": "entitlement",
    "brand.app_access.changed": "brand-app-access",
    "membership.upserted": "membership",
    "brand_access.sync": "brand-access",
    "user.deleted": "user",
}


class ProvisioningError(ValueError):
    pass


@dataclass(frozen=True)
class SignedRequest:
    timestamp: str
    nonce: str
    signature: str


def sign_request(
    secret: str, method: str, path: str, timestamp: str, nonce: str, body: bytes
) -> str:
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = "\n".join((method.upper(), path, timestamp, nonce, body_hash)).encode()
    return hmac.new(secret.encode(), canonical, hashlib.sha256).hexdigest()


def verify_signature(
    *,
    secret: str,
    method: str,
    path: str,
    body: bytes,
    signed: SignedRequest,
    now: datetime | None = None,
) -> None:
    if not secret:
        raise ProvisioningError("provisioning_not_configured")
    if not signed.nonce or len(signed.nonce) > 256:
        raise ProvisioningError("invalid_nonce")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", signed.signature):
        raise ProvisioningError("invalid_signature")
    current = now or datetime.now(UTC)
    try:
        sent_at = datetime.fromtimestamp(int(signed.timestamp), UTC)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProvisioningError("invalid_timestamp") from exc
    if abs((current - sent_at).total_seconds()) > 300:
        raise ProvisioningError("timestamp_out_of_window")
    expected = sign_request(secret, method, path, signed.timestamp, signed.nonce, body)
    if not hmac.compare_digest(expected, signed.signature.lower()):
        raise ProvisioningError("invalid_signature")


def _mapping(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProvisioningError(f"invalid_{field}")
    return dict(value)


def _first(payload: Mapping[str, Any], field: str, containers: tuple[str, ...]) -> object:
    if field in payload:
        return payload[field]
    for container in containers:
        nested = payload.get(container)
        if isinstance(nested, dict) and field in nested:
            return nested[field]
    return None


def _active_from_status(value: object, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        raise ProvisioningError(f"invalid_{field}")
    normalized = value.strip().lower()
    if normalized in {"active", "enabled", "trial"}:
        return True
    if normalized in {"inactive", "disabled", "locked", "suspended", "archived", "deleted"}:
        return False
    raise ProvisioningError(f"invalid_{field}")


def _normalize_event(event_type: str, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    projection = dict(payload)
    if event_type == "brand.upserted":
        status = _first(payload, "status", ("after", "brand"))
        if status is None:
            status = payload.get("brand_status")
        projection["active"] = _active_from_status(
            status, "brand_status"
        )
    elif event_type in {"brand.deleted", "user.deleted"}:
        projection["active"] = False
    elif event_type == "entitlement.updated":
        projection["active"] = _active_from_status(
            _first(payload, "status", ("after", "entitlement")), "entitlement_status"
        )
    elif event_type == "brand.app_access.changed":
        active = _first(payload, "active", ("after", "app_access"))
        if active is None:
            active = _first(payload, "projection_status", ("after", "app_access"))
        if active is None:
            active = _first(payload, "status", ("after", "app_access"))
        projection["active"] = _active_from_status(active, "app_access_status")
    elif event_type == "membership.upserted":
        role = _first(payload, "role", ("after", "membership"))
        if role not in CANONICAL_ROLES:
            raise ProvisioningError("invalid_membership_role")
        user_id = str(_first(payload, "user_id", ("after", "membership")) or "").strip()
        brand_id = str(_first(payload, "brand_id", ("after", "membership")) or "").strip()
        if not user_id or not brand_id:
            raise ProvisioningError("invalid_membership_authority")
        active = _first(payload, "is_active", ("after", "membership"))
        if active is None:
            active = _first(payload, "status", ("after", "membership"))
        projection.update(
            {
                "active": _active_from_status(active, "membership_status"),
                "role": role,
                "user_id": user_id,
                "brand_id": brand_id,
            }
        )
    elif event_type == "brand_access.sync":
        user = _mapping(payload.get("user"), "snapshot_user")
        brands = payload.get("brands")
        if not isinstance(brands, list) or not all(isinstance(item, dict) for item in brands):
            raise ProvisioningError("invalid_snapshot_brands")
        user_id = str(user.get("id", "")).strip()
        if not user_id or user_id != entity_id or user.get("role") not in CANONICAL_ROLES:
            raise ProvisioningError("invalid_snapshot_user")
        for brand in brands:
            role = brand.get("role")
            if not str(brand.get("id", "")).strip() or (
                role is not None and role not in CANONICAL_ROLES
            ):
                raise ProvisioningError("invalid_snapshot_brand")
        projection.update({"active": bool(brands), "brands": brands, "user": user})
    return projection


def apply_signed_event(
    *,
    secret: str,
    method: str,
    path: str,
    body: bytes,
    signed: SignedRequest,
    store: ProvisioningStore,
    session_store: SessionStore | None = None,
) -> str:
    verify_signature(secret=secret, method=method, path=path, body=body, signed=signed)
    try:
        event = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProvisioningError("invalid_json") from exc
    if not isinstance(event, dict):
        raise ProvisioningError("invalid_event")
    event_type = str(event.get("event_type", ""))
    if event_type not in SUPPORTED_EVENTS:
        raise ProvisioningError("unsupported_event")
    if event.get("app_id") not in {None, "social_media"}:
        raise ProvisioningError("wrong_app")
    event_id = str(event.get("event_id", "")).strip()
    entity_id = str(event.get("entity_id", "")).strip()
    version = event.get("version")
    if (
        not event_id
        or len(event_id) > 256
        or not entity_id
        or len(entity_id) > 256
        or not isinstance(version, int)
        or isinstance(version, bool)
        or version < 0
    ):
        raise ProvisioningError("invalid_event")
    projection = _normalize_event(event_type, entity_id, _mapping(event.get("payload"), "payload"))
    projection.update({"event_type": event_type, "version": version, "entity_id": entity_id})
    status = store.apply_event(
        nonce_hash=sha256_text(signed.nonce),
        nonce_expires_at=datetime.now(UTC) + timedelta(minutes=10),
        event_id=event_id,
        event_type=event_type,
        entity_key=f"v2:{ENTITY_KINDS[event_type]}:{entity_id}",
        version=version,
        payload=projection,
    )
    if status == "nonce_replayed":
        raise ProvisioningError("nonce_replayed")
    if status == "applied" and session_store is not None:
        if event_type == "user.deleted" or (
            event_type == "brand_access.sync" and projection["active"] is False
        ):
            session_store.revoke_authority_sessions(user_id=entity_id, brand_id=None)
        elif event_type == "brand.deleted" or (
            event_type in {"entitlement.updated", "brand.app_access.changed"}
            and projection["active"] is False
        ):
            session_store.revoke_authority_sessions(user_id=None, brand_id=entity_id)
        elif event_type == "membership.upserted" and projection["active"] is False:
            session_store.revoke_authority_sessions(
                user_id=str(projection["user_id"]), brand_id=str(projection["brand_id"])
            )
    return status

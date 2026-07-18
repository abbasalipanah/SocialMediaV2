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

from app.application.ports import (
    ProjectionReplacement,
    ProjectionWrite,
    ProvisioningStore,
    SessionStore,
)
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
    "brand.upserted": "brand-shell",
    "brand.deleted": "brand-shell",
    "entitlement.updated": "brand-entitlement",
    "brand.app_access.changed": "brand-app-access",
    "membership.upserted": "membership",
    "brand_access.sync": "brand-access-snapshot",
    "user.deleted": "user",
}
PROJECTION_KEY_MAX_LENGTH = 255


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


def _identifier(value: object, field: str) -> str:
    identifier = str(value or "").strip()
    if not identifier or len(identifier) > 256:
        raise ProvisioningError(f"invalid_{field}")
    return identifier


def _optional_identifier(value: object, field: str) -> str | None:
    if value is None:
        return None
    return _identifier(value, field)


def _access_mode_for_role(role: str) -> str:
    return "write" if role in {"super_admin", "agency_admin", "agency_operator"} else "read"


def _normalize_event(event_type: str, entity_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    projection = dict(payload)
    if event_type == "brand.upserted":
        status = _first(payload, "status", ("after", "brand"))
        if status is None:
            status = payload.get("brand_status")
        payload_brand_id = _first(payload, "brand_id", ("after", "brand"))
        if payload_brand_id is not None and _identifier(payload_brand_id, "brand_id") != entity_id:
            raise ProvisioningError("brand_id_mismatch")
        name = _first(payload, "name", ("after", "brand"))
        if name is None:
            name = payload.get("brand_name")
        parent_brand_id = _first(payload, "parent_brand_id", ("after", "brand"))
        parent_brand_id = _optional_identifier(parent_brand_id, "parent_brand_id")
        if parent_brand_id == entity_id:
            raise ProvisioningError("invalid_parent_brand_id")
        projection.update(
            {
                "active": _active_from_status(status, "brand_status"),
                "brand_id": entity_id,
                "name": str(name).strip() if name is not None else None,
                "parent_brand_id": parent_brand_id,
                "placeholder": False,
            }
        )
    elif event_type == "brand.deleted":
        projection.update({"active": False, "brand_id": entity_id})
    elif event_type == "user.deleted":
        projection["active"] = False
    elif event_type == "entitlement.updated":
        projection.update(
            {
                "active": _active_from_status(
                    _first(payload, "status", ("after", "entitlement")),
                    "entitlement_status",
                ),
                "brand_id": entity_id,
            }
        )
    elif event_type == "brand.app_access.changed":
        active = _first(payload, "active", ("after", "app_access"))
        if active is None:
            active = _first(payload, "projection_status", ("after", "app_access"))
        if active is None:
            active = _first(payload, "status", ("after", "app_access"))
        projection.update(
            {"active": _active_from_status(active, "app_access_status"), "brand_id": entity_id}
        )
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
                "access_mode": _access_mode_for_role(str(role)),
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
        user_role = str(user["role"])
        expected_user_access_mode = _access_mode_for_role(user_role)
        if user.get("access_mode") not in {None, expected_user_access_mode}:
            raise ProvisioningError("invalid_snapshot_user")
        normalized_brands: list[dict[str, Any]] = []
        brand_ids: set[str] = set()
        for brand in brands:
            brand_id = _identifier(brand.get("id"), "snapshot_brand")
            if brand_id in brand_ids:
                raise ProvisioningError("duplicate_snapshot_brand")
            brand_ids.add(brand_id)
            role = brand.get("role", user_role)
            if role not in CANONICAL_ROLES:
                raise ProvisioningError("invalid_snapshot_brand")
            parent_brand_id = _optional_identifier(
                brand.get("parent_brand_id"), "snapshot_parent_brand"
            )
            if parent_brand_id == brand_id:
                raise ProvisioningError("invalid_snapshot_brand")
            status = brand.get("status")
            active = (
                True
                if status is None
                else _active_from_status(status, "snapshot_brand_status")
            )
            normalized_brands.append(
                {
                    "access_mode": _access_mode_for_role(str(role)),
                    "active": active,
                    "brand_id": brand_id,
                    "name": str(brand.get("name") or "").strip() or None,
                    "parent_brand_id": parent_brand_id,
                    "role": role,
                    "slug": str(brand.get("slug") or "").strip() or None,
                }
            )
        default_brand_id = _optional_identifier(
            payload.get("default_brand_id"), "default_brand_id"
        )
        if default_brand_id is not None and default_brand_id not in brand_ids:
            raise ProvisioningError("invalid_default_brand_id")
        projection.update(
            {
                "active": any(brand["active"] for brand in normalized_brands),
                "brands": normalized_brands,
                "default_brand_id": default_brand_id,
                "user": {
                    **user,
                    "id": user_id,
                    "access_mode": expected_user_access_mode,
                    "role": user_role,
                },
            }
        )
    return projection


def _projection_changes(
    event_type: str, entity_id: str, projection: Mapping[str, Any], version: int
) -> tuple[tuple[ProjectionWrite, ...], ProjectionReplacement | None]:
    event_payload = {"event_type": event_type, "version": version}
    if event_type == "membership.upserted":
        user_id = str(projection["user_id"])
        brand_id = str(projection["brand_id"])
        write = ProjectionWrite(
            projection_key=f"v2:brand-access:{user_id}:{brand_id}",
            payload={
                **event_payload,
                "access_mode": projection["access_mode"],
                "active": projection["active"],
                "authority_source": "membership",
                "brand_id": brand_id,
                "role": projection["role"],
                "user_id": user_id,
            },
        )
        return (write,), None
    if event_type == "brand_access.sync":
        access_writes: list[ProjectionWrite] = []
        shell_writes: dict[str, ProjectionWrite] = {}
        for brand in projection["brands"]:
            brand_id = str(brand["brand_id"])
            parent_brand_id = brand["parent_brand_id"]
            access_writes.append(
                ProjectionWrite(
                    projection_key=f"v2:brand-access:{entity_id}:{brand_id}",
                    payload={
                        **event_payload,
                        "access_mode": brand["access_mode"],
                        "active": brand["active"],
                        "authority_source": "full_snapshot",
                        "brand_id": brand_id,
                        "role": brand["role"],
                        "user_id": entity_id,
                    },
                )
            )
            shell_writes[brand_id] = ProjectionWrite(
                projection_key=f"v2:brand-shell:{brand_id}",
                payload={
                    **event_payload,
                    "active": brand["active"],
                    "brand_id": brand_id,
                    "name": brand["name"],
                    "parent_brand_id": parent_brand_id,
                    "placeholder": False,
                    "slug": brand["slug"],
                },
            )
            if parent_brand_id is not None and parent_brand_id not in shell_writes:
                shell_writes[parent_brand_id] = ProjectionWrite(
                    projection_key=f"v2:brand-shell:{parent_brand_id}",
                    payload={
                        **event_payload,
                        "active": True,
                        "brand_id": parent_brand_id,
                        "name": None,
                        "parent_brand_id": None,
                        "placeholder": True,
                        "slug": None,
                    },
                    insert_only=True,
                )
        replacement = ProjectionReplacement(
            projection_key_prefix=f"v2:brand-access:{entity_id}:",
            writes=tuple(access_writes),
            version=version,
            event_type=event_type,
        )
        return tuple(shell_writes.values()), replacement
    if event_type == "user.deleted":
        return (), ProjectionReplacement(
            projection_key_prefix=f"v2:brand-access:{entity_id}:",
            writes=(),
            version=version,
            event_type=event_type,
        )
    return (), None


def _validate_projection_keys(
    entity_key: str,
    projection_writes: tuple[ProjectionWrite, ...],
    replacement: ProjectionReplacement | None,
) -> None:
    keys = [entity_key, *(write.projection_key for write in projection_writes)]
    if replacement is not None:
        keys.extend(write.projection_key for write in replacement.writes)
        keys.append(replacement.projection_key_prefix)
    if any(len(key) > PROJECTION_KEY_MAX_LENGTH for key in keys):
        raise ProvisioningError("invalid_event")


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
    event_key = f"v2:event:{event_id}"
    entity_key = f"v2:{ENTITY_KINDS[event_type]}:{entity_id}"
    if len(event_key) > PROJECTION_KEY_MAX_LENGTH or len(entity_key) > PROJECTION_KEY_MAX_LENGTH:
        raise ProvisioningError("invalid_event")
    projection = _normalize_event(event_type, entity_id, _mapping(event.get("payload"), "payload"))
    projection.update({"event_type": event_type, "version": version, "entity_id": entity_id})
    projection_writes, replacement = _projection_changes(
        event_type, entity_id, projection, version
    )
    _validate_projection_keys(entity_key, projection_writes, replacement)
    status = store.apply_event(
        nonce_hash=sha256_text(signed.nonce),
        nonce_expires_at=datetime.now(UTC) + timedelta(minutes=10),
        event_id=event_id,
        event_type=event_type,
        entity_key=entity_key,
        version=version,
        payload=projection,
        projection_writes=projection_writes,
        replacement=replacement,
    )
    if status == "nonce_replayed":
        raise ProvisioningError("nonce_replayed")
    if status == "applied" and session_store is not None:
        if event_type in {"user.deleted", "brand_access.sync"}:
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

"""Accumulate SSO v1 verification and hash-only local session creation."""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.application.ports import SessionStore
from app.core.security import sha256_text

CANONICAL_ROLES = {"super_admin", "agency_admin", "agency_operator", "viewer"}
WRITE_ROLES = {"super_admin", "agency_admin", "agency_operator"}
SETTINGS_ROLES = {"super_admin", "agency_admin"}
PLATFORM_CONNECTION_APP_ROLES = {"admin", "operator"}
PLATFORM_CONNECTION_MANAGE_PERMISSION = "social.connection.manage"
TIKTOK_CONNECTION_MANAGE_PERMISSION = "tiktok.connection.manage"
BRAND_STATUSES = {"active", "suspended", "archived"}
LAUNCH_TARGETS = {None: "/settings", "tiktok_owner_activation": "/settings/tiktok/connect"}
REQUIRED_CONTRACT_FIELDS = {
    "version",
    "issued_at",
    "user_id",
    "email",
    "brand_id",
    "brand_status",
    "role",
    "platform_role",
    "effective_role",
    "app_id",
    "entitlement_status",
    "access_mode",
    "access_start_at",
    "access_expires_at",
    "allowed_apps",
    "is_internal_staff",
    "settings_visible",
    "platform_branch_scope_mode",
    "platform_branches",
}


class SsoError(ValueError):
    pass


@dataclass(frozen=True)
class VerifiedSso:
    user_id: str
    email: str
    brand_id: str
    role: str
    app_role: str | None
    access_mode: str
    settings_visible: bool
    is_internal_staff: bool
    jti: str
    expires_at: datetime
    issued_at: datetime
    launch_target: str | None
    launch_path: str
    brand_scope: Mapping[str, object]


def session_can_access_settings(session: Mapping[str, object]) -> bool:
    """Settings authority is derived from the canonical workspace role only."""

    return str(session.get("role") or "").strip().lower() in SETTINGS_ROLES


def session_can_access_integrations(session: Mapping[str, object]) -> bool:
    """Mirror Performance Marketing connection authority without granting Settings."""

    role = str(session.get("role") or "").strip().lower()
    if role in SETTINGS_ROLES:
        return True
    return (
        role == "viewer"
        and str(session.get("source_system") or "").strip().lower() == "accumulate"
        and str(session.get("app_role") or "").strip().lower() in PLATFORM_CONNECTION_APP_ROLES
        and bool(str(session.get("brand_id") or "").strip())
    )


def _contract_datetime(value: object, field: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SsoError(f"invalid_{field}")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SsoError(f"invalid_{field}") from exc
    if parsed.tzinfo is None:
        raise SsoError(f"invalid_{field}")
    return parsed.astimezone(UTC)


def _verified_brand_scope(
    contract: Mapping[str, Any], *, brand_id: str, role: str, access_mode: str
) -> dict[str, object]:
    """Validate optional multi-Brand scope; fall back to the launch Brand only."""

    raw_scope = contract.get("brand_scope")
    if raw_scope is None:
        brand_name = contract.get("brand_name")
        if brand_name is not None and not isinstance(brand_name, str):
            raise SsoError("invalid_brand_scope")
        return {
            "version": "v1",
            "default_brand_id": brand_id,
            "brands": [
                {
                    "brand_id": brand_id,
                    "name": brand_name.strip() or None if isinstance(brand_name, str) else None,
                    "parent_brand_id": None,
                    "visibility": "active",
                    "access_mode": access_mode,
                    "role": role,
                }
            ],
        }
    if not isinstance(raw_scope, Mapping) or raw_scope.get("version") != "v1":
        raise SsoError("invalid_brand_scope")
    if str(raw_scope.get("default_brand_id") or "").strip() != brand_id:
        raise SsoError("brand_scope_default_mismatch")
    raw_brands = raw_scope.get("brands")
    if (
        not isinstance(raw_brands, Sequence)
        or isinstance(raw_brands, (str, bytes))
        or not 1 <= len(raw_brands) <= 500
    ):
        raise SsoError("invalid_brand_scope")

    brands: list[dict[str, object]] = []
    known: dict[str, dict[str, object]] = {}
    for raw in raw_brands:
        if not isinstance(raw, Mapping):
            raise SsoError("invalid_brand_scope")
        item_brand_id = str(raw.get("brand_id") or "").strip()
        if not item_brand_id or item_brand_id in known:
            raise SsoError("invalid_brand_scope")
        name = raw.get("name")
        if name is not None and not isinstance(name, str):
            raise SsoError("invalid_brand_scope")
        parent = raw.get("parent_brand_id")
        parent_brand_id = str(parent).strip() if parent is not None else None
        if parent_brand_id == "":
            parent_brand_id = None
        item_role = raw.get("role")
        item_access_mode = raw.get("access_mode")
        if item_role is None and item_access_mode is None:
            visibility = "hidden_parent"
        elif item_role in CANONICAL_ROLES and item_access_mode in {"read", "write"}:
            visibility = "active"
        else:
            raise SsoError("invalid_brand_scope")
        item = {
            "brand_id": item_brand_id,
            "name": name.strip() or None if isinstance(name, str) else None,
            "parent_brand_id": parent_brand_id,
            "visibility": visibility,
            "access_mode": item_access_mode,
            "role": item_role,
        }
        brands.append(item)
        known[item_brand_id] = item

    default = known.get(brand_id)
    if (
        default is None
        or default["visibility"] != "active"
        or default["role"] != role
        or default["access_mode"] != access_mode
    ):
        raise SsoError("brand_scope_default_mismatch")
    for item in brands:
        parent_id = item["parent_brand_id"]
        if parent_id is not None and parent_id not in known:
            raise SsoError("invalid_brand_scope")
        seen = {item["brand_id"]}
        current = item
        while current["parent_brand_id"] is not None:
            parent_id = current["parent_brand_id"]
            if parent_id in seen:
                raise SsoError("brand_scope_cycle")
            seen.add(parent_id)
            current = known[str(parent_id)]
    return {"version": "v1", "default_brand_id": brand_id, "brands": brands}


def verify_sso(token: str, secret: str, now: datetime | None = None) -> VerifiedSso:
    if not secret:
        raise SsoError("sso_not_configured")
    current = (now or datetime.now(UTC)).astimezone(UTC)
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience="social_media",
            options={"require": ["aud", "exp", "jti", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise SsoError("invalid_sso") from exc

    if claims.get("iss") not in {None, "accumulate"}:
        raise SsoError("invalid_issuer")
    if claims.get("token_type") != "app_sso":
        raise SsoError("invalid_token_type")
    contract = claims.get("sso_contract")
    if not isinstance(contract, dict):
        raise SsoError("contract_missing")
    missing = sorted(REQUIRED_CONTRACT_FIELDS.difference(contract))
    if missing:
        raise SsoError(f"contract_incomplete:{','.join(missing)}")
    if contract.get("version") != "v1" or contract.get("app_id") != "social_media":
        raise SsoError("invalid_contract")

    allowed_apps = contract.get("allowed_apps")
    if (
        not isinstance(allowed_apps, list)
        or not all(isinstance(item, str) for item in allowed_apps)
        or "social_media" not in allowed_apps
    ):
        raise SsoError("app_not_allowed")
    if contract.get("entitlement_status") != "enabled":
        raise SsoError("entitlement_inactive")

    role = contract.get("role")
    if role not in CANONICAL_ROLES:
        raise SsoError("invalid_role")
    if contract.get("platform_role") != role:
        raise SsoError("role_mismatch")
    raw_app_role = contract.get("app_role")
    if raw_app_role is not None and not isinstance(raw_app_role, str):
        raise SsoError("invalid_app_role")
    app_role = raw_app_role.strip().lower() or None if isinstance(raw_app_role, str) else None
    effective_role = contract.get("effective_role")
    if not isinstance(effective_role, str) or effective_role not in {
        role,
        app_role,
    }:
        raise SsoError("role_mismatch")

    brand_status = contract.get("brand_status")
    if brand_status not in BRAND_STATUSES:
        raise SsoError("invalid_brand_status")
    expected_access_mode = "write" if brand_status == "active" and role in WRITE_ROLES else "read"
    if contract.get("access_mode") != expected_access_mode:
        raise SsoError("access_mode_mismatch")

    internal_staff = contract.get("is_internal_staff")
    signed_settings_visible = contract.get("settings_visible")
    if not isinstance(internal_staff, bool) or not isinstance(signed_settings_visible, bool):
        raise SsoError("invalid_visibility_claims")
    settings_visible = role in SETTINGS_ROLES
    if contract.get("platform_branch_scope_mode") != "all":
        raise SsoError("invalid_branch_scope")
    branches = contract.get("platform_branches")
    if not isinstance(branches, list) or not all(isinstance(item, str) for item in branches):
        raise SsoError("invalid_branch_scope")

    user_id = str(contract.get("user_id", "")).strip()
    brand_id = str(contract.get("brand_id", "")).strip()
    if not user_id or not brand_id or str(claims.get("sub")) != user_id:
        raise SsoError("missing_authority")
    if not isinstance(contract.get("email"), str) or not contract["email"].strip():
        raise SsoError("missing_identity")
    email = contract["email"].strip()

    issued_at = _contract_datetime(contract.get("issued_at"), "issued_at")
    assert issued_at is not None
    if issued_at > current + timedelta(minutes=5):
        raise SsoError("issued_at_in_future")
    access_start = _contract_datetime(contract.get("access_start_at"), "access_start_at")
    access_expiry = _contract_datetime(contract.get("access_expires_at"), "access_expires_at")
    if access_start and access_expiry and access_start >= access_expiry:
        raise SsoError("invalid_access_window")
    if access_start and current < access_start:
        raise SsoError("access_not_started")
    if access_expiry and current >= access_expiry:
        raise SsoError("access_expired")

    launch_target = claims.get("launch_target")
    if launch_target not in LAUNCH_TARGETS:
        raise SsoError("invalid_launch_target")
    jti = str(claims.get("jti", "")).strip()
    if not jti:
        raise SsoError("missing_jti")
    expires_at = datetime.fromtimestamp(int(claims["exp"]), UTC)
    if access_expiry is not None:
        expires_at = min(expires_at, access_expiry)
    expires_at = min(expires_at, current + timedelta(hours=12))
    brand_scope = _verified_brand_scope(
        contract,
        brand_id=brand_id,
        role=role,
        access_mode=expected_access_mode,
    )
    return VerifiedSso(
        user_id=user_id,
        email=email,
        brand_id=brand_id,
        role=role,
        app_role=app_role,
        access_mode=expected_access_mode,
        settings_visible=settings_visible,
        is_internal_staff=internal_staff,
        jti=jti,
        expires_at=expires_at,
        issued_at=issued_at,
        launch_target=launch_target,
        launch_path=LAUNCH_TARGETS[launch_target],
        brand_scope=brand_scope,
    )


def consume_sso(token: str, secret: str, store: SessionStore) -> tuple[str, VerifiedSso]:
    verified = verify_sso(token, secret)
    raw_session = secrets.token_urlsafe(32)
    consumed_at = datetime.now(UTC)
    jti_hash = sha256_text(verified.jti)
    session_authority = {
        "role": verified.role,
        "app_role": verified.app_role,
        "source_system": "accumulate",
        "brand_id": verified.brand_id,
    }
    integrations_visible = session_can_access_integrations(session_authority)
    permissions = (
        (PLATFORM_CONNECTION_MANAGE_PERMISSION, TIKTOK_CONNECTION_MANAGE_PERMISSION)
        if integrations_visible
        else ()
    )
    payload = {
        "user_id": verified.user_id,
        "email": verified.email,
        "source_system": "accumulate",
        "brand_id": verified.brand_id,
        "brand_scope": verified.brand_scope,
        "role": verified.role,
        "app_role": verified.app_role,
        "access_mode": verified.access_mode,
        "settings_visible": verified.settings_visible,
        "integrations_visible": integrations_visible,
        "is_internal_staff": verified.is_internal_staff,
        "expires_at": verified.expires_at.isoformat(),
        "sso_issued_at": verified.issued_at.isoformat(),
        "sso_consumed_at": consumed_at.isoformat(),
        "launch_target": verified.launch_target,
        "permissions": permissions,
        "sso_jti_hash": jti_hash,
        "revoked": False,
    }
    created = store.create_from_jti(
        jti_hash=jti_hash,
        session_hash=sha256_text(raw_session),
        payload=payload,
        expires_at=verified.expires_at,
    )
    if not created:
        raise SsoError("jti_replayed")
    return raw_session, verified


def resolve_session(raw_session: str, store: SessionStore) -> dict[str, Any] | None:
    if not raw_session:
        return None
    payload = store.get_session(sha256_text(raw_session))
    if not payload or payload.get("revoked") is True:
        return None
    return dict(payload)

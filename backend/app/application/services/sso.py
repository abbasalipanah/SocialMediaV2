"""Accumulate SSO v1 verification and hash-only local session creation."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.application.ports import SessionStore
from app.core.security import sha256_text

CANONICAL_ROLES = {"super_admin", "agency_admin", "agency_operator", "viewer"}
WRITE_ROLES = {"super_admin", "agency_admin", "agency_operator"}
BRAND_STATUSES = {"active", "suspended", "archived"}
LAUNCH_TARGETS = {None: "/overview", "tiktok_owner_activation": "/settings/tiktok/connect"}
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
    access_mode: str
    settings_visible: bool
    is_internal_staff: bool
    jti: str
    expires_at: datetime
    launch_path: str


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
    if contract.get("platform_role") != role or contract.get("effective_role") != role:
        raise SsoError("role_mismatch")

    brand_status = contract.get("brand_status")
    if brand_status not in BRAND_STATUSES:
        raise SsoError("invalid_brand_status")
    expected_access_mode = "write" if brand_status == "active" and role in WRITE_ROLES else "read"
    if contract.get("access_mode") != expected_access_mode:
        raise SsoError("access_mode_mismatch")

    internal_staff = contract.get("is_internal_staff")
    settings_visible = contract.get("settings_visible")
    if not isinstance(internal_staff, bool) or not isinstance(settings_visible, bool):
        raise SsoError("invalid_visibility_claims")
    if settings_visible != internal_staff:
        raise SsoError("settings_visibility_mismatch")
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
    return VerifiedSso(
        user_id=user_id,
        email=email,
        brand_id=brand_id,
        role=role,
        access_mode=expected_access_mode,
        settings_visible=settings_visible,
        is_internal_staff=internal_staff,
        jti=jti,
        expires_at=expires_at,
        launch_path=LAUNCH_TARGETS[launch_target],
    )


def consume_sso(token: str, secret: str, store: SessionStore) -> tuple[str, VerifiedSso]:
    verified = verify_sso(token, secret)
    raw_session = secrets.token_urlsafe(32)
    payload = {
        "user_id": verified.user_id,
        "email": verified.email,
        "source_system": "accumulate",
        "brand_id": verified.brand_id,
        "role": verified.role,
        "access_mode": verified.access_mode,
        "settings_visible": verified.settings_visible,
        "is_internal_staff": verified.is_internal_staff,
        "expires_at": verified.expires_at.isoformat(),
        "revoked": False,
    }
    created = store.create_from_jti(
        jti_hash=sha256_text(verified.jti),
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

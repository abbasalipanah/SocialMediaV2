from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from app.application.services.sso import SsoError, consume_sso, resolve_session, verify_sso
from app.core.security import sha256_text

SECRET = "local-sso-contract-secret-" + ("x" * 48)


class MemorySessionStore:
    def __init__(self) -> None:
        self.jtis: set[str] = set()
        self.sessions: dict[str, dict[str, Any]] = {}

    def create_from_jti(
        self,
        *,
        jti_hash: str,
        session_hash: str,
        payload: Mapping[str, Any],
        expires_at: datetime,
    ) -> bool:
        del expires_at
        if jti_hash in self.jtis:
            return False
        self.jtis.add(jti_hash)
        self.sessions[session_hash] = dict(payload)
        return True

    def get_session(self, session_hash: str) -> Mapping[str, Any] | None:
        return self.sessions.get(session_hash)

    def revoke_session(self, session_hash: str) -> None:
        if session_hash in self.sessions:
            self.sessions[session_hash]["revoked"] = True


def token(*, contract_overrides: Mapping[str, Any] | None = None, **top_overrides: Any) -> str:
    now = datetime.now(UTC)
    contract: dict[str, Any] = {
        "version": "v1",
        "issued_at": now.isoformat(),
        "user_id": 1,
        "email": "user@example.test",
        "brand_id": 10,
        "brand_status": "active",
        "role": "agency_admin",
        "platform_role": "agency_admin",
        "effective_role": "agency_admin",
        "app_id": "social_media",
        "entitlement_status": "enabled",
        "access_mode": "write",
        "access_start_at": None,
        "access_expires_at": None,
        "allowed_apps": ["social_media"],
        "is_internal_staff": True,
        "settings_visible": True,
        "platform_branch_scope_mode": "all",
        "platform_branches": [],
    }
    contract.update(contract_overrides or {})
    claims: dict[str, Any] = {
        "sub": "1",
        "aud": "social_media",
        "token_type": "app_sso",
        "jti": "jti-1",
        "exp": int((now + timedelta(hours=2)).timestamp()),
        "sso_contract": contract,
    }
    claims.update(top_overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_valid_upstream_contract_creates_hash_only_session_and_blocks_jti_replay() -> None:
    store = MemorySessionStore()
    raw_session, verified = consume_sso(token(), SECRET, store)
    assert verified.launch_path == "/"
    assert raw_session not in repr(store.sessions)
    assert resolve_session(raw_session, store) == next(iter(store.sessions.values()))
    assert resolve_session(raw_session, store)["settings_visible"] is True
    assert resolve_session(raw_session, store)["brand_scope"]["default_brand_id"] == "10"
    with pytest.raises(SsoError, match="jti_replayed"):
        consume_sso(token(), SECRET, store)


def test_fixed_owner_launch_target_is_allowlisted() -> None:
    verified = verify_sso(token(launch_target="tiktok_owner_activation"), SECRET)
    assert verified.launch_path == "/settings/tiktok/connect"
    assert verified.launch_target == "tiktok_owner_activation"
    with pytest.raises(SsoError, match="invalid_launch_target"):
        verify_sso(token(launch_target="https://evil.example"), SECRET)


def test_signature_issuer_audience_expiry_and_algorithm_fail_closed() -> None:
    now = datetime.now(UTC)
    with pytest.raises(SsoError, match="invalid_issuer"):
        verify_sso(token(iss="unknown"), SECRET)
    assert verify_sso(token(), SECRET).user_id == "1"
    assert verify_sso(token(iss="accumulate"), SECRET).user_id == "1"

    for invalid in (
        token(aud="another_app"),
        token(exp=int((now - timedelta(seconds=1)).timestamp())),
    ):
        with pytest.raises(SsoError, match="invalid_sso"):
            verify_sso(invalid, SECRET)

    hs384 = jwt.encode(
        jwt.decode(token(), SECRET, algorithms=["HS256"], options={"verify_aud": False}),
        SECRET,
        algorithm="HS384",
    )
    with pytest.raises(SsoError, match="invalid_sso"):
        verify_sso(hs384, SECRET)
    with pytest.raises(SsoError, match="sso_not_configured"):
        verify_sso(token(), "")


def test_owner_launch_context_is_preserved_in_the_hash_only_session() -> None:
    store = MemorySessionStore()
    raw_session, verified = consume_sso(
        token(launch_target="tiktok_owner_activation"), SECRET, store
    )
    session = resolve_session(raw_session, store)
    assert session is not None
    assert session["launch_target"] == "tiktok_owner_activation"
    assert session["sso_issued_at"] == verified.issued_at.isoformat()
    assert isinstance(session["sso_consumed_at"], str)
    assert session["permissions"] == (
        "social.connection.manage",
        "tiktok.connection.manage",
    )
    assert session["sso_jti_hash"] == sha256_text(verified.jti)
    assert verified.jti not in repr(session)


def test_role_status_access_and_visibility_invariants_fail_closed() -> None:
    with pytest.raises(SsoError, match="invalid_role"):
        verify_sso(
            token(
                contract_overrides={
                    "role": "owner",
                    "platform_role": "owner",
                    "effective_role": "owner",
                }
            ),
            SECRET,
        )
    with pytest.raises(SsoError, match="role_mismatch"):
        verify_sso(token(contract_overrides={"platform_role": "viewer"}), SECRET)
    with pytest.raises(SsoError, match="access_mode_mismatch"):
        verify_sso(
            token(
                contract_overrides={
                    "role": "viewer",
                    "platform_role": "viewer",
                    "effective_role": "viewer",
                }
            ),
            SECRET,
        )
    derived = verify_sso(token(contract_overrides={"settings_visible": False}), SECRET)
    assert derived.settings_visible is True
    with pytest.raises(SsoError, match="entitlement_inactive"):
        verify_sso(token(contract_overrides={"entitlement_status": "disabled"}), SECRET)


def test_viewer_operator_gets_integrations_without_settings() -> None:
    store = MemorySessionStore()
    raw_session, verified = consume_sso(
        token(
            contract_overrides={
                "role": "viewer",
                "platform_role": "viewer",
                "effective_role": "operator",
                "app_role": "operator",
                "access_mode": "read",
                "is_internal_staff": False,
                "settings_visible": False,
            }
        ),
        SECRET,
        store,
    )
    session = resolve_session(raw_session, store)
    assert session is not None
    assert verified.app_role == "operator"
    assert session["settings_visible"] is False
    assert session["integrations_visible"] is True
    assert session["permissions"] == (
        "social.connection.manage",
        "tiktok.connection.manage",
    )


def test_internal_agency_operator_does_not_receive_settings() -> None:
    verified = verify_sso(
        token(
            contract_overrides={
                "role": "agency_operator",
                "platform_role": "agency_operator",
                "effective_role": "agency_operator",
                "settings_visible": True,
            }
        ),
        SECRET,
    )
    assert verified.settings_visible is False


def test_contract_access_window_is_enforced_and_caps_session() -> None:
    now = datetime.now(UTC)
    with pytest.raises(SsoError, match="access_not_started"):
        verify_sso(
            token(contract_overrides={"access_start_at": (now + timedelta(minutes=5)).isoformat()}),
            SECRET,
            now,
        )
    with pytest.raises(SsoError, match="access_expired"):
        verify_sso(
            token(
                contract_overrides={"access_expires_at": (now - timedelta(seconds=1)).isoformat()}
            ),
            SECRET,
            now,
        )
    expiry = now + timedelta(minutes=30)
    verified = verify_sso(
        token(contract_overrides={"access_expires_at": expiry.isoformat()}), SECRET, now
    )
    assert verified.expires_at == expiry


def test_short_lived_launch_token_creates_a_twelve_hour_local_session() -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    verified = verify_sso(
        token(exp=int((now + timedelta(minutes=10)).timestamp())),
        SECRET,
        now,
    )

    assert verified.expires_at == now + timedelta(hours=12)


def test_contract_shape_and_subject_match_are_required() -> None:
    with pytest.raises(SsoError, match="missing_identity"):
        verify_sso(token(contract_overrides={"email": None}), SECRET)
    with pytest.raises(SsoError, match="missing_authority"):
        verify_sso(token(sub="2"), SECRET)


def test_optional_multi_brand_scope_is_signed_and_validated() -> None:
    brand_scope = {
        "version": "v1",
        "default_brand_id": "10",
        "brands": [
            {
                "brand_id": "9",
                "name": "Parent",
                "parent_brand_id": None,
                "role": None,
                "access_mode": None,
            },
            {
                "brand_id": "10",
                "name": "Child",
                "parent_brand_id": "9",
                "role": "agency_admin",
                "access_mode": "write",
            },
        ],
    }
    verified = verify_sso(token(contract_overrides={"brand_scope": brand_scope}), SECRET)
    assert verified.brand_scope["brands"][0]["visibility"] == "hidden_parent"
    assert verified.brand_scope["brands"][1]["visibility"] == "active"

    invalid = {**brand_scope, "default_brand_id": "9"}
    with pytest.raises(SsoError, match="brand_scope_default_mismatch"):
        verify_sso(token(contract_overrides={"brand_scope": invalid}), SECRET)


def test_revoked_session_is_not_resolved() -> None:
    store = MemorySessionStore()
    raw_session, _ = consume_sso(token(), SECRET, store)
    store.revoke_session(sha256_text(raw_session))
    assert resolve_session(raw_session, store) is None

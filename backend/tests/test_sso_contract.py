from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from app.application.services.sso import SsoError, consume_sso, resolve_session, verify_sso
from app.core.security import sha256_text

SECRET = "local-sso-test-secret-with-sufficient-entropy"


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

    def revoke_authority_sessions(self, *, user_id: str | None, brand_id: str | None) -> int:
        count = 0
        for payload in self.sessions.values():
            if user_id and payload["user_id"] != user_id:
                continue
            if brand_id and payload["brand_id"] != brand_id:
                continue
            payload["revoked"] = True
            count += 1
        return count


def token(
    *, contract_overrides: Mapping[str, Any] | None = None, **top_overrides: Any
) -> str:
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
    assert verified.launch_path == "/overview"
    assert raw_session not in repr(store.sessions)
    assert resolve_session(raw_session, store) == next(iter(store.sessions.values()))
    assert resolve_session(raw_session, store)["settings_visible"] is True
    with pytest.raises(SsoError, match="jti_replayed"):
        consume_sso(token(), SECRET, store)


def test_fixed_owner_launch_target_is_allowlisted() -> None:
    verified = verify_sso(token(launch_target="tiktok_owner_activation"), SECRET)
    assert verified.launch_path == "/settings/tiktok/connect"
    assert verified.launch_target == "tiktok_owner_activation"
    with pytest.raises(SsoError, match="invalid_launch_target"):
        verify_sso(token(launch_target="https://evil.example"), SECRET)


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
    with pytest.raises(SsoError, match="settings_visibility_mismatch"):
        verify_sso(token(contract_overrides={"settings_visible": False}), SECRET)
    with pytest.raises(SsoError, match="entitlement_inactive"):
        verify_sso(token(contract_overrides={"entitlement_status": "disabled"}), SECRET)


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
                contract_overrides={
                    "access_expires_at": (now - timedelta(seconds=1)).isoformat()
                }
            ),
            SECRET,
            now,
        )
    expiry = now + timedelta(minutes=30)
    verified = verify_sso(
        token(contract_overrides={"access_expires_at": expiry.isoformat()}), SECRET, now
    )
    assert verified.expires_at == expiry


def test_contract_shape_and_subject_match_are_required() -> None:
    with pytest.raises(SsoError, match="missing_identity"):
        verify_sso(token(contract_overrides={"email": None}), SECRET)
    with pytest.raises(SsoError, match="missing_authority"):
        verify_sso(token(sub="2"), SECRET)


def test_revoked_session_is_not_resolved() -> None:
    store = MemorySessionStore()
    raw_session, _ = consume_sso(token(), SECRET, store)
    store.revoke_session(sha256_text(raw_session))
    assert resolve_session(raw_session, store) is None

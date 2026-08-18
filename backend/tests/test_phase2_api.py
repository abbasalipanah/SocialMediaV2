from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


class MemoryStore:
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


def sso_token(secret: str) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": "1",
            "aud": "social_media",
            "token_type": "app_sso",
            "jti": "api-jti",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "sso_contract": {
                "version": "v1",
                "issued_at": now.isoformat(),
                "user_id": 1,
                "email": "user@example.test",
                "brand_id": 10,
                "brand_name": "Example Brand",
                "brand_status": "active",
                "role": "viewer",
                "platform_role": "viewer",
                "effective_role": "viewer",
                "app_id": "social_media",
                "entitlement_status": "enabled",
                "access_mode": "read",
                "access_start_at": None,
                "access_expires_at": None,
                "allowed_apps": ["social_media"],
                "is_internal_staff": False,
                "settings_visible": False,
                "platform_branch_scope_mode": "all",
                "platform_branches": [],
            },
        },
        secret,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_sso_session_logout_and_sso_only_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    sso_secret = "local-api-sso-secret-with-32-byte-minimum"
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("SOCIAL_DB_NAME", "social_media_v2_test")
    monkeypatch.setenv("SOCIAL_SSO_HS256_SECRET", sso_secret)
    app = create_app(MemoryStore())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        consumed = await client.get("/sso/consume", params={"token": sso_token(sso_secret)})
        assert consumed.status_code == 303
        assert consumed.headers["location"] == "/"
        assert consumed.headers["cache-control"] == "no-store"
        assert "HttpOnly" in consumed.headers["set-cookie"]
        assert "SameSite=lax" in consumed.headers["set-cookie"]

        me = await client.get("/api/auth/me")
        assert me.json()["user_id"] == "1"
        assert me.json()["email"] == "user@example.test"
        assert me.json()["source_system"] == "accumulate"
        assert me.headers["cache-control"] == "no-store"
        assert me.headers["referrer-policy"] == "no-referrer"

        workspace = await client.get("/api/workspace/brands", params={"selected_brand_id": "10"})
        assert workspace.status_code == 200
        assert workspace.json()["scope"] == {
            "requested_brand_id": "10",
            "resolved_brand_ids": ["10"],
            "rollup": False,
        }
        assert workspace.headers["cache-control"] == "no-store"
        assert (
            await client.get("/api/workspace/brands", params={"selected_brand_id": "other"})
        ).status_code == 403

        # Accumulate can enter only through SSO. No provisioning webhook remains.
        removed_endpoint = await client.post("/internal/provisioning/events", content=b"{}")
        assert removed_endpoint.status_code == 404

        assert (await client.post("/api/auth/logout")).status_code == 403
        assert (
            await client.post("/api/auth/logout", headers={"Origin": "http://test"})
        ).status_code == 204
        assert (await client.get("/api/auth/me")).status_code == 401

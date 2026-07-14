from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.application.services.provisioning import sign_request
from app.main import create_app


class MemoryStore:
    def __init__(self) -> None:
        self.jtis: set[str] = set()
        self.sessions: dict[str, dict[str, Any]] = {}
        self.nonces: set[str] = set()
        self.events: set[str] = set()
        self.projections: dict[str, dict[str, Any]] = {
            "v2:brand-shell:10": {
                "active": True,
                "brand_id": "10",
                "name": "Example Brand",
                "parent_brand_id": None,
                "placeholder": False,
            },
            "v2:brand-access:1:10": {
                "access_mode": "read",
                "active": True,
                "authority_source": "full_snapshot",
                "brand_id": "10",
                "role": "viewer",
                "user_id": "1",
            },
        }

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
            if user_id and payload.get("user_id") != user_id:
                continue
            if brand_id and payload.get("brand_id") != brand_id:
                continue
            payload["revoked"] = True
            count += 1
        return count

    def apply_event(self, **values: Any) -> str:
        if values["nonce_hash"] in self.nonces:
            return "nonce_replayed"
        self.nonces.add(values["nonce_hash"])
        if values["event_id"] in self.events:
            return "duplicate_ignored"
        self.events.add(values["event_id"])
        self.projections[values["entity_key"]] = dict(values["payload"])
        for projection_write in values.get("projection_writes", ()):
            if projection_write.insert_only and projection_write.projection_key in self.projections:
                continue
            self.projections[projection_write.projection_key] = {
                **projection_write.payload,
                "version": values["version"],
            }
        replacement = values.get("replacement")
        if replacement is not None:
            desired_keys = {write.projection_key for write in replacement.writes}
            for key, projection in self.projections.items():
                if key.startswith(replacement.projection_key_prefix) and key not in desired_keys:
                    projection.update({"active": False, "version": replacement.version})
            for projection_write in replacement.writes:
                self.projections[projection_write.projection_key] = {
                    **projection_write.payload,
                    "version": replacement.version,
                }
        return "applied"

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None:
        return self.projections.get(entity_key)

    def list_projections(self, projection_key_prefix: str) -> list[Mapping[str, Any]]:
        return [
            projection
            for key, projection in sorted(self.projections.items())
            if key.startswith(projection_key_prefix)
        ]


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
async def test_sso_session_logout_and_provisioning_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    sso_secret = "local-api-sso-secret-with-32-byte-minimum"
    hmac_secret = "local-api-hmac-secret-with-32-byte-minimum"
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("SOCIAL_DB_NAME", "social_media_v2_test")
    monkeypatch.setenv("SOCIAL_SSO_HS256_SECRET", sso_secret)
    monkeypatch.setenv("SOCIAL_PROVISIONING_HMAC_SECRET", hmac_secret)
    app = create_app(MemoryStore())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        consumed = await client.get("/sso/consume", params={"token": sso_token(sso_secret)})
        assert consumed.status_code == 303
        assert consumed.headers["location"] == "/overview"
        assert consumed.headers["cache-control"] == "no-store"
        assert "HttpOnly" in consumed.headers["set-cookie"]
        assert "SameSite=lax" in consumed.headers["set-cookie"]
        me = await client.get("/api/auth/me")
        assert me.json()["user_id"] == "1"
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
            await client.get(
                "/api/workspace/brands", params={"selected_brand_id": "other"}
            )
        ).status_code == 403

        event = json.dumps(
            {
                "event_id": "e1",
                "event_type": "brand.upserted",
                "entity_id": "b1",
                "version": 1,
                "payload": {"status": "active"},
            },
            separators=(",", ":"),
        ).encode()
        timestamp = str(int(datetime.now(UTC).timestamp()))
        nonce = "api-nonce"
        signature = sign_request(
            hmac_secret, "POST", "/internal/provisioning/events", timestamp, nonce, event
        )
        provisioned = await client.post(
            "/internal/provisioning/events",
            content=event,
            headers={
                "X-Accumulate-Timestamp": timestamp,
                "X-Accumulate-Nonce": nonce,
                "X-Accumulate-Signature": signature,
            },
        )
        assert provisioned.json() == {"status": "applied"}
        replayed = await client.post(
            "/internal/provisioning/events",
            content=event,
            headers={
                "X-Accumulate-Timestamp": timestamp,
                "X-Accumulate-Nonce": nonce,
                "X-Accumulate-Signature": signature,
            },
        )
        assert replayed.status_code == 409

        revoked_event = json.dumps(
            {
                "event_id": "e2",
                "event_type": "brand.app_access.changed",
                "entity_id": "10",
                "version": 2,
                "payload": {"status": "disabled"},
            },
            separators=(",", ":"),
        ).encode()
        revoked_nonce = "api-revoke-nonce"
        revoked_signature = sign_request(
            hmac_secret,
            "POST",
            "/internal/provisioning/events",
            timestamp,
            revoked_nonce,
            revoked_event,
        )
        revoked = await client.post(
            "/internal/provisioning/events",
            content=revoked_event,
            headers={
                "X-Accumulate-Timestamp": timestamp,
                "X-Accumulate-Nonce": revoked_nonce,
                "X-Accumulate-Signature": revoked_signature,
            },
        )
        assert revoked.json() == {"status": "applied"}
        assert (await client.get("/api/auth/me")).status_code == 401
        assert (await client.post("/api/auth/logout")).status_code == 403
        assert (
            await client.post("/api/auth/logout", headers={"Origin": "http://test"})
        ).status_code == 204
        assert (await client.get("/api/auth/me")).status_code == 401

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import COOKIE_NAME
from app.application.ports import ActivationResult, ActivationStart
from app.core.security import sha256_text
from app.main import create_app
from tests.test_phase6_dashboard_api import MemoryAuthority, MemoryReporting


class FakeSelfServiceActivation:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def ready_for_start(self, context, *, require_gate_context: bool = True) -> bool:
        assert context.brand_id == 101
        self.calls.append(("ready", require_gate_context))
        return True

    def start(self, context, *, require_gate_context: bool = True) -> ActivationStart:
        assert context.brand_id == 101
        self.calls.append(("start", require_gate_context))
        return ActivationStart(
            authorization_url="https://www.tiktok.com/v2/auth/authorize/?state=self-service",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

    def complete(
        self,
        *,
        query,
        context,
        require_gate_context: bool = True,
    ) -> ActivationResult:
        # What Login Kit returns: `code`, the scopes it granted, and `state`.
        assert query == {
            "code": "authorization-code",
            "scopes": "user.info.basic,video.list",
            "state": "self-service",
        }
        assert context.brand_id == 101
        self.calls.append(("complete", require_gate_context))
        return ActivationResult(
            connection_id=77,
            link_id=88,
            brand_id=101,
            state="pending_verification",
            optional_scopes_available=(),
        )


def _make_self_service_session(authority: MemoryAuthority) -> dict[str, object]:
    session = authority.sessions[sha256_text(authority.raw_session)]
    session["role"] = "viewer"
    session["app_role"] = "operator"
    session["source_system"] = "accumulate"
    session["access_mode"] = "read"
    session["settings_visible"] = False
    session["integrations_visible"] = True
    session["is_internal_staff"] = False
    session["permissions"] = (
        "social.connection.manage",
        "tiktok.connection.manage",
    )
    for brand in session["brand_scope"]["brands"]:
        if brand["brand_id"] == session["brand_id"]:
            brand["role"] = "viewer"
            brand["access_mode"] = "read"
    session["launch_target"] = None
    session.pop("sso_issued_at", None)
    session.pop("sso_consumed_at", None)
    session.pop("sso_jti_hash", None)
    return session


def _reporting(tmp_path) -> MemoryReporting:
    media_path = tmp_path / "media.jpg"
    media_path.write_bytes(b"self-service-test-media")
    return MemoryReporting(media_path)


@pytest.mark.asyncio
async def test_self_service_readiness_is_brand_scoped_without_owner_sso(
    tmp_path,
) -> None:
    authority = MemoryAuthority()
    session = _make_self_service_session(authority)
    app = create_app(authority, _reporting(tmp_path))

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as client:
        response = await client.get(
            "/api/integrations/tiktok/self-service/readiness",
            params={"brand_id": "101"},
        )
        capabilities = await client.get(
            "/api/workspace/capabilities",
            params={"selected_brand_id": "101"},
        )
        integration_accounts = await client.get(
            "/api/integrations/status/social-accounts",
            params={"brand_id": "101"},
        )
        settings_accounts = await client.get(
            "/api/settings/social-accounts",
            params={"brand_id": "101"},
        )

        assert response.status_code == 200
        assert response.json() | {"checked_at": "ignored"} == {
            "brand_id": "101",
            "can_manage": True,
            "connection_state": "disconnected",
            "linked_account_count": 0,
            "oauth_start_available": False,
            "reason": "provider_activation_not_configured",
            "runtime_mode": "development",
            "writes_enabled": False,
            "checked_at": "ignored",
        }
        assert response.headers["cache-control"] == "no-store"
        assert capabilities.json()["permissions"]["settings_visible"] is False
        assert capabilities.json()["permissions"]["integrations_visible"] is True
        assert capabilities.json()["permissions"]["tiktok_connection_manage"] is True
        assert integration_accounts.status_code == 200
        assert settings_accounts.status_code == 403

        session["app_role"] = "viewer"
        denied = await client.get(
            "/api/integrations/tiktok/self-service/readiness",
            params={"brand_id": "101"},
        )
        assert denied.status_code == 403
        assert denied.json() == {"detail": "integrations_capability_required"}
        denied_status = await client.get(
            "/api/integrations/status/social-accounts",
            params={"brand_id": "101"},
        )
        assert denied_status.status_code == 403

        session["app_role"] = "operator"
        wrong_brand = await client.get(
            "/api/integrations/tiktok/self-service/readiness",
            params={"brand_id": "102"},
        )
        assert wrong_brand.status_code == 403
        wrong_brand_status = await client.get(
            "/api/integrations/status/social-accounts",
            params={"brand_id": "102"},
        )
        assert wrong_brand_status.status_code == 403


@pytest.mark.asyncio
async def test_self_service_start_and_callback_use_non_sso_context(tmp_path) -> None:
    authority = MemoryAuthority()
    _make_self_service_session(authority)
    activation = FakeSelfServiceActivation()
    app = create_app(
        authority,
        _reporting(tmp_path),
        tiktok_activation=activation,
    )

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
        follow_redirects=False,
    ) as client:
        readiness = await client.get(
            "/api/integrations/tiktok/self-service/readiness",
            params={"brand_id": "101"},
        )
        started = await client.post(
            "/api/integrations/tiktok/oauth/start",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
        )
        callback = await client.get(
            "/api/social/tiktok/oauth/callback",
            params={
                "code": "authorization-code",
                "scopes": "user.info.basic,video.list",
                "state": "self-service",
            },
        )

    assert readiness.json()["oauth_start_available"] is True
    assert started.status_code == 200
    assert started.json()["authorization_url"].startswith("https://www.tiktok.com/")
    assert callback.status_code == 200
    assert callback.headers["content-type"].startswith("text/html")
    assert '"type":"social-media:tiktok-oauth"' in callback.text
    assert '"brandId":"101"' in callback.text
    assert '"connectionState":"pending_verification"' in callback.text
    assert activation.calls == [
        ("ready", False),
        ("start", False),
        ("complete", False),
    ]

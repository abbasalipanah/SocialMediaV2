from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import COOKIE_NAME
from app.application.ports import (
    ActivationStart,
    OAuthConnectionResult,
    OAuthDiscovery,
    OAuthLinkResult,
)
from app.application.ports.reporting import ReportingAccount, ReportingConnection
from app.core.security import sha256_text
from app.domain.platforms import PlatformId
from app.main import create_app
from tests.test_phase6_dashboard_api import MemoryAuthority, MemoryReporting


class FakeOAuthActivation:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.callback_brand = 101

    def ready_for_start(self, context) -> bool:
        assert context.brand_id == 101
        self.calls.append("ready")
        return True

    def list_discoveries(self, context):
        assert context.brand_id == 101
        self.calls.append("discoveries")
        return (
            OAuthDiscovery(
                71,
                PlatformId.YOUTUBE,
                "UC-linked",
                "Linked Channel",
                "linked",
            ),
            OAuthDiscovery(
                71,
                PlatformId.YOUTUBE,
                "UC-available",
                "Available Channel",
                "available",
            ),
        )

    def start(self, context) -> ActivationStart:
        assert context.brand_id == 101
        self.calls.append("start")
        return ActivationStart(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth?state=signed",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

    def callback_brand_id(self, *, query) -> int:
        assert query["state"] == "signed"
        self.calls.append("callback_brand")
        return self.callback_brand

    def complete(self, *, query, context) -> OAuthConnectionResult:
        assert query == {
            "code": "authorization-code",
            "scope": "youtube.readonly",
            "state": "signed",
        }
        assert context.brand_id == 101
        self.calls.append("complete")
        return OAuthConnectionResult(
            71,
            101,
            PlatformId.YOUTUBE,
            "pending_verification",
            2,
        )

    def link_accounts(self, *, context, connection_id, selections) -> OAuthLinkResult:
        assert context.brand_id == 101
        assert connection_id == 71
        assert [item.external_id for item in selections] == ["UC-available"]
        self.calls.append("link")
        return OAuthLinkResult(
            71,
            101,
            PlatformId.YOUTUBE,
            1,
            "connected",
        )

    def unlink(self, *, context, external_id) -> OAuthLinkResult:
        assert context.brand_id == 101
        assert external_id == "UC-linked"
        self.calls.append("unlink")
        return OAuthLinkResult(
            71,
            101,
            PlatformId.YOUTUBE,
            0,
            "disconnected",
        )


def _reporting(tmp_path) -> MemoryReporting:
    media_path = tmp_path / "media.jpg"
    media_path.write_bytes(b"oauth-channel-api")
    reporting = MemoryReporting(media_path)
    reporting.accounts += (
        ReportingAccount(
            account_id=81,
            brand_id="101",
            platform=PlatformId.YOUTUBE,
            external_id="UC-linked",
            display_name="Linked Channel",
            status="active",
            connection_state="connected",
            health_status="unknown",
            backfill_status="pending",
            nightly_enabled=True,
            last_synced_at=None,
            link_status="connected",
        ),
    )
    reporting.connections += (
        ReportingConnection(
            connection_id=71,
            brand_id="101",
            platform=PlatformId.YOUTUBE,
            state="connected",
            expires_at=None,
            projected_at=datetime.now(UTC),
        ),
    )
    return reporting


@pytest.mark.asyncio
async def test_youtube_self_service_lifecycle_is_brand_scoped(tmp_path) -> None:
    authority = MemoryAuthority()
    activation = FakeOAuthActivation()
    app = create_app(
        authority,
        _reporting(tmp_path),
        youtube_activation=activation,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as browser:
        readiness = await browser.get(
            "/api/integrations/youtube/self-service/readiness",
            params={"brand_id": "101"},
        )
        started = await browser.post(
            "/api/integrations/youtube/oauth/start",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
        )
        linked = await browser.post(
            "/api/integrations/youtube/accounts/link",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
            json={"connection_id": 71, "external_ids": ["UC-available"]},
        )
        unlinked = await browser.delete(
            "/api/integrations/youtube/accounts/unlink",
            params={"brand_id": "101", "external_id": "UC-linked"},
            headers={"Origin": "http://test"},
        )
        callback = await browser.get(
            "/api/social/youtube/oauth/callback",
            params={
                "code": "authorization-code",
                "scope": "youtube.readonly",
                "state": "signed",
            },
        )

    assert readiness.status_code == 200
    assert readiness.json() | {"checked_at": "ignored"} == {
        "brand_id": "101",
        "platform": "youtube",
        "can_manage": True,
        "connection_state": "pending_verification",
        "linked_account_count": 1,
        "linked_accounts": [
            {
                "connection_id": 71,
                "external_id": "UC-linked",
                "display_name": "Linked Channel",
                "state": "linked",
            }
        ],
        "available_accounts": [
            {
                "connection_id": 71,
                "external_id": "UC-available",
                "display_name": "Available Channel",
                "state": "available",
            }
        ],
        "oauth_start_available": True,
        "reason": "self_service_available",
        "runtime_mode": "development",
        "writes_enabled": False,
        "checked_at": "ignored",
    }
    assert started.status_code == 200
    assert linked.json() == {
        "connection_id": 71,
        "linked_count": 1,
        "connection_state": "connected",
    }
    assert unlinked.json() == {
        "brand_id": "101",
        "platform": "youtube",
        "external_id": "UC-linked",
        "connection_state": "disconnected",
    }
    assert callback.status_code == 200
    assert '"type":"social-media:youtube-oauth"' in callback.text
    assert '"discoveredCount":2' in callback.text
    assert activation.calls == [
        "discoveries",
        "ready",
        "start",
        "link",
        "unlink",
        "callback_brand",
        "complete",
    ]


@pytest.mark.asyncio
async def test_oauth_channel_viewer_can_start_but_cannot_manage_accounts(tmp_path) -> None:
    authority = MemoryAuthority()
    session = authority.sessions[sha256_text(authority.raw_session)]
    session.update(
        {
            "role": "viewer",
            "app_role": "operator",
            "source_system": "accumulate",
            "access_mode": "read",
            "settings_visible": False,
            "integrations_visible": True,
            "is_internal_staff": False,
        }
    )
    activation = FakeOAuthActivation()
    app = create_app(
        authority,
        _reporting(tmp_path),
        youtube_activation=activation,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as browser:
        readiness = await browser.get(
            "/api/integrations/youtube/self-service/readiness",
            params={"brand_id": "101"},
        )
        started = await browser.post(
            "/api/integrations/youtube/oauth/start",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
        )
        linked = await browser.post(
            "/api/integrations/youtube/accounts/link",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
            json={"connection_id": 71, "external_ids": ["UC-available"]},
        )

    assert readiness.status_code == 200
    assert readiness.json()["can_manage"] is False
    assert readiness.json()["linked_accounts"] == []
    assert readiness.json()["available_accounts"] == []
    assert started.status_code == 200
    assert linked.status_code == 403
    assert linked.json() == {"detail": "settings_capability_required"}
    assert activation.calls == ["ready", "start"]


@pytest.mark.asyncio
async def test_unconfigured_youtube_stays_fail_closed(tmp_path) -> None:
    authority = MemoryAuthority()
    app = create_app(authority, _reporting(tmp_path))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as browser:
        readiness = await browser.get(
            "/api/integrations/youtube/self-service/readiness",
            params={"brand_id": "101"},
        )
        started = await browser.post(
            "/api/integrations/youtube/oauth/start",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
        )

    assert readiness.status_code == 200
    assert readiness.json()["oauth_start_available"] is False
    assert readiness.json()["reason"] == "provider_activation_not_configured"
    assert started.status_code == 503
    assert started.json() == {"detail": "oauth_channel_not_configured"}

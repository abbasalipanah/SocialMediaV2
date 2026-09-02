from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import COOKIE_NAME
from app.application.ports import (
    ActivationStart,
    MetaCatalogAccount,
    MetaConnectionResult,
    MetaDiscovery,
    MetaLinkResult,
)
from app.core.security import sha256_text
from app.domain.platforms import PlatformId
from app.main import create_app
from tests.test_phase6_dashboard_api import MemoryAuthority, MemoryReporting


class FakeMetaActivation:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.link_selections: list[tuple[PlatformId, str]] = []
        self.catalog_link_selections: list[tuple[PlatformId, str]] = []

    def ready_for_start(self, context) -> bool:
        assert context.brand_id == 101
        self.calls.append("ready")
        return True

    def start(self, context) -> ActivationStart:
        assert context.brand_id == 101
        self.calls.append("start")
        return ActivationStart(
            authorization_url="https://www.facebook.com/v26.0/dialog/oauth?state=bound",
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )

    def complete(self, *, query, context) -> MetaConnectionResult:
        assert query == {"code": "authorization-value", "state": "bound"}
        assert context.brand_id == 101
        self.calls.append("complete")
        return MetaConnectionResult(
            connection_id=91,
            brand_id=101,
            state="pending_verification",
            facebook_count=1,
            instagram_count=1,
        )

    def list_discoveries(self, context) -> tuple[MetaDiscovery, ...]:
        assert context.brand_id == 101
        self.calls.append("discoveries")
        return (
            MetaDiscovery(91, PlatformId.FACEBOOK, "10001", "Coastal Page", "discovered"),
            MetaDiscovery(
                91,
                PlatformId.INSTAGRAM,
                "20002",
                "coastal.hotel",
                "discovered",
            ),
        )

    def list_catalog_accounts(self, context) -> tuple[MetaCatalogAccount, ...]:
        assert context.brand_id == 101
        self.calls.append("catalog")
        return (
            MetaCatalogAccount(PlatformId.FACEBOOK, "10001", "Coastal Page"),
            MetaCatalogAccount(PlatformId.INSTAGRAM, "20002", "coastal.hotel"),
        )

    def refresh_accounts(self, context) -> MetaConnectionResult:
        assert context.brand_id == 101
        self.calls.append("refresh")
        return MetaConnectionResult(
            connection_id=91,
            brand_id=101,
            state="connected",
            facebook_count=40,
            instagram_count=59,
        )

    def link_accounts(self, *, context, connection_id, selections) -> MetaLinkResult:
        assert context.brand_id == 101
        assert connection_id == 91
        self.link_selections = [
            (item.platform, item.external_id) for item in selections
        ]
        self.calls.append("link")
        return MetaLinkResult(
            connection_id=91,
            brand_id=101,
            linked_count=len(selections),
            state="connected" if selections else "disconnected",
        )

    def link_catalog_accounts(self, *, context, selections) -> MetaLinkResult:
        assert context.brand_id == 101
        self.catalog_link_selections = [
            (item.platform, item.external_id) for item in selections
        ]
        self.calls.append("catalog_link")
        return MetaLinkResult(
            connection_id=92,
            brand_id=101,
            linked_count=len(selections),
            state="connected" if selections else "disconnected",
        )


def _session(authority: MemoryAuthority) -> dict[str, object]:
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


def _settings_session(authority: MemoryAuthority) -> dict[str, object]:
    session = _session(authority)
    session["role"] = "agency_admin"
    session["app_role"] = None
    session["access_mode"] = "write"
    session["settings_visible"] = True
    for brand in session["brand_scope"]["brands"]:
        if brand["brand_id"] == session["brand_id"]:
            brand["role"] = "agency_admin"
            brand["access_mode"] = "write"
    return session


def _reporting(tmp_path) -> MemoryReporting:
    media_path = tmp_path / "media.jpg"
    media_path.write_bytes(b"meta-self-service-test")
    return MemoryReporting(media_path)


@pytest.mark.asyncio
async def test_meta_readiness_is_exact_brand_and_hides_accounts_from_viewer(tmp_path) -> None:
    authority = MemoryAuthority()
    _session(authority)
    activation = FakeMetaActivation()
    app = create_app(
        authority,
        _reporting(tmp_path),
        meta_activation=activation,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as browser:
        readiness = await browser.get(
            "/api/integrations/meta/self-service/readiness",
            params={"brand_id": "101"},
        )
        capabilities = await browser.get(
            "/api/workspace/capabilities",
            params={"selected_brand_id": "101"},
        )
        wrong_brand = await browser.get(
            "/api/integrations/meta/self-service/readiness",
            params={"brand_id": "102"},
        )

    assert readiness.status_code == 200
    payload = readiness.json()
    assert payload["can_manage"] is True
    assert payload["oauth_start_available"] is True
    assert payload["connection_state"] == "connected"
    assert payload["facebook_linked_count"] == 0
    assert payload["instagram_linked_count"] == 0
    assert payload["linked_accounts"] == []
    assert payload["discoveries"] == []
    assert payload["catalog_accounts"] == []
    assert capabilities.json()["permissions"]["settings_visible"] is False
    assert capabilities.json()["permissions"]["meta_connection_manage"] is True
    assert wrong_brand.status_code == 403


@pytest.mark.asyncio
async def test_meta_viewer_can_authorize_but_account_management_requires_settings(tmp_path) -> None:
    authority = MemoryAuthority()
    _session(authority)
    activation = FakeMetaActivation()
    app = create_app(
        authority,
        _reporting(tmp_path),
        meta_activation=activation,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
        follow_redirects=False,
    ) as browser:
        started = await browser.post(
            "/api/integrations/meta/oauth/start",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
        )
        callback = await browser.get(
            "/api/social/meta/oauth/callback",
            params={"code": "authorization-value", "state": "bound"},
        )
        viewer_refreshed = await browser.post(
            "/api/integrations/meta/accounts/refresh",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
        )
        viewer_linked = await browser.post(
            "/api/integrations/meta/accounts/link",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
            json={
                "connection_id": 91,
                "accounts": [
                    {"platform": "facebook", "external_id": "10001"},
                    {"platform": "instagram", "external_id": "20002"},
                ],
            },
        )
        viewer_catalog_linked = await browser.post(
            "/api/settings/meta/accounts/link",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
            json={"accounts": [{"platform": "facebook", "external_id": "10001"}]},
        )

        _settings_session(authority)
        settings_readiness = await browser.get(
            "/api/integrations/meta/self-service/readiness",
            params={"brand_id": "101"},
        )
        refreshed = await browser.post(
            "/api/integrations/meta/accounts/refresh",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
        )
        linked = await browser.post(
            "/api/integrations/meta/accounts/link",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
            json={
                "connection_id": 91,
                "accounts": [
                    {"platform": "facebook", "external_id": "10001"},
                    {"platform": "instagram", "external_id": "20002"},
                ],
            },
        )
        catalog_linked = await browser.post(
            "/api/settings/meta/accounts/link",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
            json={"accounts": [{"platform": "facebook", "external_id": "10001"}]},
        )

    assert started.status_code == 200
    assert started.json()["authorization_url"].startswith("https://www.facebook.com/")
    assert callback.status_code == 200
    assert '"type":"social-media:meta-oauth"' in callback.text
    assert '"facebookCount":0' in callback.text
    assert '"instagramCount":0' in callback.text
    assert viewer_refreshed.status_code == 403
    assert viewer_refreshed.json() == {"detail": "settings_capability_required"}
    assert viewer_linked.status_code == 403
    assert viewer_linked.json() == {"detail": "settings_capability_required"}
    assert viewer_catalog_linked.status_code == 403
    assert viewer_catalog_linked.json() == {"detail": "settings_capability_required"}
    assert settings_readiness.status_code == 200
    assert settings_readiness.json()["catalog_accounts"] == [
        {"platform": "facebook", "external_id": "10001", "display_name": "Coastal Page"},
        {"platform": "instagram", "external_id": "20002", "display_name": "coastal.hotel"},
    ]
    assert refreshed.status_code == 200
    assert refreshed.json() == {
        "connection_id": 91,
        "facebook_count": 40,
        "instagram_count": 59,
        "discovered_count": 99,
    }
    assert linked.json() == {
        "connection_id": 91,
        "linked_count": 2,
        "connection_state": "connected",
    }
    assert catalog_linked.json() == {
        "connection_id": 92,
        "linked_count": 1,
        "connection_state": "connected",
    }
    assert activation.link_selections == [
        (PlatformId.FACEBOOK, "10001"),
        (PlatformId.INSTAGRAM, "20002"),
    ]
    assert activation.catalog_link_selections == [(PlatformId.FACEBOOK, "10001")]
    assert activation.calls == [
        "start", "complete", "discoveries", "catalog", "ready", "refresh", "link",
        "catalog_link",
    ]


@pytest.mark.asyncio
async def test_meta_link_accepts_an_empty_selection_to_unlink_all(tmp_path) -> None:
    authority = MemoryAuthority()
    _settings_session(authority)
    activation = FakeMetaActivation()
    app = create_app(
        authority,
        _reporting(tmp_path),
        meta_activation=activation,
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as browser:
        response = await browser.post(
            "/api/integrations/meta/accounts/link",
            params={"brand_id": "101"},
            headers={"Origin": "http://test"},
            json={"connection_id": 91, "accounts": []},
        )

    assert response.status_code == 200
    assert response.json() == {
        "connection_id": 91,
        "linked_count": 0,
        "connection_state": "disconnected",
    }
    assert activation.link_selections == []

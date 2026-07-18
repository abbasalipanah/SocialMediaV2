from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.local_demo import create_local_demo_app


@pytest.fixture(autouse=True)
def local_demo_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_LOCAL_DEMO", "true")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "development")
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "false")
    for key in ("SOCIAL_DB_URL", "SOCIAL_DB_HOST", "SOCIAL_DB_NAME", "SOCIAL_DB_USER"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_local_demo_opens_a_scoped_session_and_serves_product_data() -> None:
    application = create_local_demo_app()
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://127.0.0.1:8000",
    ) as browser:
        assert (await browser.get("/api/auth/me")).status_code == 401
        assert (await browser.post("/api/dev/session")).status_code == 403

        opened = await browser.post(
            "/api/dev/session", headers={"X-Social-Local-Demo": "true"}
        )
        assert opened.status_code == 204
        assert opened.headers["x-social-local-demo"] == "true"

        identity = await browser.get("/api/auth/me")
        assert identity.status_code == 200
        assert identity.json()["email"] == "local.demo@example.test"

        workspace = await browser.get("/api/workspace/brands")
        assert workspace.status_code == 200
        assert [brand["name"] for brand in workspace.json()["brands"]] == [
            "Demo Hotel Group",
            "Demo Resort",
            "Demo City Hotel",
        ]

        capabilities = await browser.get(
            "/api/workspace/capabilities", params={"selected_brand_id": "101"}
        )
        assert capabilities.status_code == 200
        assert {
            item["platform"]: item["navigation_available"]
            for item in capabilities.json()["platforms"]
        } == {"facebook": True, "instagram": True, "tiktok": True}

        dashboard = await browser.get(
            "/api/dashboards/overview", params={"brand_id": "101", "range": "last_30_days"}
        )
        assert dashboard.status_code == 200
        assert dashboard.json()["meta"]["data_status"] == "partial"
        assert {item["meta"]["platform"] for item in dashboard.json()["platforms"]} == {
            "facebook",
            "instagram",
            "tiktok",
        }

        settings = await browser.get("/api/settings/social-accounts", params={"brand_id": "101"})
        assert settings.status_code == 200
        assert len(settings.json()["items"]) == 3

        closed = await browser.post(
            "/api/dev/logout", headers={"X-Social-Local-Demo": "true"}
        )
        assert closed.status_code == 204
        assert (await browser.get("/api/auth/me")).status_code == 401


def test_local_demo_requires_an_explicit_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SOCIAL_LOCAL_DEMO")
    with pytest.raises(RuntimeError, match="SOCIAL_LOCAL_DEMO=true"):
        create_local_demo_app()

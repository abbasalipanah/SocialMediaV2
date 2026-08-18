"""The launch also arrives as a form POST, because the URL has a ceiling.

The signed contract carries the accessible Brand family, so a launch URL grows
with the Brand catalogue and a large one is dropped in transit before it ever
reaches the application. Both routes must behave identically.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from tests.test_phase2_api import MemoryStore, sso_token

SSO_SECRET = "local-api-sso-secret-with-32-byte-minimum"
FORM = {"content-type": "application/x-www-form-urlencoded"}


def _app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("SOCIAL_DB_NAME", "social_media_v2_test")
    monkeypatch.setenv("SOCIAL_SSO_HS256_SECRET", SSO_SECRET)
    return create_app(MemoryStore())


@pytest.mark.asyncio
async def test_post_launch_matches_the_get_launch(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        response = await client.post(
            "/sso/consume", content=f"token={sso_token(SSO_SECRET)}", headers=FORM
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "content_type", "expected"),
    [
        ("token=", "application/x-www-form-urlencoded", 400),
        ("nottoken=value", "application/x-www-form-urlencoded", 400),
        ("token=one&token=two", "application/x-www-form-urlencoded", 400),
        ('{"token":"value"}', "application/json", 415),
    ],
)
async def test_malformed_launch_bodies_are_refused(
    monkeypatch: pytest.MonkeyPatch, body: str, content_type: str, expected: int
) -> None:
    app = _app(monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        response = await client.post(
            "/sso/consume", content=body, headers={"content-type": content_type}
        )

    assert response.status_code == expected


@pytest.mark.asyncio
async def test_oversized_launch_body_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", follow_redirects=False
    ) as client:
        response = await client.post(
            "/sso/consume",
            content="token=" + ("a" * (256 * 1024 + 1)),
            headers=FORM,
        )

    assert response.status_code == 413

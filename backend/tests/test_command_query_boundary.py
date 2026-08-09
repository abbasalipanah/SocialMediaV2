from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from app.api import create_api_router
from app.core import WritePolicy, load_settings
from app.main import create_app


def _api_routes() -> list[APIRoute]:
    settings = load_settings()
    router = create_api_router(settings, WritePolicy.from_settings(settings))
    routes: list[APIRoute] = []
    pending = list(router.routes)
    while pending:
        route = pending.pop()
        if isinstance(route, APIRoute):
            routes.append(route)
        elif included := getattr(route, "original_router", None):
            pending.extend(included.routes)
    return routes


def test_all_routes_have_explicit_boundary_semantics() -> None:
    routes = _api_routes()
    assert {(route.path, tuple(sorted(route.methods))) for route in routes} == {
        ("/api/auth/logout", ("POST",)),
        ("/api/auth/me", ("GET",)),
        ("/api/dashboards/facebook", ("GET",)),
        ("/api/dashboards/instagram", ("GET",)),
        ("/api/dashboards/overview", ("GET",)),
        ("/api/dashboards/tiktok", ("GET",)),
        ("/api/health", ("GET",)),
        ("/api/insights", ("GET",)),
        ("/api/insights/generate", ("POST",)),
        ("/api/insights/limit", ("GET",)),
        ("/api/integrations/meta/accounts/link", ("POST",)),
        ("/api/integrations/meta/oauth/start", ("POST",)),
        ("/api/integrations/meta/self-service/readiness", ("GET",)),
        ("/api/integrations/status/connections", ("GET",)),
        ("/api/integrations/status/social-accounts", ("GET",)),
        ("/api/integrations/status/sync-jobs", ("GET",)),
        ("/api/integrations/tiktok/oauth/start", ("POST",)),
        ("/api/integrations/tiktok/self-service/readiness", ("GET",)),
        ("/api/media/{platform}/{content_id}", ("GET",)),
        ("/api/operations/backfill", ("POST",)),
        ("/api/operations/readiness", ("GET",)),
        ("/api/operations/sync", ("POST",)),
        ("/api/platforms/facebook/accounts", ("GET",)),
        ("/api/platforms/instagram/accounts", ("GET",)),
        ("/api/platforms/tiktok/accounts", ("GET",)),
        ("/api/settings/audit", ("GET",)),
        ("/api/settings/brand-links", ("GET",)),
        ("/api/settings/brands", ("GET",)),
        ("/api/settings/connections", ("GET",)),
        ("/api/settings/social-accounts", ("GET",)),
        ("/api/settings/sync-jobs", ("GET",)),
        ("/api/settings/tiktok/connection", ("DELETE",)),
        ("/api/settings/tiktok/connection", ("GET",)),
        ("/api/settings/tiktok/activation-readiness", ("GET",)),
        ("/api/settings/tiktok/oauth/account/start", ("POST",)),
        ("/api/social/tiktok/oauth/callback", ("GET",)),
        ("/api/social/meta/oauth/callback", ("GET",)),
        ("/api/workspace/brands", ("GET",)),
        ("/api/workspace/capabilities", ("GET",)),
        ("/sso/consume", ("GET",)),
    }
    for route in routes:
        boundary = route.endpoint.__route_boundary__
        if route.path in {
            "/sso/consume",
            "/api/social/meta/oauth/callback",
            "/api/social/tiktok/oauth/callback",
        }:
            assert route.methods == {"GET"}
            assert boundary == "protocol_command"
        elif route.methods == {"GET"}:
            assert boundary == "query"
        else:
            assert route.methods in ({"POST"}, {"DELETE"})
            assert boundary == "command"


@pytest.mark.asyncio
async def test_health_and_readiness_are_safe_and_fail_closed() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        health = await client.get("/api/health")
        readiness = await client.get("/api/operations/readiness")
    assert health.json() == {"status": "ok"}
    assert readiness.status_code == 200
    assert readiness.json() == {
        "status": "ready",
        "runtime_mode": "development",
        "writes_enabled": False,
        "database_configured": False,
    }
    assert app.state.write_policy.allows("sync") is False

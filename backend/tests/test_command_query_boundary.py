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
    return [route for route in router.routes if isinstance(route, APIRoute)]


def test_all_bootstrap_get_routes_are_explicit_queries() -> None:
    routes = _api_routes()
    assert {route.path for route in routes} == {"/api/health", "/api/operations/readiness"}
    for route in routes:
        assert route.methods == {"GET"}
        assert route.endpoint.__route_boundary__ == "query"


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

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
    assert {route.path for route in routes} == {
        "/api/health",
        "/api/operations/readiness",
        "/api/auth/me",
        "/api/auth/logout",
        "/api/workspace/brands",
        "/sso/consume",
        "/internal/provisioning/events",
    }
    for route in routes:
        boundary = route.endpoint.__route_boundary__
        if route.path == "/sso/consume":
            assert route.methods == {"GET"}
            assert boundary == "protocol_command"
        elif route.methods == {"GET"}:
            assert boundary == "query"
        else:
            assert route.methods == {"POST"}
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

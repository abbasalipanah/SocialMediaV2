"""Bootstrap API routes with explicit query semantics."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.auth import create_auth_router
from app.api.internal import create_internal_router
from app.application.ports import AuthorityStore
from app.core import AppSettings, Boundary, WritePolicy, mark_boundary


def create_api_router(
    settings: AppSettings,
    policy: WritePolicy,
    store: AuthorityStore | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/health", tags=["health"], summary="Health probe")
    @mark_boundary(Boundary.QUERY)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(
        "/api/operations/readiness",
        tags=["operations"],
        summary="Dormant readiness probe",
    )
    @mark_boundary(Boundary.QUERY)
    async def readiness() -> dict[str, str | bool]:
        return {
            "status": "ready",
            "runtime_mode": settings.runtime_mode.value,
            "writes_enabled": policy.writes_enabled,
            "database_configured": settings.db.configured,
        }

    router.include_router(create_auth_router(settings, policy, store))
    router.include_router(create_internal_router(settings, policy, store))
    return router


__all__ = ["create_api_router"]

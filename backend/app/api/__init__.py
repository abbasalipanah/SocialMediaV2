"""Bootstrap API routes with explicit query semantics."""

from __future__ import annotations

from fastapi import APIRouter

from app.core import AppSettings, Boundary, WritePolicy, mark_boundary


def create_api_router(settings: AppSettings, policy: WritePolicy) -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/health", tags=["health"], summary="Health probe")
    @mark_boundary(Boundary.QUERY)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(
        "/operations/readiness",
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

    return router


__all__ = ["create_api_router"]

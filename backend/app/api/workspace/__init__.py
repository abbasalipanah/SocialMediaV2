"""Brand family workspace query routes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Query, Response

from app.api.auth import COOKIE_NAME
from app.api.contracts import (
    CapabilityPlatform,
    RuntimeCapabilities,
    WorkspaceCapabilitiesResponse,
    WorkspacePermissions,
)
from app.application.ports import AuthorityStore
from app.application.services.authority import AuthorityError, build_brand_workspace
from app.application.services.sso import resolve_session
from app.capabilities import PlatformCapabilityRegistry
from app.core import Boundary, RuntimeMode, WritePolicy, mark_boundary
from app.domain.authority import BrandWorkspace
from app.domain.platforms import PlatformId


def create_workspace_router(
    store: AuthorityStore | None,
    capabilities: PlatformCapabilityRegistry,
    policy: WritePolicy,
    runtime_mode: RuntimeMode,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/workspace/brands", response_model=BrandWorkspace)
    @mark_boundary(Boundary.QUERY)
    async def workspace_brands(
        response: Response,
        selected_brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> BrandWorkspace:
        if store is None or not session or not (payload := resolve_session(session, store)):
            raise HTTPException(401, "session_invalid")
        user_id = str(payload.get("user_id") or "")
        launch_brand_id = str(payload.get("brand_id") or "")
        try:
            workspace = build_brand_workspace(
                store=store,
                user_id=user_id,
                selected_brand_id=selected_brand_id or launch_brand_id,
                rollup=rollup,
            )
        except AuthorityError as exc:
            raise HTTPException(403, str(exc)) from exc
        response.headers["Cache-Control"] = "no-store"
        return workspace

    @router.get(
        "/api/workspace/capabilities", response_model=WorkspaceCapabilitiesResponse
    )
    @mark_boundary(Boundary.QUERY)
    async def workspace_capabilities(
        response: Response,
        selected_brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> WorkspaceCapabilitiesResponse:
        if store is None or not session or not (payload := resolve_session(session, store)):
            raise HTTPException(401, "session_invalid")
        try:
            workspace = build_brand_workspace(
                store=store,
                user_id=str(payload.get("user_id") or ""),
                selected_brand_id=selected_brand_id or str(payload.get("brand_id") or ""),
                rollup=rollup,
            )
        except AuthorityError as exc:
            raise HTTPException(403, str(exc)) from exc
        response.headers["Cache-Control"] = "no-store"
        return WorkspaceCapabilitiesResponse(
            scope=workspace.scope,
            platforms=tuple(
                CapabilityPlatform(
                    platform=platform,
                    capabilities=tuple(
                        record
                        for record in capabilities.records()
                        if record.platform is platform
                    ),
                )
                for platform in PlatformId
            ),
            permissions=WorkspacePermissions(
                settings_visible=payload.get("settings_visible") is True,
                internal_audit_visible=payload.get("is_internal_staff") is True,
                rollup_available=True,
                operation_mutation_available=False,
            ),
            runtime=RuntimeCapabilities(
                mode=runtime_mode,
                writes_enabled=policy.writes_enabled,
                automated_schedule_available=False,
            ),
        )

    return router


__all__ = ["create_workspace_router"]

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
from app.application.ports import AuthorityStore, ReportingStore
from app.application.queries.brand_visibility import brands_with_social_media
from app.application.services.authority import AuthorityError, build_brand_workspace
from app.application.services.sso import (
    resolve_session,
    session_can_access_integrations,
    session_can_access_settings,
)
from app.capabilities import PlatformCapabilityRegistry
from app.core import Boundary, RuntimeMode, WritePolicy, mark_boundary
from app.domain.authority import BrandWorkspace
from app.domain.platforms import PlatformId


def create_workspace_router(
    store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    capabilities: PlatformCapabilityRegistry,
    policy: WritePolicy,
    runtime_mode: RuntimeMode,
    automated_schedule_available: bool = False,
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
        launch_brand_id = str(payload.get("brand_id") or "")
        try:
            workspace = build_brand_workspace(
                session=payload,
                selected_brand_id=selected_brand_id or launch_brand_id,
                rollup=rollup,
            )
        except AuthorityError as exc:
            raise HTTPException(403, str(exc)) from exc
        workspace = brands_with_social_media(
            workspace,
            reporting_store=reporting_store,
            keep_brand_id=selected_brand_id or launch_brand_id,
        )
        response.headers["Cache-Control"] = "no-store"
        return workspace

    @router.get("/api/workspace/capabilities", response_model=WorkspaceCapabilitiesResponse)
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
                session=payload,
                selected_brand_id=selected_brand_id or str(payload.get("brand_id") or ""),
                rollup=rollup,
            )
        except AuthorityError as exc:
            raise HTTPException(403, str(exc)) from exc
        accounts = (
            reporting_store.list_accounts(
                brand_ids=workspace.scope.resolved_brand_ids,
            )
            if reporting_store is not None
            else ()
        )
        response.headers["Cache-Control"] = "no-store"
        selected_brand_is_session_brand = (
            workspace.scope.rollup is False
            and workspace.scope.requested_brand_id == str(payload.get("brand_id") or "")
            and workspace.scope.resolved_brand_ids == (str(payload.get("brand_id") or ""),)
        )
        integrations_visible = session_can_access_integrations(payload)
        return WorkspaceCapabilitiesResponse(
            scope=workspace.scope,
            platforms=tuple(
                CapabilityPlatform(
                    platform=platform,
                    capabilities=tuple(
                        record for record in capabilities.records() if record.platform is platform
                    ),
                    linked_account_count=sum(account.platform is platform for account in accounts),
                    # Whether this Brand can open the platform, which is a
                    # question about its accounts. The capability records say
                    # what the product supports, so folding them in here left
                    # every platform navigable for every Brand: TikTok opened
                    # on a Brand with no TikTok account and showed an empty
                    # dashboard headed "No Accounts".
                    navigation_available=any(
                        account.platform is platform for account in accounts
                    ),
                )
                for platform in PlatformId
            ),
            permissions=WorkspacePermissions(
                settings_visible=session_can_access_settings(payload),
                integrations_visible=integrations_visible,
                internal_audit_visible=(
                    session_can_access_settings(payload)
                    and payload.get("is_internal_staff") is True
                ),
                rollup_available=True,
                operation_mutation_available=False,
                tiktok_connection_manage=(selected_brand_is_session_brand and integrations_visible),
                meta_connection_manage=(selected_brand_is_session_brand and integrations_visible),
            ),
            runtime=RuntimeCapabilities(
                mode=runtime_mode,
                writes_enabled=policy.writes_enabled,
                automated_schedule_available=automated_schedule_available,
            ),
        )

    return router


__all__ = ["create_workspace_router"]

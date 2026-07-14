"""Read-only Settings surface and fail-closed connection commands."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request

from app.api.auth import COOKIE_NAME
from app.api.contracts import (
    AuditResponse,
    BrandLinkItem,
    BrandLinksResponse,
    ConnectionsResponse,
    SettingsBrandItem,
    SettingsBrandsResponse,
    SocialAccountsResponse,
    SyncJobsResponse,
    TikTokConnectionResponse,
)
from app.api.scope import RequestScope, resolve_request_scope
from app.application.ports import AuthorityStore, ReportingStore
from app.capabilities import PlatformCapabilityRegistry
from app.core import Boundary, WritePolicy, mark_boundary
from app.domain.platforms import CapabilityId, PlatformId

TIKTOK_CONNECTION_STATES = {
    "disconnected",
    "pending_owner_activation",
    "pending_verification",
    "connected",
    "revoked",
    "error",
}


def create_settings_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    capabilities: PlatformCapabilityRegistry,
    policy: WritePolicy,
) -> APIRouter:
    router = APIRouter()

    def _scope(
        *, raw_session: str | None, brand_id: str | None, rollup: bool
    ) -> RequestScope:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        return resolve_request_scope(
            store=authority_store,
            raw_session=raw_session,
            selected_brand_id=brand_id,
            rollup=rollup,
            require_settings=True,
        )

    @router.get("/api/settings/brands", response_model=SettingsBrandsResponse)
    @mark_boundary(Boundary.QUERY)
    async def brands(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> SettingsBrandsResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=rollup)
        assert reporting_store is not None
        visible_ids = tuple(item.brand_id for item in scope.workspace.brands)
        accounts = reporting_store.list_accounts(brand_ids=visible_ids)
        return SettingsBrandsResponse(
            meta=scope.workspace.scope,
            items=tuple(
                SettingsBrandItem(
                    brand_id=item.brand_id,
                    name=item.name,
                    parent_brand_id=item.parent_brand_id,
                    visibility=item.visibility,
                    access_mode=item.access_mode,
                    role=item.role,
                    linked_account_count=sum(
                        account.brand_id == item.brand_id for account in accounts
                    ),
                    last_sync_at=max(
                        (
                            account.last_synced_at
                            for account in accounts
                            if account.brand_id == item.brand_id
                            and account.last_synced_at is not None
                        ),
                        default=None,
                    ),
                )
                for item in scope.workspace.brands
            ),
        )

    @router.get("/api/settings/social-accounts", response_model=SocialAccountsResponse)
    @mark_boundary(Boundary.QUERY)
    async def social_accounts(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        platform: Annotated[PlatformId | None, Query()] = None,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> SocialAccountsResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=rollup)
        assert reporting_store is not None
        accounts = reporting_store.list_accounts(
            brand_ids=scope.workspace.scope.resolved_brand_ids,
            platform=platform,
        )
        return SocialAccountsResponse(meta=scope.workspace.scope, items=accounts)

    @router.get("/api/settings/brand-links", response_model=BrandLinksResponse)
    @mark_boundary(Boundary.QUERY)
    async def brand_links(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> BrandLinksResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=rollup)
        assert reporting_store is not None
        accounts = reporting_store.list_accounts(
            brand_ids=scope.workspace.scope.resolved_brand_ids
        )
        return BrandLinksResponse(
            meta=scope.workspace.scope,
            items=tuple(
                BrandLinkItem(
                    brand_id=account.brand_id,
                    platform=account.platform,
                    account_id=account.account_id,
                    external_id=account.external_id,
                    display_name=account.display_name,
                    link_status=account.status,
                )
                for account in accounts
            ),
        )

    @router.get("/api/settings/connections", response_model=ConnectionsResponse)
    @mark_boundary(Boundary.QUERY)
    async def connections(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> ConnectionsResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=rollup)
        assert reporting_store is not None
        rows = reporting_store.list_connections(
            brand_ids=scope.workspace.scope.resolved_brand_ids
        )
        return ConnectionsResponse(meta=scope.workspace.scope, items=rows)

    @router.get("/api/settings/sync-jobs", response_model=SyncJobsResponse)
    @mark_boundary(Boundary.QUERY)
    async def sync_jobs(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> SyncJobsResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=rollup)
        assert reporting_store is not None
        rows = reporting_store.list_sync_jobs(
            brand_ids=scope.workspace.scope.resolved_brand_ids
        )
        return SyncJobsResponse(meta=scope.workspace.scope, items=rows)

    @router.get("/api/settings/audit", response_model=AuditResponse)
    @mark_boundary(Boundary.QUERY)
    async def audit(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> AuditResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=rollup)
        return AuditResponse(
            meta=scope.workspace.scope,
            status="unavailable",
            reason="operational_audit_store_not_configured",
            items=(),
        )

    @router.get(
        "/api/settings/tiktok/connection", response_model=TikTokConnectionResponse
    )
    @mark_boundary(Boundary.QUERY)
    async def tiktok_connection(
        brand_id: str | None = Query(default=None),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> TikTokConnectionResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=False)
        assert reporting_store is not None
        rows = tuple(
            row
            for row in reporting_store.list_connections(
                brand_ids=scope.workspace.scope.resolved_brand_ids
            )
            if row.platform is PlatformId.TIKTOK
        )
        selected = rows[-1] if rows else None
        state = selected.state if selected else "disconnected"
        if state not in TIKTOK_CONNECTION_STATES:
            state = "error"
        return TikTokConnectionResponse(
            meta=scope.workspace.scope,
            state=state,
            connection=selected,
            capabilities=tuple(
                capabilities.get(PlatformId.TIKTOK, capability)
                for capability in CapabilityId
            ),
            checked_at=datetime.now(UTC),
        )

    @router.delete("/api/settings/tiktok/connection", status_code=503)
    @mark_boundary(Boundary.COMMAND)
    async def delete_tiktok_connection(
        request: Request,
        brand_id: str | None = Query(default=None),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> None:
        _same_origin(request)
        resolve_request_scope(
            store=authority_store,
            raw_session=session,
            selected_brand_id=brand_id,
            rollup=False,
            require_write=True,
            require_settings=True,
        )
        try:
            policy.assert_allows_mutation("tiktok_connection_delete")
        except PermissionError as exc:
            raise HTTPException(403, "writes_disabled") from exc
        raise HTTPException(503, "connection_mutation_unavailable_before_cutover")

    return router


def _same_origin(request: Request) -> None:
    if request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "origin_invalid")


__all__ = ["create_settings_router"]

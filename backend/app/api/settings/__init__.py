"""Read-only Settings surface and fail-closed connection commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response

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
    TikTokActivationReadinessResponse,
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
TIKTOK_OWNER_LAUNCH_TARGET = "tiktok_owner_activation"
TIKTOK_OWNER_SSO_FRESHNESS = timedelta(minutes=10)


def create_settings_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    capabilities: PlatformCapabilityRegistry,
    policy: WritePolicy,
) -> APIRouter:
    router = APIRouter()

    def _scope(
        *,
        raw_session: str | None,
        brand_id: str | None,
        rollup: bool,
        require_write: bool = False,
    ) -> RequestScope:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        return resolve_request_scope(
            store=authority_store,
            raw_session=raw_session,
            selected_brand_id=brand_id,
            rollup=rollup,
            require_write=require_write,
            require_settings=True,
        )

    def _session_time(session: dict[str, object], field: str) -> datetime:
        value = session.get(field)
        if not isinstance(value, str):
            raise HTTPException(403, "fresh_owner_sso_required")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HTTPException(403, "fresh_owner_sso_required") from exc
        if parsed.tzinfo is None:
            raise HTTPException(403, "fresh_owner_sso_required")
        return parsed.astimezone(UTC)

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

    @router.get(
        "/api/settings/tiktok/activation-readiness",
        response_model=TikTokActivationReadinessResponse,
    )
    @mark_boundary(Boundary.QUERY)
    async def tiktok_activation_readiness(
        response: Response,
        brand_id: str | None = Query(default=None),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> TikTokActivationReadinessResponse:
        scope = _scope(
            raw_session=session,
            brand_id=brand_id,
            rollup=False,
            require_write=True,
        )
        launch_brand_id = str(scope.session.get("brand_id") or "")
        requested_brand_id = scope.workspace.scope.requested_brand_id
        if (
            scope.session.get("launch_target") != TIKTOK_OWNER_LAUNCH_TARGET
            or requested_brand_id != launch_brand_id
            or scope.workspace.scope.rollup
            or scope.workspace.scope.resolved_brand_ids != (launch_brand_id,)
        ):
            raise HTTPException(403, "tiktok_owner_launch_required")
        current = datetime.now(UTC)
        issued_at = _session_time(scope.session, "sso_issued_at")
        consumed_at = _session_time(scope.session, "sso_consumed_at")
        fresh_until = min(
            issued_at + TIKTOK_OWNER_SSO_FRESHNESS,
            consumed_at + TIKTOK_OWNER_SSO_FRESHNESS,
        )
        if (
            issued_at > current + timedelta(minutes=5)
            or consumed_at > current
            or current >= fresh_until
        ):
            raise HTTPException(403, "fresh_owner_sso_required")
        assert reporting_store is not None
        rows = tuple(
            row
            for row in reporting_store.list_connections(brand_ids=(launch_brand_id,))
            if row.platform is PlatformId.TIKTOK
        )
        connection_state = rows[-1].state if rows else "disconnected"
        if connection_state not in TIKTOK_CONNECTION_STATES:
            connection_state = "error"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return TikTokActivationReadinessResponse(
            handoff_ready=True,
            brand_id=launch_brand_id,
            launch_target=TIKTOK_OWNER_LAUNCH_TARGET,
            fresh_until=fresh_until,
            runtime_mode=policy.runtime_mode,
            writes_enabled=policy.writes_enabled,
            connection_state=connection_state,
            oauth_start_available=False,
            reason="oauth_start_unavailable_before_cutover",
            checked_at=current,
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

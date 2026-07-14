"""Read-only Settings surface and fail-closed connection commands."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

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
from app.application.ports import (
    ActivationContext,
    AuthorityStore,
    ReportingStore,
    TikTokActivationError,
)
from app.application.services.sso import TIKTOK_CONNECTION_MANAGE_PERMISSION
from app.application.services.tiktok_activation import TikTokActivationCoordinator
from app.capabilities import PlatformCapabilityRegistry
from app.core import Boundary, WritePolicy, mark_boundary
from app.core.security import sha256_text
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
TIKTOK_OWNER_SSO_FRESHNESS = timedelta(minutes=5)


def create_settings_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    capabilities: PlatformCapabilityRegistry,
    policy: WritePolicy,
    activation: TikTokActivationCoordinator | None = None,
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

    def _owner_context(
        *,
        raw_session: str | None,
        requested_brand_id: str | None,
    ) -> tuple[RequestScope, ActivationContext, datetime]:
        scope = _scope(
            raw_session=raw_session,
            brand_id=requested_brand_id,
            rollup=False,
            require_write=True,
        )
        launch_brand_id = str(scope.session.get("brand_id") or "")
        resolved_brand_ids = scope.workspace.scope.resolved_brand_ids
        if (
            scope.session.get("launch_target") != TIKTOK_OWNER_LAUNCH_TARGET
            or scope.workspace.scope.requested_brand_id != launch_brand_id
            or scope.workspace.scope.rollup
            or resolved_brand_ids != (launch_brand_id,)
        ):
            raise HTTPException(403, "tiktok_owner_launch_required")
        permissions = scope.session.get("permissions")
        if (
            not isinstance(permissions, (list, tuple))
            or TIKTOK_CONNECTION_MANAGE_PERMISSION not in permissions
        ):
            raise HTTPException(403, "tiktok_connection_manage_required")
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
        jti_hash = scope.session.get("sso_jti_hash")
        if not isinstance(jti_hash, str):
            raise HTTPException(403, "fresh_owner_sso_required")
        try:
            numeric_brand_id = int(launch_brand_id)
            context = ActivationContext(
                user_id=str(scope.session.get("user_id") or ""),
                brand_id=numeric_brand_id,
                session_binding=sha256_text(raw_session or ""),
                sso_jti_hash=jti_hash,
                sso_consumed_at=consumed_at,
            )
        except (TypeError, ValueError, TikTokActivationError) as exc:
            raise HTTPException(403, "tiktok_owner_launch_required") from exc
        return scope, context, fresh_until

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
        scope, owner_context, fresh_until = _owner_context(
            raw_session=session,
            requested_brand_id=brand_id,
        )
        launch_brand_id = str(scope.session.get("brand_id") or "")
        current = datetime.now(UTC)
        assert reporting_store is not None
        rows = tuple(
            row
            for row in reporting_store.list_connections(brand_ids=(launch_brand_id,))
            if row.platform is PlatformId.TIKTOK
        )
        connection_state = rows[-1].state if rows else "disconnected"
        if connection_state not in TIKTOK_CONNECTION_STATES:
            connection_state = "error"
        start_available = activation is not None and activation.ready_for_start(owner_context)
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
            oauth_start_available=start_available,
            reason=(
                "manual_intent_available"
                if start_available
                else "oauth_start_unavailable_before_cutover"
            ),
            checked_at=current,
        )

    @router.post("/api/settings/tiktok/oauth/account/start", status_code=303)
    @mark_boundary(Boundary.COMMAND)
    async def tiktok_activation_start(
        request: Request,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> RedirectResponse:
        _same_origin(request)
        if activation is None:
            raise HTTPException(503, "owner_activation_unavailable")
        _, context, _ = _owner_context(raw_session=session, requested_brand_id=None)
        try:
            started = activation.start(context)
        except TikTokActivationError as exc:
            _raise_activation_error(exc)
        response = RedirectResponse(started.authorization_url, status_code=303)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @router.get("/api/social/tiktok/oauth/callback", status_code=303)
    @mark_boundary(Boundary.PROTOCOL_COMMAND)
    async def tiktok_activation_callback(
        request: Request,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> RedirectResponse:
        if activation is None:
            raise HTTPException(503, "owner_activation_unavailable")
        pairs = list(request.query_params.multi_items())
        if len(pairs) != 2 or len({key for key, _ in pairs}) != 2:
            raise HTTPException(400, "activation_callback_rejected")
        _, context, _ = _owner_context(raw_session=session, requested_brand_id=None)
        try:
            result = activation.complete(query=dict(pairs), context=context)
        except TikTokActivationError as exc:
            _raise_activation_error(exc)
        if result.state != "pending_verification":
            raise HTTPException(503, "activation_completion_failed")
        response = RedirectResponse(
            "/settings/tiktok/connect?activation=pending_verification",
            status_code=303,
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

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


def _raise_activation_error(exc: TikTokActivationError) -> None:
    reason = str(exc)
    if reason == "activation_disabled":
        raise HTTPException(503, "owner_activation_unavailable") from exc
    if reason == "activation_authority_denied":
        raise HTTPException(403, "activation_authority_denied") from exc
    if reason == "activation_callback_rejected":
        raise HTTPException(400, "activation_callback_rejected") from exc
    if reason in {"activation_scope_denied", "activation_scope_mismatch"}:
        raise HTTPException(409, reason) from exc
    raise HTTPException(503, "activation_completion_failed") from exc


__all__ = ["create_settings_router"]

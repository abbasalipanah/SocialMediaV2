"""Read-only Settings surface and fail-closed connection commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.api.auth import COOKIE_NAME
from app.api.contracts import (
    AuditResponse,
    BrandLinkItem,
    BrandLinksResponse,
    ConnectionsResponse,
    MetaDiscoveryItem,
    MetaLinkedAccountItem,
    MetaLinkResponse,
    MetaSelfServiceReadinessResponse,
    MetaSelfServiceStartResponse,
    SettingsBrandItem,
    SettingsBrandsResponse,
    SocialAccountsResponse,
    SyncJobsResponse,
    TikTokActivationReadinessResponse,
    TikTokConnectionResponse,
    TikTokSelfServiceReadinessResponse,
    TikTokSelfServiceStartResponse,
)
from app.api.scope import RequestScope, resolve_request_scope
from app.application.ports import (
    ActivationContext,
    AuthorityStore,
    MetaActivationError,
    MetaLinkSelection,
    ReportingStore,
    TikTokActivationError,
)
from app.application.queries.brand_visibility import brands_with_social_media
from app.application.services.meta_activation import MetaActivationCoordinator
from app.application.services.sso import (
    TIKTOK_CONNECTION_MANAGE_PERMISSION,
    resolve_session,
    session_can_access_settings,
)
from app.application.services.tiktok_activation import TikTokActivationCoordinator
from app.capabilities import PlatformCapabilityRegistry
from app.core import Boundary, WritePolicy, mark_boundary
from app.core.security import sha256_text
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.providers.tiktok.accounts.oauth_state import CALLBACK_FIELDS

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


class MetaAccountSelectionPayload(BaseModel):
    platform: PlatformId
    external_id: str = Field(min_length=1, max_length=64)


class MetaLinkPayload(BaseModel):
    connection_id: int = Field(gt=0)
    accounts: list[MetaAccountSelectionPayload] = Field(max_length=200)


def create_settings_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    capabilities: PlatformCapabilityRegistry,
    policy: WritePolicy,
    activation: TikTokActivationCoordinator | None = None,
    meta_activation: MetaActivationCoordinator | None = None,
) -> APIRouter:
    router = APIRouter()

    def _scope(
        *,
        raw_session: str | None,
        brand_id: str | None,
        rollup: bool,
        require_write: bool = False,
        require_settings: bool = True,
        require_integrations: bool = False,
    ) -> RequestScope:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        return resolve_request_scope(
            store=authority_store,
            raw_session=raw_session,
            selected_brand_id=brand_id,
            rollup=rollup,
            require_write=require_write,
            require_settings=require_settings,
            require_integrations=require_integrations,
        )

    def _integration_scope(
        *,
        raw_session: str | None,
        brand_id: str | None,
        rollup: bool,
    ) -> RequestScope:
        scope = _scope(
            raw_session=raw_session,
            brand_id=brand_id,
            rollup=rollup,
            require_settings=False,
            require_integrations=True,
        )
        if not session_can_access_settings(scope.session):
            session_brand_id = str(scope.session.get("brand_id") or "")
            if (
                scope.workspace.scope.rollup
                or scope.workspace.scope.requested_brand_id != session_brand_id
                or scope.workspace.scope.resolved_brand_ids != (session_brand_id,)
            ):
                raise HTTPException(403, "integration_brand_forbidden")
        return scope

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

    def _self_service_context(
        *,
        raw_session: str | None,
        requested_brand_id: str | None,
    ) -> tuple[RequestScope, ActivationContext]:
        scope = _scope(
            raw_session=raw_session,
            brand_id=requested_brand_id,
            rollup=False,
            require_write=False,
            require_settings=False,
            require_integrations=True,
        )
        # The Brand being set up, as for Meta: an admin opens Brand Setup for the
        # row they clicked, which need not be the Brand this session was launched
        # with. The signed scope has already been resolved, and the activation
        # authority re-checks write access on this Brand before any exchange.
        target_brand_id = scope.workspace.scope.requested_brand_id
        session_brand_id = str(scope.session.get("brand_id") or "")
        # Settings authority may set up any Brand its signed scope grants: an
        # admin opens Brand Setup for the row they clicked, which need not be the
        # Brand this session was launched with. A session delegated by Accumulate
        # for one Brand -- a viewer carrying a connection app role -- stays bound
        # to that Brand, which is the whole point of the delegation.
        if target_brand_id != session_brand_id and not session_can_access_settings(
            scope.session
        ):
            raise HTTPException(403, "tiktok_self_service_brand_forbidden")
        if scope.workspace.scope.rollup or scope.workspace.scope.resolved_brand_ids != (
            target_brand_id,
        ):
            raise HTTPException(403, "tiktok_self_service_brand_forbidden")
        try:
            context = ActivationContext(
                user_id=str(scope.session.get("user_id") or ""),
                brand_id=int(target_brand_id),
                session_binding=sha256_text(raw_session or ""),
                # These legacy-named context fields carry a stable, session-bound
                # self-service authority reference. They do not assert an SSO handoff.
                sso_jti_hash=sha256_text(f"tiktok-self-service:{raw_session or ''}"),
                sso_consumed_at=datetime.fromtimestamp(0, UTC),
            )
        except (TypeError, ValueError, TikTokActivationError) as exc:
            raise HTTPException(403, "tiktok_self_service_brand_forbidden") from exc
        return scope, context

    def _meta_context(
        *,
        raw_session: str | None,
        requested_brand_id: str | None,
    ) -> tuple[RequestScope, ActivationContext]:
        scope = _scope(
            raw_session=raw_session,
            brand_id=requested_brand_id,
            rollup=False,
            require_write=False,
            require_settings=False,
            require_integrations=True,
        )
        # The Brand being set up, which need not be the one this session was
        # launched with: an admin opens Brand Setup from the Settings table for
        # whichever Brand's row they clicked. `_scope` has already resolved the
        # request against the signed scope, and the activation authority
        # re-checks write access on this Brand before anything is exchanged.
        target_brand_id = scope.workspace.scope.requested_brand_id
        session_brand_id = str(scope.session.get("brand_id") or "")
        # Settings authority may set up any Brand its signed scope grants: an
        # admin opens Brand Setup for the row they clicked, which need not be the
        # Brand this session was launched with. A session delegated by Accumulate
        # for one Brand -- a viewer carrying a connection app role -- stays bound
        # to that Brand, which is the whole point of the delegation.
        if target_brand_id != session_brand_id and not session_can_access_settings(
            scope.session
        ):
            raise HTTPException(403, "meta_self_service_brand_forbidden")
        if scope.workspace.scope.rollup or scope.workspace.scope.resolved_brand_ids != (
            target_brand_id,
        ):
            raise HTTPException(403, "meta_self_service_brand_forbidden")
        try:
            context = ActivationContext(
                user_id=str(scope.session.get("user_id") or ""),
                brand_id=int(target_brand_id),
                session_binding=sha256_text(raw_session or ""),
                sso_jti_hash=sha256_text(f"meta-self-service:{raw_session or ''}"),
                sso_consumed_at=datetime.fromtimestamp(0, UTC),
            )
        except (TypeError, ValueError, TikTokActivationError) as exc:
            raise HTTPException(403, "meta_self_service_brand_forbidden") from exc
        return scope, context

    @router.get("/api/settings/brands", response_model=SettingsBrandsResponse)
    @mark_boundary(Boundary.QUERY)
    async def brands(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> SettingsBrandsResponse:
        scope = _scope(raw_session=session, brand_id=brand_id, rollup=rollup)
        assert reporting_store is not None
        # The same narrowing the switcher applies. Listing every Brand the user
        # may open in Accumulate meant this page offered a hundred and
        # thirty-five rows where the product serves a third of them, and each
        # extra row read as a Brand whose accounts had gone missing.
        workspace = brands_with_social_media(
            scope.workspace,
            reporting_store=reporting_store,
            keep_brand_id=brand_id or scope.workspace.default_brand_id,
        )
        visible_ids = tuple(item.brand_id for item in workspace.brands)
        accounts = reporting_store.list_accounts(brand_ids=visible_ids)
        return SettingsBrandsResponse(
            meta=workspace.scope,
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
                for item in workspace.brands
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
        accounts = reporting_store.list_accounts(brand_ids=scope.workspace.scope.resolved_brand_ids)
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
        rows = reporting_store.list_connections(brand_ids=scope.workspace.scope.resolved_brand_ids)
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
        rows = reporting_store.list_sync_jobs(brand_ids=scope.workspace.scope.resolved_brand_ids)
        return SyncJobsResponse(meta=scope.workspace.scope, items=rows)

    @router.get(
        "/api/integrations/status/social-accounts",
        response_model=SocialAccountsResponse,
    )
    @mark_boundary(Boundary.QUERY)
    async def integration_social_accounts(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        platform: Annotated[PlatformId | None, Query()] = None,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> SocialAccountsResponse:
        scope = _integration_scope(
            raw_session=session,
            brand_id=brand_id,
            rollup=rollup,
        )
        assert reporting_store is not None
        rows = reporting_store.list_accounts(
            brand_ids=scope.workspace.scope.resolved_brand_ids,
            platform=platform,
        )
        return SocialAccountsResponse(meta=scope.workspace.scope, items=rows)

    @router.get(
        "/api/integrations/status/connections",
        response_model=ConnectionsResponse,
    )
    @mark_boundary(Boundary.QUERY)
    async def integration_connections(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> ConnectionsResponse:
        scope = _integration_scope(
            raw_session=session,
            brand_id=brand_id,
            rollup=rollup,
        )
        assert reporting_store is not None
        rows = reporting_store.list_connections(brand_ids=scope.workspace.scope.resolved_brand_ids)
        return ConnectionsResponse(meta=scope.workspace.scope, items=rows)

    @router.get(
        "/api/integrations/status/sync-jobs",
        response_model=SyncJobsResponse,
    )
    @mark_boundary(Boundary.QUERY)
    async def integration_sync_jobs(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> SyncJobsResponse:
        scope = _integration_scope(
            raw_session=session,
            brand_id=brand_id,
            rollup=rollup,
        )
        assert reporting_store is not None
        rows = reporting_store.list_sync_jobs(brand_ids=scope.workspace.scope.resolved_brand_ids)
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
        "/api/integrations/meta/self-service/readiness",
        response_model=MetaSelfServiceReadinessResponse,
    )
    @mark_boundary(Boundary.QUERY)
    async def meta_self_service_readiness(
        response: Response,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> MetaSelfServiceReadinessResponse:
        scope, context = _meta_context(
            raw_session=session,
            requested_brand_id=brand_id,
        )
        assert reporting_store is not None
        accounts = tuple(
            account
            for account in reporting_store.list_accounts(brand_ids=(brand_id,))
            if account.platform in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}
        )
        connections = tuple(
            row
            for row in reporting_store.list_connections(brand_ids=(brand_id,))
            if row.platform is PlatformId.FACEBOOK
        )
        discoveries = (
            meta_activation.list_discoveries(context) if meta_activation is not None else ()
        )
        selected = connections[-1] if connections else None
        connection_state = (
            selected.state if selected else ("connected" if accounts else "disconnected")
        )
        if any(item.status == "discovered" for item in discoveries):
            connection_state = "pending_verification"
        start_available = meta_activation is not None and meta_activation.ready_for_start(context)
        if start_available:
            reason = "self_service_available"
        elif meta_activation is None:
            reason = "provider_activation_not_configured"
        elif not policy.writes_enabled:
            reason = "writes_disabled"
        else:
            reason = "provider_activation_unavailable"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return MetaSelfServiceReadinessResponse(
            brand_id=scope.workspace.scope.requested_brand_id,
            can_manage=True,
            connection_state=connection_state,
            facebook_linked_count=sum(item.platform is PlatformId.FACEBOOK for item in accounts),
            instagram_linked_count=sum(item.platform is PlatformId.INSTAGRAM for item in accounts),
            linked_accounts=tuple(
                MetaLinkedAccountItem(
                    platform=item.platform,
                    external_id=item.external_id,
                    display_name=item.display_name,
                )
                for item in accounts
            ),
            discoveries=tuple(
                MetaDiscoveryItem(
                    connection_id=item.connection_id,
                    platform=item.platform,
                    external_id=item.external_id,
                    display_name=item.display_name,
                    status=item.status,
                )
                for item in discoveries
            ),
            oauth_start_available=start_available,
            reason=reason,
            runtime_mode=policy.runtime_mode,
            writes_enabled=policy.writes_enabled,
            checked_at=datetime.now(UTC),
        )

    @router.post(
        "/api/integrations/meta/oauth/start",
        response_model=MetaSelfServiceStartResponse,
    )
    @mark_boundary(Boundary.COMMAND)
    async def meta_self_service_start(
        request: Request,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> MetaSelfServiceStartResponse:
        _same_origin(request)
        if meta_activation is None:
            raise HTTPException(503, "meta_self_service_unavailable")
        _, context = _meta_context(
            raw_session=session,
            requested_brand_id=brand_id,
        )
        try:
            started = meta_activation.start(context)
        except MetaActivationError as exc:
            _raise_meta_activation_error(exc)
        return MetaSelfServiceStartResponse(
            authorization_url=started.authorization_url,
            expires_at=started.expires_at,
        )

    @router.post(
        "/api/integrations/meta/accounts/link",
        response_model=MetaLinkResponse,
    )
    @mark_boundary(Boundary.COMMAND)
    async def meta_link_accounts(
        payload: MetaLinkPayload,
        request: Request,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> MetaLinkResponse:
        _same_origin(request)
        if meta_activation is None:
            raise HTTPException(503, "meta_self_service_unavailable")
        _, context = _meta_context(
            raw_session=session,
            requested_brand_id=brand_id,
        )
        try:
            result = meta_activation.link_accounts(
                context=context,
                connection_id=payload.connection_id,
                selections=tuple(
                    MetaLinkSelection(
                        platform=item.platform,
                        external_id=item.external_id,
                    )
                    for item in payload.accounts
                ),
            )
        except MetaActivationError as exc:
            _raise_meta_activation_error(exc)
        return MetaLinkResponse(
            connection_id=result.connection_id,
            linked_count=result.linked_count,
            connection_state=result.state,
        )

    @router.get(
        "/api/social/meta/oauth/callback",
        response_model=None,
    )
    @mark_boundary(Boundary.PROTOCOL_COMMAND)
    async def meta_activation_callback(
        request: Request,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> HTMLResponse:
        if meta_activation is None:
            return _meta_callback_page(
                brand_id="",
                error_code="meta_self_service_unavailable",
                status_code=503,
            )
        pairs = list(request.query_params.multi_items())
        payload = (
            resolve_session(session, authority_store)
            if session and authority_store is not None
            else None
        )
        brand_id = str(payload.get("brand_id") or "") if payload else ""
        if any(key in {"error", "error_reason", "error_description"} for key, _ in pairs):
            return _meta_callback_page(
                brand_id=brand_id,
                error_code="meta_authorization_declined",
                status_code=400,
            )
        if len(pairs) != 2 or {key for key, _ in pairs} != {"code", "state"}:
            return _meta_callback_page(
                brand_id=brand_id,
                error_code="meta_callback_rejected",
                status_code=400,
            )
        try:
            scope, context = _meta_context(
                raw_session=session,
                requested_brand_id=None,
            )
            result = meta_activation.complete(query=dict(pairs), context=context)
        except (HTTPException, MetaActivationError) as exc:
            error_code = (
                "meta_self_service_authority_denied"
                if isinstance(exc, HTTPException)
                else _meta_error_code(exc)
            )
            return _meta_callback_page(
                brand_id=brand_id,
                error_code=error_code,
                status_code=400,
            )
        return _meta_callback_page(
            brand_id=scope.workspace.scope.requested_brand_id,
            connection_id=result.connection_id,
            facebook_count=result.facebook_count,
            instagram_count=result.instagram_count,
        )

    @router.get("/api/settings/tiktok/connection", response_model=TikTokConnectionResponse)
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
                capabilities.get(PlatformId.TIKTOK, capability) for capability in CapabilityId
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
                else "oauth_start_disabled_by_runtime_policy"
            ),
            checked_at=current,
        )

    @router.get(
        "/api/integrations/tiktok/self-service/readiness",
        response_model=TikTokSelfServiceReadinessResponse,
    )
    @mark_boundary(Boundary.QUERY)
    async def tiktok_self_service_readiness(
        response: Response,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> TikTokSelfServiceReadinessResponse:
        scope, context = _self_service_context(
            raw_session=session,
            requested_brand_id=brand_id,
        )
        assert reporting_store is not None
        accounts = tuple(
            account
            for account in reporting_store.list_accounts(brand_ids=(brand_id,))
            if account.platform is PlatformId.TIKTOK
        )
        rows = tuple(
            row
            for row in reporting_store.list_connections(brand_ids=(brand_id,))
            if row.platform is PlatformId.TIKTOK
        )
        connection_state = rows[-1].state if rows else "disconnected"
        if connection_state not in TIKTOK_CONNECTION_STATES:
            connection_state = "error"
        start_available = activation is not None and activation.ready_for_start(
            context,
            require_gate_context=False,
        )
        if start_available:
            reason = "self_service_available"
        elif activation is None:
            reason = "provider_activation_not_configured"
        elif not policy.writes_enabled:
            reason = "writes_disabled"
        else:
            reason = "provider_activation_unavailable"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return TikTokSelfServiceReadinessResponse(
            brand_id=scope.workspace.scope.requested_brand_id,
            can_manage=True,
            connection_state=connection_state,
            linked_account_count=len(accounts),
            oauth_start_available=start_available,
            reason=reason,
            runtime_mode=policy.runtime_mode,
            writes_enabled=policy.writes_enabled,
            checked_at=datetime.now(UTC),
        )

    @router.post(
        "/api/integrations/tiktok/oauth/start",
        response_model=TikTokSelfServiceStartResponse,
    )
    @mark_boundary(Boundary.COMMAND)
    async def tiktok_self_service_start(
        request: Request,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> TikTokSelfServiceStartResponse:
        _same_origin(request)
        if activation is None:
            raise HTTPException(503, "tiktok_self_service_unavailable")
        _, context = _self_service_context(
            raw_session=session,
            requested_brand_id=brand_id,
        )
        try:
            started = activation.start(context, require_gate_context=False)
        except TikTokActivationError as exc:
            _raise_self_service_activation_error(exc)
        return TikTokSelfServiceStartResponse(
            authorization_url=started.authorization_url,
            expires_at=started.expires_at,
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

    @router.get(
        "/api/social/tiktok/oauth/callback",
        status_code=303,
        response_model=None,
    )
    @mark_boundary(Boundary.PROTOCOL_COMMAND)
    async def tiktok_activation_callback(
        request: Request,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> Response:
        if activation is None:
            raise HTTPException(503, "owner_activation_unavailable")
        pairs = list(request.query_params.multi_items())
        # Login Kit returns `code`, the scopes it granted, and `state`. Insisting
        # on exactly two parameters rejected every authorization on arrival.
        if len(pairs) != len(CALLBACK_FIELDS) or {key for key, _ in pairs} != set(
            CALLBACK_FIELDS
        ):
            raise HTTPException(400, "activation_callback_rejected")
        payload = (
            resolve_session(session, authority_store)
            if session and authority_store is not None
            else None
        )
        if payload and payload.get("launch_target") == TIKTOK_OWNER_LAUNCH_TARGET:
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

        try:
            scope, context = _self_service_context(
                raw_session=session,
                requested_brand_id=None,
            )
            result = activation.complete(
                query=dict(pairs),
                context=context,
                require_gate_context=False,
            )
            if result.state != "pending_verification":
                raise TikTokActivationError("activation_completion_failed")
        except TikTokActivationError as exc:
            return _self_service_callback_page(
                brand_id=str(payload.get("brand_id") or "") if payload else "",
                error_code=_self_service_error_code(exc),
                status_code=400,
            )
        return _self_service_callback_page(
            brand_id=scope.workspace.scope.requested_brand_id,
            connection_id=result.connection_id,
            link_id=result.link_id,
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
        raise HTTPException(503, "connection_mutation_not_implemented")

    return router


def _same_origin(request: Request) -> None:
    if request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "origin_invalid")


def _raise_meta_activation_error(exc: MetaActivationError) -> None:
    reason = _meta_error_code(exc)
    if reason == "meta_self_service_unavailable":
        raise HTTPException(503, reason) from exc
    if reason == "meta_self_service_authority_denied":
        raise HTTPException(403, reason) from exc
    if reason in {"meta_callback_rejected", "meta_link_selection_invalid"}:
        raise HTTPException(400, reason) from exc
    if reason in {"meta_scope_denied", "meta_accounts_unavailable"}:
        raise HTTPException(409, reason) from exc
    raise HTTPException(503, reason) from exc


def _meta_error_code(exc: MetaActivationError) -> str:
    reason = str(exc)
    if reason == "meta_activation_disabled":
        return "meta_self_service_unavailable"
    if reason == "meta_activation_authority_denied":
        return "meta_self_service_authority_denied"
    if reason == "meta_activation_callback_rejected":
        return "meta_callback_rejected"
    if reason == "meta_activation_scope_denied":
        return "meta_scope_denied"
    if reason == "meta_activation_accounts_unavailable":
        return "meta_accounts_unavailable"
    if reason in {"meta_link_selection_invalid", "meta_discovery_selection_invalid"}:
        return "meta_link_selection_invalid"
    return "meta_connection_failed"


def _meta_callback_page(
    *,
    brand_id: str,
    connection_id: int | None = None,
    facebook_count: int = 0,
    instagram_count: int = 0,
    error_code: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    callback_status = "error" if error_code else "success"
    payload = json.dumps(
        {
            "type": "social-media:meta-oauth",
            "status": callback_status,
            "brandId": brand_id,
            "connectionId": connection_id,
            "facebookCount": facebook_count,
            "instagramCount": instagram_count,
            "connectionState": "pending_verification" if not error_code else "error",
            "errorCode": error_code,
        },
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    fallback_path = f"/integrations?meta_oauth={callback_status}" + (
        f"&error={error_code}" if error_code else ""
    )
    fallback_json = json.dumps(fallback_path)
    title = "Meta accounts discovered" if not error_code else "Meta connection failed"
    badge_background = "#ecfdf5" if not error_code else "#fff1f2"
    badge_color = "#047857" if not error_code else "#be123c"
    message = (
        "Facebook Pages and Instagram Business accounts were discovered. "
        "Return to Integrations to choose the accounts for this Brand."
        if not error_code
        else "The Meta authorization could not be completed. Return to Integrations and try again."
    )
    content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{
        margin: 0; background: #f8fafc; color: #0f172a;
        font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      }}
      main {{
        max-width: 34rem; margin: 12vh auto; padding: 2rem; border: 1px solid #e2e8f0;
        border-radius: 1rem; background: white; box-shadow: 0 18px 45px rgba(15, 23, 42, .12);
      }}
      span {{
        display: inline-flex; padding: .35rem .7rem; border-radius: 999px;
        background: {badge_background}; color: {badge_color}; font-size: .75rem; font-weight: 800;
      }}
      h1 {{ margin: 1rem 0 .5rem; font-size: 1.4rem; }}
      p {{ margin: 0; color: #475569; line-height: 1.6; }}
      a {{ display: inline-flex; margin-top: 1.25rem; color: #4338ca; font-weight: 800; }}
    </style>
  </head>
  <body>
    <main>
      <span>{callback_status}</span><h1>{title}</h1><p>{message}</p>
      <a href="{fallback_path}">Return to Integrations</a>
    </main>
    <script>
      (() => {{
        const payload = {payload};
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, window.location.origin);
          window.setTimeout(() => window.close(), 350);
          return;
        }}
        window.setTimeout(() => window.location.replace({fallback_json}), 900);
      }})();
    </script>
  </body>
</html>"""
    return HTMLResponse(
        content=content,
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


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


def _raise_self_service_activation_error(exc: TikTokActivationError) -> None:
    reason = _self_service_error_code(exc)
    if reason == "tiktok_self_service_unavailable":
        raise HTTPException(503, reason) from exc
    if reason in {
        "tiktok_self_service_authority_denied",
        "tiktok_self_service_scope_denied",
    }:
        raise HTTPException(403, reason) from exc
    if reason == "tiktok_self_service_callback_rejected":
        raise HTTPException(400, reason) from exc
    raise HTTPException(503, reason) from exc


def _self_service_error_code(exc: TikTokActivationError) -> str:
    reason = str(exc)
    if reason == "activation_disabled":
        return "tiktok_self_service_unavailable"
    if reason == "activation_authority_denied":
        return "tiktok_self_service_authority_denied"
    if reason in {"activation_scope_denied", "activation_scope_mismatch"}:
        return "tiktok_self_service_scope_denied"
    if reason == "activation_callback_rejected":
        return "tiktok_self_service_callback_rejected"
    return "tiktok_self_service_completion_failed"


def _self_service_callback_page(
    *,
    brand_id: str,
    connection_id: int | None = None,
    link_id: int | None = None,
    error_code: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    callback_status = "error" if error_code else "success"
    payload = json.dumps(
        {
            "type": "social-media:tiktok-oauth",
            "status": callback_status,
            "brandId": brand_id,
            "connectionId": connection_id,
            "linkId": link_id,
            "connectionState": "pending_verification" if not error_code else "error",
            "errorCode": error_code,
        },
        separators=(",", ":"),
    ).replace("<", "\\u003c")
    fallback_path = f"/integrations?tiktok_oauth={callback_status}" + (
        f"&error={error_code}" if error_code else ""
    )
    fallback_json = json.dumps(fallback_path)
    title = "TikTok connection received" if not error_code else "TikTok connection failed"
    badge_background = "#ecfdf5" if not error_code else "#fff1f2"
    badge_color = "#047857" if not error_code else "#be123c"
    message = (
        "The authorized TikTok account is pending verification. You can return to Integrations."
        if not error_code
        else "The authorization could not be completed. Return to Integrations and try again."
    )
    content = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <style>
      body {{
        margin: 0; background: #f8fafc; color: #0f172a;
        font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      }}
      main {{
        max-width: 34rem; margin: 12vh auto; padding: 2rem; border: 1px solid #e2e8f0;
        border-radius: 1rem; background: white; box-shadow: 0 18px 45px rgba(15, 23, 42, .12);
      }}
      span {{
        display: inline-flex; padding: .35rem .7rem; border-radius: 999px;
        background: {badge_background}; color: {badge_color}; font-size: .75rem; font-weight: 800;
      }}
      h1 {{ margin: 1rem 0 .5rem; font-size: 1.4rem; }}
      p {{ margin: 0; color: #475569; line-height: 1.6; }}
      a {{ display: inline-flex; margin-top: 1.25rem; color: #4338ca; font-weight: 800; }}
    </style>
  </head>
  <body>
    <main>
      <span>{callback_status}</span><h1>{title}</h1><p>{message}</p>
      <a href="{fallback_path}">Return to Integrations</a>
    </main>
    <script>
      (() => {{
        const payload = {payload};
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, window.location.origin);
          window.setTimeout(() => window.close(), 350);
          return;
        }}
        window.setTimeout(() => window.location.replace({fallback_json}), 900);
      }})();
    </script>
  </body>
</html>"""
    return HTMLResponse(
        content=content,
        status_code=status_code,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


__all__ = ["create_settings_router"]

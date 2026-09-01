"""Self-service HTTP boundary shared by X, LinkedIn, and YouTube OAuth."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse

from app.api.auth import COOKIE_NAME
from app.application.ports import (
    OAUTH_CHANNEL_PLATFORMS,
    AuthorityStore,
    OAuthChannelError,
    OAuthLinkSelection,
    ReportingStore,
)
from app.application.services.oauth_channel_activation import (
    OAuthChannelActivationCoordinator,
)
from app.application.services.sso import session_can_access_settings
from app.core import Boundary, WritePolicy, mark_boundary
from app.domain.platforms import PlatformId

from .callback import oauth_channel_callback_page
from .context import resolve_oauth_channel_context
from .contracts import (
    OAuthChannelAccountItem,
    OAuthChannelLinkPayload,
    OAuthChannelLinkResponse,
    OAuthChannelReadinessResponse,
    OAuthChannelStartResponse,
    OAuthChannelUnlinkResponse,
)


def create_oauth_channel_router(
    *,
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    policy: WritePolicy,
    activations: Mapping[PlatformId, OAuthChannelActivationCoordinator],
    platforms: tuple[PlatformId, ...] = (PlatformId.YOUTUBE,),
) -> APIRouter:
    router = APIRouter()
    registered = set(platforms)
    if (
        not platforms
        or len(registered) != len(platforms)
        or not registered.issubset(OAUTH_CHANNEL_PLATFORMS)
        or not set(activations).issubset(registered)
    ):
        raise ValueError("oauth_channel_router_platform_invalid")
    for platform in platforms:
        router.include_router(
            _platform_router(
                platform=platform,
                authority_store=authority_store,
                reporting_store=reporting_store,
                policy=policy,
                activation=activations.get(platform),
            )
        )
    return router


def _platform_router(
    *,
    platform: PlatformId,
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    policy: WritePolicy,
    activation: OAuthChannelActivationCoordinator | None,
) -> APIRouter:
    router = APIRouter()
    integration_path = f"/api/integrations/{platform.value}"

    @router.get(
        f"{integration_path}/self-service/readiness",
        response_model=OAuthChannelReadinessResponse,
    )
    @mark_boundary(Boundary.QUERY)
    async def readiness(
        response: Response,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> OAuthChannelReadinessResponse:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        scope, context = resolve_oauth_channel_context(
            authority_store=authority_store,
            raw_session=session,
            requested_brand_id=brand_id,
            platform=platform,
        )
        can_manage = session_can_access_settings(scope.session)
        accounts = tuple(
            account
            for account in reporting_store.list_accounts(brand_ids=(brand_id,))
            if account.platform is platform
            and account.link_status in {"active", "connected"}
        )
        connections = tuple(
            connection
            for connection in reporting_store.list_connections(brand_ids=(brand_id,))
            if connection.platform is platform
        )
        discoveries = ()
        if activation is not None and can_manage:
            try:
                discoveries = activation.list_discoveries(context)
            except OAuthChannelError as exc:
                _raise_oauth_channel_error(exc)
        available = tuple(item for item in discoveries if item.status == "available")
        linked = tuple(item for item in discoveries if item.status == "linked")
        connection_state = connections[-1].state if connections else "disconnected"
        if available:
            connection_state = "pending_verification"
        start_available = activation is not None and activation.ready_for_start(context)
        reason = _readiness_reason(
            activation=activation,
            policy=policy,
            start_available=start_available,
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return OAuthChannelReadinessResponse(
            brand_id=scope.workspace.scope.requested_brand_id,
            platform=platform,
            can_manage=can_manage,
            connection_state=connection_state,
            linked_account_count=len(accounts) if can_manage else 0,
            linked_accounts=(
                tuple(
                    OAuthChannelAccountItem(
                        connection_id=item.connection_id,
                        external_id=item.external_id,
                        display_name=item.display_name,
                        state=item.status,
                    )
                    for item in linked
                )
                if can_manage
                else ()
            ),
            available_accounts=(
                tuple(
                    OAuthChannelAccountItem(
                        connection_id=item.connection_id,
                        external_id=item.external_id,
                        display_name=item.display_name,
                        state=item.status,
                    )
                    for item in available
                )
                if can_manage
                else ()
            ),
            oauth_start_available=start_available,
            reason=reason,
            runtime_mode=policy.runtime_mode,
            writes_enabled=policy.writes_enabled,
            checked_at=datetime.now(UTC),
        )

    @router.post(
        f"{integration_path}/oauth/start",
        response_model=OAuthChannelStartResponse,
    )
    @mark_boundary(Boundary.COMMAND)
    async def start(
        request: Request,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> OAuthChannelStartResponse:
        _same_origin(request)
        if activation is None:
            raise HTTPException(503, "oauth_channel_not_configured")
        _, context = resolve_oauth_channel_context(
            authority_store=authority_store,
            raw_session=session,
            requested_brand_id=brand_id,
            platform=platform,
        )
        try:
            result = activation.start(context)
        except OAuthChannelError as exc:
            _raise_oauth_channel_error(exc)
        return OAuthChannelStartResponse(
            authorization_url=result.authorization_url,
            expires_at=result.expires_at,
        )

    @router.post(
        f"{integration_path}/accounts/link",
        response_model=OAuthChannelLinkResponse,
    )
    @mark_boundary(Boundary.COMMAND)
    async def link(
        payload: OAuthChannelLinkPayload,
        request: Request,
        brand_id: str = Query(min_length=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> OAuthChannelLinkResponse:
        _same_origin(request)
        if activation is None:
            raise HTTPException(503, "oauth_channel_not_configured")
        scope, context = resolve_oauth_channel_context(
            authority_store=authority_store,
            raw_session=session,
            requested_brand_id=brand_id,
            platform=platform,
        )
        if not session_can_access_settings(scope.session):
            raise HTTPException(403, "settings_capability_required")
        try:
            result = activation.link_accounts(
                context=context,
                connection_id=payload.connection_id,
                selections=tuple(
                    OAuthLinkSelection(external_id=value)
                    for value in payload.external_ids
                ),
            )
        except OAuthChannelError as exc:
            _raise_oauth_channel_error(exc)
        return OAuthChannelLinkResponse(
            connection_id=result.connection_id,
            linked_count=result.linked_count,
            connection_state=result.state,
        )

    @router.delete(
        f"{integration_path}/accounts/unlink",
        response_model=OAuthChannelUnlinkResponse,
    )
    @mark_boundary(Boundary.COMMAND)
    async def unlink(
        request: Request,
        brand_id: str = Query(min_length=1),
        external_id: str = Query(min_length=1, max_length=255),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> OAuthChannelUnlinkResponse:
        _same_origin(request)
        if activation is None:
            raise HTTPException(503, "oauth_channel_not_configured")
        scope, context = resolve_oauth_channel_context(
            authority_store=authority_store,
            raw_session=session,
            requested_brand_id=brand_id,
            platform=platform,
        )
        if not session_can_access_settings(scope.session):
            raise HTTPException(403, "settings_capability_required")
        try:
            result = activation.unlink(context=context, external_id=external_id)
        except OAuthChannelError as exc:
            _raise_oauth_channel_error(exc)
        return OAuthChannelUnlinkResponse(
            brand_id=scope.workspace.scope.requested_brand_id,
            platform=platform,
            external_id=external_id,
            connection_state=result.state,
        )

    @router.get(
        f"/api/social/{platform.value}/oauth/callback",
        response_model=None,
    )
    @mark_boundary(Boundary.PROTOCOL_COMMAND)
    async def callback(
        request: Request,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> HTMLResponse:
        if activation is None:
            return oauth_channel_callback_page(
                platform=platform,
                brand_id="",
                error_code="oauth_channel_not_configured",
                status_code=503,
            )
        pairs = list(request.query_params.multi_items())
        fallback_brand_id = ""
        if any(key in {"error", "error_description", "error_uri"} for key, _ in pairs):
            return oauth_channel_callback_page(
                platform=platform,
                brand_id=fallback_brand_id,
                error_code="oauth_authorization_declined",
                status_code=400,
            )
        if len({key for key, _ in pairs}) != len(pairs):
            return oauth_channel_callback_page(
                platform=platform,
                brand_id=fallback_brand_id,
                error_code="oauth_activation_callback_rejected",
                status_code=400,
            )
        query = dict(pairs)
        try:
            fallback_brand_id = str(activation.callback_brand_id(query=query))
            scope, context = resolve_oauth_channel_context(
                authority_store=authority_store,
                raw_session=session,
                requested_brand_id=fallback_brand_id,
                platform=platform,
            )
            result = activation.complete(query=query, context=context)
        except OAuthChannelError as exc:
            return oauth_channel_callback_page(
                platform=platform,
                brand_id=fallback_brand_id,
                error_code=_oauth_channel_error_code(exc),
                status_code=400,
            )
        except HTTPException as exc:
            return oauth_channel_callback_page(
                platform=platform,
                brand_id=fallback_brand_id,
                error_code="oauth_activation_authority_denied",
                status_code=exc.status_code,
            )
        return oauth_channel_callback_page(
            platform=platform,
            brand_id=scope.workspace.scope.requested_brand_id,
            connection_id=result.connection_id,
            discovered_count=result.discovered_count,
        )

    return router


def _readiness_reason(
    *,
    activation: OAuthChannelActivationCoordinator | None,
    policy: WritePolicy,
    start_available: bool,
) -> str:
    if start_available:
        return "self_service_available"
    if activation is None:
        return "provider_activation_not_configured"
    if not policy.writes_enabled:
        return "writes_disabled"
    return "provider_activation_unavailable"


def _same_origin(request: Request) -> None:
    if request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "origin_invalid")


def _raise_oauth_channel_error(exc: OAuthChannelError) -> None:
    reason = _oauth_channel_error_code(exc)
    if reason == "oauth_channel_not_configured":
        raise HTTPException(503, reason) from exc
    if reason == "oauth_activation_authority_denied":
        raise HTTPException(403, reason) from exc
    if reason in {
        "oauth_activation_callback_rejected",
        "oauth_link_selection_invalid",
    }:
        raise HTTPException(400, reason) from exc
    if reason == "oauth_link_not_found":
        raise HTTPException(404, reason) from exc
    if reason == "oauth_activation_grant_denied":
        raise HTTPException(409, reason) from exc
    raise HTTPException(503, reason) from exc


def _oauth_channel_error_code(exc: OAuthChannelError) -> str:
    reason = str(exc)
    if reason == "oauth_activation_disabled":
        return "oauth_channel_not_configured"
    allowed = {
        "oauth_activation_authority_denied",
        "oauth_activation_callback_rejected",
        "oauth_activation_grant_denied",
        "oauth_link_not_found",
        "oauth_link_selection_invalid",
    }
    return reason if reason in allowed else "oauth_channel_operation_failed"


__all__ = ["create_oauth_channel_router"]

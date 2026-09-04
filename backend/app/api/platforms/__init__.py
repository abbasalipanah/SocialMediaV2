"""Canonical social-account query routes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Query

from app.api.auth import COOKIE_NAME
from app.api.contracts import PlatformAccountsResponse
from app.api.scope import resolve_request_scope
from app.application.ports import AuthorityStore, ReportingStore
from app.core import Boundary, mark_boundary
from app.domain.platforms import PlatformId
from app.domain.platforms.catalog import PLATFORM_CATALOG


def create_platform_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
) -> APIRouter:
    router = APIRouter()

    def _accounts(
        *,
        platform: PlatformId,
        raw_session: str | None,
        brand_id: str | None,
        rollup: bool,
    ) -> PlatformAccountsResponse:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        scope = resolve_request_scope(
            store=authority_store,
            raw_session=raw_session,
            selected_brand_id=brand_id,
            rollup=rollup,
        )
        accounts = reporting_store.list_accounts(
            brand_ids=scope.workspace.scope.resolved_brand_ids,
            platform=platform,
        )
        return PlatformAccountsResponse(
            meta=scope.workspace.scope,
            platform=platform,
            accounts=accounts,
        )

    def _register(path: str, platform: PlatformId) -> None:
        async def endpoint(
            brand_id: str | None = Query(default=None),
            rollup: bool = Query(default=False),
            session: str | None = Cookie(default=None, alias=COOKIE_NAME),
        ) -> PlatformAccountsResponse:
            return _accounts(
                platform=platform,
                raw_session=session,
                brand_id=brand_id,
                rollup=rollup,
            )

        mark_boundary(Boundary.QUERY)(endpoint)
        router.add_api_route(
            path, endpoint, methods=["GET"], response_model=PlatformAccountsResponse
        )

    for definition in PLATFORM_CATALOG:
        _register(
            f"/api/platforms/{definition.route}/accounts",
            definition.platform,
        )
    return router


__all__ = ["create_platform_router"]

"""Authorized Overview and platform dashboard routes."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query

from app.api.auth import COOKIE_NAME
from app.api.scope import resolve_request_scope
from app.application.ports import AuthorityStore, ReportingStore
from app.application.queries import (
    DashboardQuery,
    build_overview_dashboard,
    build_platform_dashboard,
    resolve_reporting_range,
)
from app.core import Boundary, mark_boundary
from app.domain.metrics import MetricCatalog
from app.domain.platforms import PlatformId
from app.domain.platforms.catalog import PLATFORM_CATALOG
from app.domain.reporting import OverviewDashboard, PlatformDashboard

ALLOWED_TABS = {
    "account",
    "overview",
    "cover",
    "page",
    "profile",
    "content",
    "videos",
    "stories",
    "audience",
}


def create_dashboard_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    metric_catalog: MetricCatalog,
) -> APIRouter:
    router = APIRouter()

    def _query(
        *,
        raw_session: str | None,
        brand_id: str | None,
        rollup: bool,
        range_key: str,
        start_on: date | None,
        end_on: date | None,
        account_id: int | None,
        content_type: str | None,
        tab: str | None,
        platform: PlatformId | None,
    ) -> DashboardQuery:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        scope = resolve_request_scope(
            store=authority_store,
            raw_session=raw_session,
            selected_brand_id=brand_id,
            rollup=rollup,
        )
        normalized_tab = tab.lower().strip() if tab else None
        if normalized_tab and normalized_tab not in ALLOWED_TABS:
            raise HTTPException(400, "dashboard_tab_unknown")
        if normalized_tab == "stories":
            if platform is not PlatformId.INSTAGRAM:
                raise HTTPException(400, "stories_platform_invalid")
            content_type = "story"
        try:
            date_range = resolve_reporting_range(
                range_key=range_key,
                start_on=start_on,
                end_on=end_on,
            )
            return DashboardQuery(
                requested_brand_id=scope.workspace.scope.requested_brand_id,
                resolved_brand_ids=scope.workspace.scope.resolved_brand_ids,
                rollup=scope.workspace.scope.rollup,
                date_range=date_range,
                account_id=account_id,
                content_type=content_type,
                excluded_content_types=(
                    ("story",)
                    if normalized_tab == "content" and platform is PlatformId.INSTAGRAM
                    else ()
                ),
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    def _platform(
        *,
        platform: PlatformId,
        raw_session: str | None,
        brand_id: str | None,
        rollup: bool,
        range_key: str,
        start_on: date | None,
        end_on: date | None,
        account_id: int | None,
        content_type: str | None,
        tab: str | None,
    ) -> PlatformDashboard:
        query = _query(
            raw_session=raw_session,
            brand_id=brand_id,
            rollup=rollup,
            range_key=range_key,
            start_on=start_on,
            end_on=end_on,
            account_id=account_id,
            content_type=content_type,
            tab=tab,
            platform=platform,
        )
        assert reporting_store is not None
        try:
            return build_platform_dashboard(
                store=reporting_store,
                catalog=metric_catalog,
                platform=platform,
                query=query,
            )
        except ValueError as exc:
            status = 403 if str(exc) == "dashboard_account_scope_denied" else 400
            raise HTTPException(status, str(exc)) from exc

    @router.get("/api/dashboards/overview", response_model=OverviewDashboard)
    @mark_boundary(Boundary.QUERY)
    async def overview(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        range_key: str = Query(default="last_30_days", alias="range"),
        start_on: Annotated[date | None, Query(alias="start_date")] = None,
        end_on: Annotated[date | None, Query(alias="end_date")] = None,
        content_type: str | None = Query(default=None),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> OverviewDashboard:
        query = _query(
            raw_session=session,
            brand_id=brand_id,
            rollup=rollup,
            range_key=range_key,
            start_on=start_on,
            end_on=end_on,
            account_id=None,
            content_type=content_type,
            tab=None,
            platform=None,
        )
        assert reporting_store is not None
        return build_overview_dashboard(
            store=reporting_store,
            catalog=metric_catalog,
            query=query,
        )

    def _register_platform(path: str, platform: PlatformId) -> None:
        async def endpoint(
            brand_id: str | None = Query(default=None),
            rollup: bool = Query(default=False),
            range_key: str = Query(default="last_30_days", alias="range"),
            start_on: Annotated[date | None, Query(alias="start_date")] = None,
            end_on: Annotated[date | None, Query(alias="end_date")] = None,
            account_id: int | None = Query(default=None, ge=1),
            content_type: str | None = Query(default=None),
            tab: str | None = Query(default=None),
            session: str | None = Cookie(default=None, alias=COOKIE_NAME),
        ) -> PlatformDashboard:
            return _platform(
                platform=platform,
                raw_session=session,
                brand_id=brand_id,
                rollup=rollup,
                range_key=range_key,
                start_on=start_on,
                end_on=end_on,
                account_id=account_id,
                content_type=content_type,
                tab=tab,
            )

        mark_boundary(Boundary.QUERY)(endpoint)
        router.add_api_route(
            path, endpoint, methods=["GET"], response_model=PlatformDashboard
        )

    for definition in PLATFORM_CATALOG:
        _register_platform(
            f"/api/dashboards/{definition.route}",
            definition.platform,
        )
    return router


__all__ = ["create_dashboard_router"]

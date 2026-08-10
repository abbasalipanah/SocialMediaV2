"""Session-bound queue API for transient XLSX dashboard reports."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response

from app.api.auth import COOKIE_NAME
from app.api.contracts import ReportJobResponse
from app.api.scope import resolve_request_scope
from app.application.ports import AuthorityStore, ReportingStore
from app.application.queries import (
    DashboardQuery,
    build_overview_dashboard,
    build_platform_dashboard,
    resolve_reporting_range,
)
from app.application.services.report_exports import (
    ReportJobError,
    ReportJobManager,
    ReportJobView,
)
from app.core import Boundary, mark_boundary
from app.core.security import sha256_text
from app.domain.metrics import MetricCatalog
from app.domain.platforms import PlatformId
from app.infrastructure.reports import (
    ReportContext,
    build_overview_xlsx,
    build_platform_xlsx,
)

ReportSurface = Literal["overview", "facebook", "instagram", "tiktok"]

PLATFORM_TABS = {
    PlatformId.FACEBOOK: frozenset({"cover", "page", "content", "audience"}),
    PlatformId.INSTAGRAM: frozenset({"cover", "page", "content", "stories", "audience"}),
    PlatformId.TIKTOK: frozenset({"cover", "account", "content", "audience"}),
}


def create_reports_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    metric_catalog: MetricCatalog,
    jobs: ReportJobManager,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/reports/xlsx", response_model=ReportJobResponse, status_code=202)
    @mark_boundary(Boundary.COMMAND)
    async def create_report(
        request: Request,
        surface: Annotated[ReportSurface, Query()],
        tab: str = Query(default="cover", min_length=1, max_length=20),
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        range_key: str = Query(default="last_30_days", alias="range"),
        start_on: Annotated[date | None, Query(alias="start_date")] = None,
        end_on: Annotated[date | None, Query(alias="end_date")] = None,
        account_id: int | None = Query(default=None, ge=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> ReportJobResponse:
        _same_origin(request)
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        scope = resolve_request_scope(
            store=authority_store,
            raw_session=session,
            selected_brand_id=brand_id,
            rollup=rollup,
        )
        normalized_tab = tab.lower().strip()
        if surface == "overview":
            if normalized_tab not in {"overview", "cover"} or account_id is not None:
                raise HTTPException(400, "report_surface_invalid")
            normalized_tab = "overview"
            platform = None
        else:
            platform = PlatformId(surface)
            if normalized_tab not in PLATFORM_TABS[platform]:
                raise HTTPException(400, "report_tab_invalid")
        try:
            date_range = resolve_reporting_range(
                range_key=range_key,
                start_on=start_on,
                end_on=end_on,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        dashboard_query = DashboardQuery(
            requested_brand_id=scope.workspace.scope.requested_brand_id,
            resolved_brand_ids=scope.workspace.scope.resolved_brand_ids,
            rollup=scope.workspace.scope.rollup,
            date_range=date_range,
            account_id=account_id,
            content_type="story" if normalized_tab == "stories" else None,
            excluded_content_types=(
                ("story",)
                if normalized_tab == "content" and platform is PlatformId.INSTAGRAM
                else ()
            ),
        )
        brand = next(
            (
                item
                for item in scope.workspace.brands
                if item.brand_id == scope.workspace.scope.requested_brand_id
            ),
            None,
        )
        brand_name = (
            brand.name if brand and brand.name else f"Brand {dashboard_query.requested_brand_id}"
        )
        accounts = reporting_store.list_accounts(
            brand_ids=dashboard_query.resolved_brand_ids,
            platform=platform,
        )
        if account_id is not None:
            accounts = tuple(item for item in accounts if item.account_id == account_id)
        if account_id is not None and not accounts:
            raise HTTPException(403, "dashboard_account_scope_denied")
        context = ReportContext(
            brand_name=brand_name,
            account_name=_account_name(accounts),
            surface=surface,
            tab=normalized_tab,
            rollup=dashboard_query.rollup,
        )

        def render(progress):
            progress(6, "Reading canonical dashboard projection")
            if platform is None:
                dashboard = build_overview_dashboard(
                    store=reporting_store,
                    catalog=metric_catalog,
                    query=dashboard_query,
                )
                return build_overview_xlsx(
                    dashboard=dashboard,
                    context=context,
                    progress=progress,
                )
            dashboard = build_platform_dashboard(
                store=reporting_store,
                catalog=metric_catalog,
                platform=platform,
                query=dashboard_query,
            )
            return build_platform_xlsx(
                dashboard=dashboard,
                context=context,
                progress=progress,
            )

        try:
            view = jobs.enqueue(
                owner_session_hash=sha256_text(session or ""),
                brand_id=dashboard_query.requested_brand_id,
                rollup=dashboard_query.rollup,
                task=render,
            )
        except ReportJobError as exc:
            status = 429 if exc.code in {"report_queue_full", "report_owner_job_limit"} else 503
            raise HTTPException(status, exc.code) from exc
        return _response(view)

    @router.get("/api/reports/xlsx/{job_id}", response_model=ReportJobResponse)
    @mark_boundary(Boundary.QUERY)
    async def report_status(
        job_id: str,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> ReportJobResponse:
        owner_hash = sha256_text(session or "")
        _revalidate_job_scope(jobs, job_id, owner_hash, authority_store, session)
        try:
            return _response(jobs.status(job_id=job_id, owner_session_hash=owner_hash))
        except ReportJobError as exc:
            raise HTTPException(404, exc.code) from exc

    @router.post("/api/reports/xlsx/{job_id}/download")
    @mark_boundary(Boundary.COMMAND)
    async def download_report(
        request: Request,
        job_id: str,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> Response:
        _same_origin(request)
        owner_hash = sha256_text(session or "")
        _revalidate_job_scope(jobs, job_id, owner_hash, authority_store, session)
        try:
            artifact = jobs.consume(job_id=job_id, owner_session_hash=owner_hash)
        except ReportJobError as exc:
            status = 409 if exc.code == "report_job_not_ready" else 404
            raise HTTPException(status, exc.code) from exc
        return Response(
            artifact.content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{artifact.filename}"',
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router


def _revalidate_job_scope(
    jobs: ReportJobManager,
    job_id: str,
    owner_hash: str,
    authority_store: AuthorityStore | None,
    session: str | None,
) -> None:
    try:
        brand_id, rollup = jobs.scope(job_id=job_id, owner_session_hash=owner_hash)
    except ReportJobError as exc:
        raise HTTPException(404, exc.code) from exc
    resolve_request_scope(
        store=authority_store,
        raw_session=session,
        selected_brand_id=brand_id,
        rollup=rollup,
    )


def _account_name(accounts) -> str:
    names = tuple(dict.fromkeys(item.display_name for item in accounts if item.display_name))
    if not names:
        return "No connected account"
    if len(names) <= 3:
        return ", ".join(names)
    return f"{len(names)} connected accounts"


def _response(view: ReportJobView) -> ReportJobResponse:
    return ReportJobResponse(**view.__dict__)


def _same_origin(request: Request) -> None:
    if request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "origin_invalid")


__all__ = ["create_reports_router"]

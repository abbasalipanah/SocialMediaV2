"""Stored AI insight query route; generation is not triggered by GET."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request

from app.api.auth import COOKIE_NAME
from app.api.contracts import AiSummaryLimitResponse, InsightsResponse
from app.api.scope import resolve_request_scope
from app.application.ports import (
    AiSummaryError,
    AiSummaryService,
    AuthorityStore,
    ReportingStore,
)
from app.application.ports.reporting import ReportingInsight
from app.application.services.sso import session_can_generate_ai_summary
from app.core import Boundary, mark_boundary


def create_insights_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    ai_summary: AiSummaryService | None = None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/insights", response_model=InsightsResponse)
    @mark_boundary(Boundary.QUERY)
    async def insights(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        start_on: Annotated[date | None, Query(alias="start_date")] = None,
        end_on: Annotated[date | None, Query(alias="end_date")] = None,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> InsightsResponse:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        scope = resolve_request_scope(
            store=authority_store,
            raw_session=session,
            selected_brand_id=brand_id,
            rollup=rollup,
        )
        try:
            rows = reporting_store.list_insights(
                brand_ids=scope.workspace.scope.resolved_brand_ids,
                start_on=start_on,
                end_on=end_on,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return InsightsResponse(meta=scope.workspace.scope, items=rows)

    def _generation_scope(
        *,
        raw_session: str | None,
        brand_id: str | None,
        rollup: bool,
    ):
        if rollup:
            raise HTTPException(403, "ai_summary_rollup_denied")
        scope = resolve_request_scope(
            store=authority_store,
            raw_session=raw_session,
            selected_brand_id=brand_id,
            rollup=False,
        )
        if not session_can_generate_ai_summary(scope.session):
            raise HTTPException(403, "ai_summary_operator_required")
        selected = next(
            (
                item
                for item in scope.workspace.brands
                if item.brand_id == scope.workspace.scope.requested_brand_id
            ),
            None,
        )
        if selected is None or selected.role != "viewer" or selected.access_mode != "read":
            raise HTTPException(403, "ai_summary_brand_scope_denied")
        return scope

    @router.get("/api/insights/limit", response_model=AiSummaryLimitResponse)
    @mark_boundary(Boundary.QUERY)
    async def insight_limit(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> AiSummaryLimitResponse:
        scope = _generation_scope(
            raw_session=session,
            brand_id=brand_id,
            rollup=rollup,
        )
        if ai_summary is None:
            raise HTTPException(503, "ai_summary_store_unavailable")
        return AiSummaryLimitResponse.from_status(
            ai_summary.limit_status(brand_id=scope.workspace.scope.requested_brand_id)
        )

    @router.post("/api/insights/generate", response_model=ReportingInsight)
    @mark_boundary(Boundary.COMMAND)
    async def generate_insight(
        request: Request,
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        range_key: str = Query(default="last_30_days", alias="range"),
        start_on: Annotated[date | None, Query(alias="start_date")] = None,
        end_on: Annotated[date | None, Query(alias="end_date")] = None,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> ReportingInsight:
        _same_origin(request)
        scope = _generation_scope(
            raw_session=session,
            brand_id=brand_id,
            rollup=rollup,
        )
        if ai_summary is None:
            raise HTTPException(503, "ai_summary_store_unavailable")
        try:
            return await ai_summary.generate(
                brand_id=scope.workspace.scope.requested_brand_id,
                user_sub=str(scope.session.get("user_id") or ""),
                range_key=range_key,
                start_on=start_on,
                end_on=end_on,
            )
        except AiSummaryError as exc:
            if exc.code == "weekly_limit_reached":
                raise HTTPException(429, exc.code) from exc
            if exc.code == "generation_in_progress":
                raise HTTPException(409, exc.code) from exc
            if exc.code in {
                "reporting_range_incomplete",
                "reporting_range_invalid",
                "reporting_range_unknown",
            }:
                raise HTTPException(400, exc.code) from exc
            if exc.code == "ai_summary_data_unavailable":
                raise HTTPException(409, exc.code) from exc
            if exc.code in {"provider_not_configured", "ai_summary_store_unavailable"}:
                raise HTTPException(503, exc.code) from exc
            raise HTTPException(502, exc.code) from exc

    return router


def _same_origin(request: Request) -> None:
    if request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
        raise HTTPException(403, "origin_invalid")


__all__ = ["create_insights_router"]

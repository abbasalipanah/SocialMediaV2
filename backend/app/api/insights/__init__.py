"""Stored AI insight query route; generation is not triggered by GET."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query

from app.api.auth import COOKIE_NAME
from app.api.contracts import InsightsResponse
from app.api.scope import resolve_request_scope
from app.application.ports import AuthorityStore, ReportingStore
from app.core import Boundary, mark_boundary


def create_insights_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
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

    return router


__all__ = ["create_insights_router"]

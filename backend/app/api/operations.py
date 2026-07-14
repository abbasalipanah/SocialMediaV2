"""Dormant operation command surface."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Query, Request

from app.api.auth import COOKIE_NAME
from app.api.scope import resolve_request_scope
from app.application.ports import AuthorityStore
from app.core import Boundary, WritePolicy, mark_boundary
from app.domain.platforms import PlatformId


def create_operations_router(
    authority_store: AuthorityStore | None, policy: WritePolicy
) -> APIRouter:
    router = APIRouter()

    def _reject_unavailable(
        *,
        command: str,
        request: Request,
        raw_session: str | None,
        brand_id: str | None,
    ) -> None:
        if request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
            raise HTTPException(403, "origin_invalid")
        resolve_request_scope(
            store=authority_store,
            raw_session=raw_session,
            selected_brand_id=brand_id,
            rollup=False,
            require_write=True,
        )
        try:
            policy.assert_allows_mutation(command)
        except PermissionError as exc:
            raise HTTPException(403, "writes_disabled") from exc
        raise HTTPException(503, "operation_unavailable_before_cutover")

    @router.post("/api/operations/sync", status_code=503)
    @mark_boundary(Boundary.COMMAND)
    async def sync(
        request: Request,
        platform: Annotated[PlatformId, Query()],
        account_id: Annotated[int, Query(ge=1)],
        brand_id: str | None = Query(default=None),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> None:
        del platform, account_id
        _reject_unavailable(
            command="manual_sync",
            request=request,
            raw_session=session,
            brand_id=brand_id,
        )

    @router.post("/api/operations/backfill", status_code=503)
    @mark_boundary(Boundary.COMMAND)
    async def backfill(
        request: Request,
        platform: Annotated[PlatformId, Query()],
        account_id: Annotated[int, Query(ge=1)],
        brand_id: str | None = Query(default=None),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> None:
        del platform, account_id
        _reject_unavailable(
            command="manual_backfill",
            request=request,
            raw_session=session,
            brand_id=brand_id,
        )

    return router


__all__ = ["create_operations_router"]

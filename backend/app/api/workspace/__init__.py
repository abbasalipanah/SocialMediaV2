"""Brand family workspace query routes."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Cookie, HTTPException, Query, Response

from app.api.auth import COOKIE_NAME
from app.application.ports import AuthorityStore
from app.application.services.authority import AuthorityError, build_brand_workspace
from app.application.services.sso import resolve_session
from app.core import Boundary, mark_boundary


def create_workspace_router(store: AuthorityStore | None) -> APIRouter:
    router = APIRouter()

    @router.get("/api/workspace/brands")
    @mark_boundary(Boundary.QUERY)
    async def workspace_brands(
        response: Response,
        selected_brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> dict[str, object]:
        if store is None or not session or not (payload := resolve_session(session, store)):
            raise HTTPException(401, "session_invalid")
        user_id = str(payload.get("user_id") or "")
        launch_brand_id = str(payload.get("brand_id") or "")
        try:
            workspace = build_brand_workspace(
                store=store,
                user_id=user_id,
                selected_brand_id=selected_brand_id or launch_brand_id,
                rollup=rollup,
            )
        except AuthorityError as exc:
            raise HTTPException(403, str(exc)) from exc
        response.headers["Cache-Control"] = "no-store"
        return asdict(workspace)

    return router


__all__ = ["create_workspace_router"]

"""Shared session and Brand scope resolution for API queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException

from app.application.ports import AuthorityStore
from app.application.services.authority import AuthorityError, build_brand_workspace
from app.application.services.sso import (
    resolve_session,
    session_can_access_integrations,
    session_can_access_settings,
)
from app.domain.authority import BrandWorkspace


@dataclass(frozen=True)
class RequestScope:
    session: dict[str, Any]
    workspace: BrandWorkspace


def resolve_request_scope(
    *,
    store: AuthorityStore | None,
    raw_session: str | None,
    selected_brand_id: str | None,
    rollup: bool,
    require_write: bool = False,
    require_settings: bool = False,
    require_integrations: bool = False,
) -> RequestScope:
    if store is None or not raw_session or not (payload := resolve_session(raw_session, store)):
        raise HTTPException(401, "session_invalid")
    if require_settings and not session_can_access_settings(payload):
        raise HTTPException(403, "settings_capability_required")
    if require_integrations and not session_can_access_integrations(payload):
        raise HTTPException(403, "integrations_capability_required")
    launch_brand_id = str(payload.get("brand_id") or "")
    try:
        workspace = build_brand_workspace(
            session=payload,
            selected_brand_id=selected_brand_id or launch_brand_id,
            rollup=rollup,
            require_write=require_write,
        )
    except AuthorityError as exc:
        raise HTTPException(403, str(exc)) from exc
    return RequestScope(session=payload, workspace=workspace)


__all__ = ["RequestScope", "resolve_request_scope"]

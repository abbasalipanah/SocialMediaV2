"""Shared signed-session context for OAuth channel commands."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException

from app.api.scope import RequestScope, resolve_request_scope
from app.application.ports import ActivationContext, AuthorityStore, TikTokActivationError
from app.application.services.sso import session_can_access_settings
from app.core.security import sha256_text
from app.domain.platforms import PlatformId


def resolve_oauth_channel_context(
    *,
    authority_store: AuthorityStore | None,
    raw_session: str | None,
    requested_brand_id: str | None,
    platform: PlatformId,
) -> tuple[RequestScope, ActivationContext]:
    scope = resolve_request_scope(
        store=authority_store,
        raw_session=raw_session,
        selected_brand_id=requested_brand_id,
        rollup=False,
        require_write=False,
        require_settings=False,
        require_integrations=True,
    )
    target_brand_id = scope.workspace.scope.requested_brand_id
    session_brand_id = str(scope.session.get("brand_id") or "")
    if target_brand_id != session_brand_id and not session_can_access_settings(
        scope.session
    ):
        raise HTTPException(403, "oauth_channel_brand_forbidden")
    if scope.workspace.scope.resolved_brand_ids != (target_brand_id,):
        raise HTTPException(403, "oauth_channel_brand_forbidden")
    try:
        context = ActivationContext(
            user_id=str(scope.session.get("user_id") or ""),
            brand_id=int(target_brand_id),
            session_binding=sha256_text(raw_session or ""),
            sso_jti_hash=sha256_text(
                f"{platform.value}-self-service:{raw_session or ''}"
            ),
            sso_consumed_at=datetime.fromtimestamp(0, UTC),
        )
    except (TypeError, ValueError, TikTokActivationError) as exc:
        raise HTTPException(403, "oauth_channel_brand_forbidden") from exc
    return scope, context


__all__ = ["resolve_oauth_channel_context"]

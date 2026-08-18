"""SSO consume and local-session routes."""

from __future__ import annotations

import time
from urllib.parse import parse_qs

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.api.contracts import AuthMeResponse
from app.application.ports import AuthorityStore
from app.application.services.authority import session_has_current_brand_access
from app.application.services.sso import (
    SsoError,
    consume_sso,
    resolve_session,
    session_can_access_integrations,
    session_can_access_settings,
)
from app.core import AppSettings, Boundary, WritePolicy, mark_boundary
from app.core.security import sha256_text

COOKIE_NAME = "social_media_session"
# A launch token stays far below this even with the contract's 500-Brand ceiling.
MAX_CONSUME_BODY_BYTES = 256 * 1024


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    expected = f"{request.url.scheme}://{request.url.netloc}"
    if origin != expected:
        raise HTTPException(403, "origin_invalid")


def create_auth_router(
    settings: AppSettings, policy: WritePolicy, store: AuthorityStore | None
) -> APIRouter:
    router = APIRouter()

    def _consume(token: str) -> RedirectResponse:
        if store is None:
            raise HTTPException(503, "session_store_unavailable")
        try:
            policy.assert_allows_mutation("sso_consume")
            raw_session, verified = consume_sso(token, settings.sso_hs256_secret, store)
        except PermissionError as exc:
            raise HTTPException(403, "writes_disabled") from exc
        except SsoError as exc:
            reason = str(exc)
            raise HTTPException(503 if reason == "sso_not_configured" else 401, reason) from exc
        response = RedirectResponse(verified.launch_path, status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            raw_session,
            httponly=True,
            secure=settings.session_cookie_secure,
            samesite="lax",
            max_age=max(0, int(verified.expires_at.timestamp() - time.time())),
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @router.get("/sso/consume", include_in_schema=False)
    @mark_boundary(Boundary.PROTOCOL_COMMAND)
    async def sso_consume(token: str = Query(min_length=1)) -> RedirectResponse:
        return _consume(token)

    @router.post("/sso/consume", include_in_schema=False)
    @mark_boundary(Boundary.PROTOCOL_COMMAND)
    async def sso_consume_form(request: Request) -> RedirectResponse:
        """Same launch, with the token in a request body instead of the URL.

        The signed contract carries the accessible Brand family, so the launch
        URL grows with the Brand catalogue and a large one is dropped by proxies
        long before it reaches the application. A body has no such ceiling.
        Both routes share one implementation so they can never diverge.

        The single field is parsed here rather than through `Form`, which would
        pull in a form-parsing dependency for one value.
        """
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        if content_type != "application/x-www-form-urlencoded":
            raise HTTPException(415, "unsupported_media_type")
        body = await request.body()
        if len(body) > MAX_CONSUME_BODY_BYTES:
            raise HTTPException(413, "launch_payload_too_large")
        try:
            fields = parse_qs(body.decode("utf-8"), strict_parsing=True)
        except (UnicodeDecodeError, ValueError) as exc:
            raise HTTPException(400, "launch_payload_invalid") from exc
        tokens = fields.get("token") or []
        if len(tokens) != 1 or not tokens[0]:
            raise HTTPException(400, "launch_payload_invalid")
        return _consume(tokens[0])

    @router.get("/api/auth/me", response_model=AuthMeResponse)
    @mark_boundary(Boundary.QUERY)
    async def auth_me(
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> dict[str, object]:
        if store is None or not session or not (payload := resolve_session(session, store)):
            raise HTTPException(401, "session_invalid")
        if not session_has_current_brand_access(
            session=payload,
            brand_id=str(payload.get("brand_id") or ""),
        ):
            raise HTTPException(401, "session_authority_revoked")
        return {
            "authenticated": True,
            "email": payload.get("email"),
            "source_system": payload.get("source_system"),
            **payload,
            "app_role": payload.get("app_role"),
            "settings_visible": session_can_access_settings(payload),
            "integrations_visible": session_can_access_integrations(payload),
        }

    @router.post("/api/auth/logout", status_code=204)
    @mark_boundary(Boundary.COMMAND)
    async def logout(
        request: Request,
        response: Response,
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> None:
        if store is None:
            raise HTTPException(503, "session_store_unavailable")
        try:
            policy.assert_allows_mutation("session_logout")
        except PermissionError as exc:
            raise HTTPException(403, "writes_disabled") from exc
        if session:
            _require_same_origin(request)
            store.revoke_session(sha256_text(session))
        response.delete_cookie(
            COOKIE_NAME,
            path="/",
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"

    return router

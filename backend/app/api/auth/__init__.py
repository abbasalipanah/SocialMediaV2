"""SSO consume and local-session routes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse

from app.api.contracts import AuthMeResponse
from app.application.ports import AuthorityStore
from app.application.services.authority import session_has_current_brand_access
from app.application.services.sso import SsoError, consume_sso, resolve_session
from app.core import AppSettings, Boundary, WritePolicy, mark_boundary
from app.core.security import sha256_text

COOKIE_NAME = "social_media_session"


def _require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    expected = f"{request.url.scheme}://{request.url.netloc}"
    if origin != expected:
        raise HTTPException(403, "origin_invalid")


def create_auth_router(
    settings: AppSettings, policy: WritePolicy, store: AuthorityStore | None
) -> APIRouter:
    router = APIRouter()

    @router.get("/sso/consume", include_in_schema=False)
    @mark_boundary(Boundary.PROTOCOL_COMMAND)
    async def sso_consume(token: str = Query(min_length=1)) -> RedirectResponse:
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
            max_age=max(0, int(verified.expires_at.timestamp() - __import__("time").time())),
            path="/",
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

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

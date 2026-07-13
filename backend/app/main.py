"""ASGI application factory for the canonical Social Media V2 backend."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from app.api import create_api_router
from app.application.ports import AuthorityStore
from app.core import WritePolicy, load_settings
from app.infrastructure.persistence.projection_state import ProjectionStateStore


def create_app(store: AuthorityStore | None = None) -> FastAPI:
    settings = load_settings()
    policy = WritePolicy.from_settings(settings)
    application = FastAPI(
        title="Social Media V2",
        version="0.1.0",
        redirect_slashes=False,
    )
    application.state.settings = settings
    application.state.write_policy = policy

    @application.middleware("http")
    async def auth_cache_policy(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.url.path == "/sso/consume" or request.url.path.startswith("/api/auth/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    if store is None and settings.db.url:
        store = ProjectionStateStore(settings.db.url)
    application.include_router(create_api_router(settings, policy, store))
    return application


app = create_app()

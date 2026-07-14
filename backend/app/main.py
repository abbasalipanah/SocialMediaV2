"""ASGI application factory for the canonical Social Media V2 backend."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from sqlalchemy import create_engine

from app.api import create_api_router
from app.application.ports import AuthorityStore, ReportingStore
from app.core import WritePolicy, load_settings
from app.infrastructure.persistence.legacy_socialmedia import LegacyReportingStore
from app.infrastructure.persistence.projection_state import ProjectionStateStore


def create_app(
    store: AuthorityStore | None = None,
    reporting_store: ReportingStore | None = None,
    media_root: Path | None = None,
) -> FastAPI:
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

    if settings.db.url and (store is None or reporting_store is None):
        engine = create_engine(settings.db.url, pool_pre_ping=True, pool_size=5, max_overflow=2)
        if store is None:
            store = ProjectionStateStore(engine=engine)
        if reporting_store is None:
            reporting_store = LegacyReportingStore(engine)
    resolved_media_root = media_root or (
        Path(settings.media_storage_root) if settings.media_storage_root else None
    )
    application.include_router(
        create_api_router(
            settings,
            policy,
            store,
            reporting_store=reporting_store,
            media_root=resolved_media_root,
        )
    )
    return application


app = create_app()

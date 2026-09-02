"""ASGI application factory for the canonical Social Media V2 backend."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from sqlalchemy import create_engine

from app.api import create_api_router
from app.application.ports import AiSummaryService, AuthorityStore, ReportingStore
from app.application.services.ai_summary import AiSummaryCoordinator
from app.application.services.meta_activation import MetaActivationCoordinator
from app.application.services.oauth_channel_activation import (
    OAuthChannelActivationCoordinator,
)
from app.application.services.report_exports import ReportJobManager
from app.application.services.tiktok_activation import TikTokActivationCoordinator
from app.core import WritePolicy, load_settings
from app.domain.metrics import bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.projection_state import ProjectionStateStore
from app.infrastructure.persistence.social_v2 import (
    SocialAiSummaryRepository,
    SocialReportingStore,
)
from app.infrastructure.providers.ai import OpenRouterAiSummaryProvider
from app.infrastructure.providers.linkedin.runtime import create_linkedin_activation_runtime
from app.infrastructure.providers.meta.runtime import create_meta_activation_runtime
from app.infrastructure.providers.tiktok.runtime import create_tiktok_activation_runtime
from app.infrastructure.providers.x.runtime import create_x_activation_runtime
from app.infrastructure.providers.youtube.runtime import create_youtube_activation_runtime


def create_app(
    store: AuthorityStore | None = None,
    reporting_store: ReportingStore | None = None,
    media_root: Path | None = None,
    tiktok_activation: TikTokActivationCoordinator | None = None,
    meta_activation: MetaActivationCoordinator | None = None,
    x_activation: OAuthChannelActivationCoordinator | None = None,
    linkedin_activation: OAuthChannelActivationCoordinator | None = None,
    youtube_activation: OAuthChannelActivationCoordinator | None = None,
    ai_summary: AiSummaryService | None = None,
) -> FastAPI:
    settings = load_settings()
    policy = WritePolicy.from_settings(settings)
    report_jobs = ReportJobManager()

    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        try:
            yield
        finally:
            report_jobs.close()

    application = FastAPI(
        title="Social Media V2",
        version="0.1.0",
        redirect_slashes=False,
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.write_policy = policy
    application.state.report_jobs = report_jobs

    @application.middleware("http")
    async def auth_cache_policy(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if (
            request.url.path == "/sso/consume"
            or request.url.path == "/api/social/tiktok/oauth/callback"
            or request.url.path.startswith("/api/auth/")
            or request.url.path.startswith("/api/settings/tiktok/oauth/")
            or request.url.path.startswith("/api/integrations/tiktok/")
            or request.url.path == "/api/social/meta/oauth/callback"
            or request.url.path.startswith("/api/integrations/meta/")
            or request.url.path.startswith("/api/integrations/x/")
            or request.url.path == "/api/social/x/oauth/callback"
            or request.url.path.startswith("/api/integrations/linkedin/")
            or request.url.path == "/api/social/linkedin/oauth/callback"
            or request.url.path.startswith("/api/integrations/youtube/")
            or request.url.path == "/api/social/youtube/oauth/callback"
            or request.url.path.startswith("/api/insights")
            or request.url.path.startswith("/api/reports/")
        ):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
        return response

    engine = None
    if settings.db.url and (
        store is None
        or reporting_store is None
        or (tiktok_activation is None and settings.tiktok.account_enabled)
        or (meta_activation is None and settings.meta.account_enabled)
        or (x_activation is None and settings.x.account_enabled)
        or (linkedin_activation is None and settings.linkedin.account_enabled)
        or (youtube_activation is None and settings.youtube.account_enabled)
    ):
        engine = create_engine(settings.db.url, pool_pre_ping=True, pool_size=5, max_overflow=2)
        if store is None:
            store = ProjectionStateStore(engine=engine)
        if reporting_store is None:
            reporting_store = SocialReportingStore(engine)
    if tiktok_activation is None and settings.tiktok.account_enabled:
        if engine is None or store is None:
            raise RuntimeError("tiktok_activation_runtime_unavailable")
        tiktok_activation = create_tiktok_activation_runtime(
            settings=settings,
            policy=policy,
            engine=engine,
            authority_store=store,
        )
    if meta_activation is None and settings.meta.account_enabled:
        if engine is None or store is None:
            raise RuntimeError("meta_activation_runtime_unavailable")
        meta_activation = create_meta_activation_runtime(
            settings=settings,
            policy=policy,
            engine=engine,
            authority_store=store,
        )
    if youtube_activation is None and settings.youtube.account_enabled:
        if engine is None or store is None:
            raise RuntimeError("youtube_activation_runtime_unavailable")
        youtube_activation = create_youtube_activation_runtime(
            settings=settings,
            policy=policy,
            engine=engine,
            authority_store=store,
        )
    if x_activation is None and settings.x.account_enabled:
        if engine is None or store is None:
            raise RuntimeError("x_activation_runtime_unavailable")
        x_activation = create_x_activation_runtime(
            settings=settings,
            policy=policy,
            engine=engine,
            authority_store=store,
        )
    if linkedin_activation is None and settings.linkedin.account_enabled:
        if engine is None or store is None:
            raise RuntimeError("linkedin_activation_runtime_unavailable")
        linkedin_activation = create_linkedin_activation_runtime(
            settings=settings,
            policy=policy,
            engine=engine,
            authority_store=store,
        )
    if ai_summary is None and engine is not None and reporting_store is not None:
        ai_summary = AiSummaryCoordinator(
            repository=SocialAiSummaryRepository(engine),
            reporting_store=reporting_store,
            metric_catalog=bootstrap_metric_catalog(),
            provider=(
                OpenRouterAiSummaryProvider(settings.ai_summary)
                if settings.ai_summary.configured
                else None
            ),
        )
    application.state.tiktok_activation_configured = tiktok_activation is not None
    application.state.meta_activation_configured = meta_activation is not None
    application.state.youtube_activation_configured = youtube_activation is not None
    application.state.x_activation_configured = x_activation is not None
    application.state.linkedin_activation_configured = linkedin_activation is not None
    application.state.ai_summary_provider_configured = (
        ai_summary.provider_configured if ai_summary is not None else False
    )
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
            tiktok_activation=tiktok_activation,
            meta_activation=meta_activation,
            oauth_activations=(
                {
                    platform: activation
                    for platform, activation in (
                        (PlatformId.X, x_activation),
                        (PlatformId.LINKEDIN, linkedin_activation),
                        (PlatformId.YOUTUBE, youtube_activation),
                    )
                    if activation is not None
                }
            ),
            ai_summary=ai_summary,
            report_jobs=report_jobs,
        )
    )
    return application


app = create_app()

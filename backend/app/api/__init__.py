"""Bootstrap API routes with explicit query semantics."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Cookie, HTTPException, Query

from app.api.auth import COOKIE_NAME, create_auth_router
from app.api.contracts import OperationsReadinessResponse, ReadinessPlatform
from app.api.dashboards import create_dashboard_router
from app.api.insights import create_insights_router
from app.api.internal import create_internal_router
from app.api.media import create_media_router
from app.api.operations import create_operations_router
from app.api.platforms import create_platform_router
from app.api.scope import resolve_request_scope
from app.api.settings import create_settings_router
from app.api.workspace import create_workspace_router
from app.application.ports import AuthorityStore, ReportingStore
from app.application.services.meta_activation import MetaActivationCoordinator
from app.application.services.tiktok_activation import TikTokActivationCoordinator
from app.capabilities import bootstrap_registry
from app.core import AppSettings, Boundary, WritePolicy, mark_boundary
from app.domain.metrics import bootstrap_metric_catalog
from app.domain.platforms import PlatformId


def create_api_router(
    settings: AppSettings,
    policy: WritePolicy,
    store: AuthorityStore | None = None,
    *,
    reporting_store: ReportingStore | None = None,
    media_root: Path | None = None,
    tiktok_activation: TikTokActivationCoordinator | None = None,
    meta_activation: MetaActivationCoordinator | None = None,
) -> APIRouter:
    router = APIRouter()
    capabilities = bootstrap_registry()
    metric_catalog = bootstrap_metric_catalog()

    @router.get("/api/health", tags=["health"], summary="Health probe")
    @mark_boundary(Boundary.QUERY)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get(
        "/api/operations/readiness",
        tags=["operations"],
        summary="Dormant readiness probe",
        response_model=OperationsReadinessResponse,
        response_model_exclude_none=True,
        response_model_exclude_defaults=True,
    )
    @mark_boundary(Boundary.QUERY)
    async def readiness(
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> OperationsReadinessResponse:
        base = OperationsReadinessResponse(
            status="ready",
            runtime_mode=settings.runtime_mode,
            writes_enabled=policy.writes_enabled,
            database_configured=settings.db.configured,
        )
        if session is None and brand_id is None:
            return base
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        scope = resolve_request_scope(
            store=store,
            raw_session=session,
            selected_brand_id=brand_id,
            rollup=rollup,
        )
        accounts = reporting_store.list_accounts(
            brand_ids=scope.workspace.scope.resolved_brand_ids
        )
        jobs = reporting_store.list_sync_jobs(
            brand_ids=scope.workspace.scope.resolved_brand_ids
        )
        return OperationsReadinessResponse(
            status=base.status,
            runtime_mode=base.runtime_mode,
            writes_enabled=base.writes_enabled,
            database_configured=base.database_configured,
            scope=scope.workspace.scope,
            platforms=tuple(
                ReadinessPlatform(
                    platform=platform,
                    account_count=sum(
                        account.platform is platform for account in accounts
                    ),
                    last_sync_at=max(
                        (
                            account.last_synced_at
                            for account in accounts
                            if account.platform is platform
                            and account.last_synced_at is not None
                        ),
                        default=None,
                    ),
                    pending_job_count=sum(
                        job.platform is platform and job.status in {"pending", "running"}
                        for job in jobs
                    ),
                )
                for platform in PlatformId
            ),
        )

    router.include_router(create_auth_router(settings, policy, store))
    router.include_router(create_internal_router(settings, policy, store))
    router.include_router(
        create_workspace_router(
            store, reporting_store, capabilities, policy, settings.runtime_mode
        )
    )
    router.include_router(create_dashboard_router(store, reporting_store, metric_catalog))
    router.include_router(create_platform_router(store, reporting_store))
    router.include_router(
        create_settings_router(
            store,
            reporting_store,
            capabilities,
            policy,
            activation=tiktok_activation,
            meta_activation=meta_activation,
        )
    )
    router.include_router(create_insights_router(store, reporting_store))
    router.include_router(create_operations_router(store, policy))
    router.include_router(create_media_router(store, reporting_store, media_root))
    return router


__all__ = ["create_api_router"]

"""Authorized local-only social media proxy."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fastapi import APIRouter, Cookie, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.auth import COOKIE_NAME
from app.api.scope import resolve_request_scope
from app.application.ports import AuthorityStore, ReportingStore
from app.core import Boundary, mark_boundary
from app.domain.platforms import PlatformId


def create_media_router(
    authority_store: AuthorityStore | None,
    reporting_store: ReportingStore | None,
    media_root: Path | None,
) -> APIRouter:
    router = APIRouter()

    @router.get("/api/media/{platform}/{content_id}")
    @mark_boundary(Boundary.QUERY)
    async def social_media(
        platform: PlatformId,
        content_id: str,
        brand_id: str | None = Query(default=None),
        rollup: bool = Query(default=False),
        account_id: int | None = Query(default=None, ge=1),
        session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> FileResponse:
        if reporting_store is None:
            raise HTTPException(503, "reporting_store_unavailable")
        if media_root is None:
            raise HTTPException(503, "media_root_unavailable")
        scope = resolve_request_scope(
            store=authority_store,
            raw_session=session,
            selected_brand_id=brand_id,
            rollup=rollup,
        )
        media = reporting_store.find_media(
            brand_ids=scope.workspace.scope.resolved_brand_ids,
            platform=platform,
            external_content_id=content_id,
            account_id=account_id,
        )
        if media is None:
            raise HTTPException(404, "media_not_found")
        root = media_root.resolve()
        candidate = media.storage_path
        resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise HTTPException(404, "media_not_found")
        if resolved.stat().st_size != media.size_bytes:
            raise HTTPException(409, "media_integrity_failed")
        digest = hashlib.sha256()
        with resolved.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != media.checksum:
            raise HTTPException(409, "media_integrity_failed")
        return FileResponse(
            resolved,
            media_type=media.mime_type,
            headers={
                "Cache-Control": "private, max-age=300",
                "ETag": f'"{media.checksum}"',
                "X-Content-Type-Options": "nosniff",
            },
        )

    return router


__all__ = ["create_media_router"]

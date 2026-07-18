"""Loopback-only demo runtime for exercising the complete local product UI."""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request, Response

from app.api.auth import COOKIE_NAME
from app.application.ports import ProjectionReplacement, ProjectionWrite
from app.application.ports.reporting import (
    ReportingAccount,
    ReportingComment,
    ReportingConnection,
    ReportingContent,
    ReportingInsight,
    ReportingMedia,
    ReportingMetric,
    ReportingSyncJob,
)
from app.core import Boundary, RuntimeMode, mark_boundary
from app.core.security import sha256_text
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.main import create_app

LOCAL_DEMO_HEADER = "X-Social-Local-Demo"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class LocalDemoAuthority:
    """Small in-memory authority store that never reads an external identity system."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.projections: dict[str, dict[str, Any]] = {
            "v2:brand-shell:100": {
                "active": True,
                "brand_id": "100",
                "name": "Demo Hotel Group",
                "parent_brand_id": None,
                "placeholder": False,
            },
            "v2:brand-shell:101": {
                "active": True,
                "brand_id": "101",
                "name": "Demo Resort",
                "parent_brand_id": "100",
                "placeholder": False,
            },
            "v2:brand-shell:102": {
                "active": True,
                "brand_id": "102",
                "name": "Demo City Hotel",
                "parent_brand_id": "100",
                "placeholder": False,
            },
            "v2:brand-access:local-demo-user:101": {
                "access_mode": "write",
                "active": True,
                "authority_source": "full_snapshot",
                "brand_id": "101",
                "role": "agency_admin",
                "user_id": "local-demo-user",
            },
            "v2:brand-access:local-demo-user:102": {
                "access_mode": "read",
                "active": True,
                "authority_source": "full_snapshot",
                "brand_id": "102",
                "role": "viewer",
                "user_id": "local-demo-user",
            },
        }

    def open_session(self) -> str:
        raw_session = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=12)
        self.sessions[sha256_text(raw_session)] = {
            "user_id": "local-demo-user",
            "email": "local.demo@example.test",
            "source_system": "accumulate",
            "brand_id": "101",
            "role": "agency_admin",
            "access_mode": "write",
            "settings_visible": True,
            "is_internal_staff": True,
            "expires_at": expires_at.isoformat(),
            "sso_issued_at": now.isoformat(),
            "sso_consumed_at": now.isoformat(),
            "launch_target": None,
            "permissions": ("tiktok.connection.manage",),
            "sso_jti_hash": sha256_text(f"local-demo-{raw_session}"),
            "revoked": False,
        }
        return raw_session

    def create_from_jti(
        self,
        *,
        jti_hash: str,
        session_hash: str,
        payload: Mapping[str, Any],
        expires_at: datetime,
    ) -> bool:
        del expires_at
        replay_key = f"v2:sso-jti:{jti_hash}"
        if replay_key in self.projections:
            return False
        self.projections[replay_key] = {"consumed": True}
        self.sessions[session_hash] = dict(payload)
        return True

    def get_session(self, session_hash: str) -> Mapping[str, Any] | None:
        return self.sessions.get(session_hash)

    def revoke_session(self, session_hash: str) -> None:
        if payload := self.sessions.get(session_hash):
            payload["revoked"] = True

    def revoke_authority_sessions(self, *, user_id: str | None, brand_id: str | None) -> int:
        revoked = 0
        for payload in self.sessions.values():
            if user_id and payload.get("user_id") != user_id:
                continue
            if brand_id and payload.get("brand_id") != brand_id:
                continue
            if payload.get("revoked") is not True:
                payload["revoked"] = True
                revoked += 1
        return revoked

    def apply_event(
        self,
        *,
        nonce_hash: str,
        nonce_expires_at: datetime,
        event_id: str,
        event_type: str,
        entity_key: str,
        version: int,
        payload: Mapping[str, Any],
        projection_writes: tuple[ProjectionWrite, ...] = (),
        replacement: ProjectionReplacement | None = None,
    ) -> str:
        del nonce_hash, nonce_expires_at, event_type
        event_key = f"v2:event:{event_id}"
        if event_key in self.projections:
            return "duplicate_ignored"
        current = self.projections.get(entity_key, {})
        if int(current.get("version", -1)) >= version:
            return "stale_ignored"
        self.projections[event_key] = {"version": version}
        self.projections[entity_key] = {**payload, "version": version}
        for write in projection_writes:
            self.projections[write.projection_key] = {**write.payload, "version": version}
        if replacement is not None:
            desired = {write.projection_key for write in replacement.writes}
            for key in tuple(self.projections):
                if key.startswith(replacement.projection_key_prefix) and key not in desired:
                    self.projections[key] = {
                        **self.projections[key],
                        "active": False,
                        "version": replacement.version,
                    }
            for write in replacement.writes:
                self.projections[write.projection_key] = {
                    **write.payload,
                    "version": replacement.version,
                }
        return "applied"

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None:
        return self.projections.get(entity_key)

    def list_projections(self, projection_key_prefix: str) -> list[Mapping[str, Any]]:
        return [
            payload
            for key, payload in sorted(self.projections.items())
            if key.startswith(projection_key_prefix)
        ]


def _metric(
    account_id: int,
    brand_id: str,
    platform: PlatformId,
    observed_on: date,
    metric_id: MetricId,
    value: float,
) -> ReportingMetric:
    return ReportingMetric(
        account_id=account_id,
        brand_id=brand_id,
        platform=platform,
        observed_on=observed_on,
        metric_id=metric_id,
        value=value,
    )


class LocalDemoReporting:
    """Deterministic social reporting rows for local visual and API testing."""

    def __init__(self) -> None:
        now = datetime.now(UTC)
        today = now.date()
        previous = today - timedelta(days=29)
        recent = today - timedelta(days=1)
        synced_at = now - timedelta(minutes=20)
        self.accounts = (
            ReportingAccount(
                11, "101", PlatformId.FACEBOOK, "page-101", "Demo Resort Facebook",
                "active", "connected", "healthy", "complete", True, synced_at,
            ),
            ReportingAccount(
                12, "102", PlatformId.FACEBOOK, "page-102", "Demo City Facebook",
                "active", "connected", "healthy", "complete", True, synced_at,
            ),
            ReportingAccount(
                21, "101", PlatformId.INSTAGRAM, "profile-101", "Demo Resort Instagram",
                "active", "connected", "healthy", "complete", True, synced_at,
            ),
            ReportingAccount(
                31, "101", PlatformId.TIKTOK, "account-101", "Demo Resort TikTok",
                "active", "connected", "healthy", "complete", False, synced_at,
            ),
        )
        self.metrics = (
            _metric(11, "101", PlatformId.FACEBOOK, previous, MetricId.FOLLOWERS, 1240),
            _metric(11, "101", PlatformId.FACEBOOK, recent, MetricId.FOLLOWERS, 1385),
            _metric(11, "101", PlatformId.FACEBOOK, recent, MetricId.REACH, 18400),
            _metric(11, "101", PlatformId.FACEBOOK, recent, MetricId.INTERACTIONS, 1260),
            _metric(11, "101", PlatformId.FACEBOOK, recent, MetricId.PAGE_VIEWS, 3250),
            _metric(12, "102", PlatformId.FACEBOOK, previous, MetricId.FOLLOWERS, 860),
            _metric(12, "102", PlatformId.FACEBOOK, recent, MetricId.FOLLOWERS, 940),
            _metric(12, "102", PlatformId.FACEBOOK, recent, MetricId.REACH, 9200),
            _metric(21, "101", PlatformId.INSTAGRAM, previous, MetricId.FOLLOWERS, 8120),
            _metric(21, "101", PlatformId.INSTAGRAM, recent, MetricId.FOLLOWERS, 8560),
            _metric(21, "101", PlatformId.INSTAGRAM, recent, MetricId.REACH, 42600),
            _metric(21, "101", PlatformId.INSTAGRAM, recent, MetricId.VIEWS, 73100),
            _metric(21, "101", PlatformId.INSTAGRAM, recent, MetricId.INTERACTIONS, 4810),
            _metric(21, "101", PlatformId.INSTAGRAM, recent, MetricId.PROFILE_VIEWS, 6100),
            _metric(31, "101", PlatformId.TIKTOK, previous, MetricId.FOLLOWERS, 3400),
            _metric(31, "101", PlatformId.TIKTOK, recent, MetricId.FOLLOWERS, 3890),
            _metric(31, "101", PlatformId.TIKTOK, previous, MetricId.VIDEO_VIEWS_TOTAL, 98000),
            _metric(31, "101", PlatformId.TIKTOK, recent, MetricId.VIDEO_VIEWS_TOTAL, 126000),
            _metric(31, "101", PlatformId.TIKTOK, recent, MetricId.VIDEO_LIKES_TOTAL, 9400),
            _metric(31, "101", PlatformId.TIKTOK, recent, MetricId.VIDEO_COMMENTS_TOTAL, 620),
            _metric(31, "101", PlatformId.TIKTOK, recent, MetricId.VIDEO_SHARES_TOTAL, 1180),
        )
        self.content = (
            ReportingContent(
                11, "101", PlatformId.FACEBOOK, "demo-fb-post", "image",
                "https://example.test/demo-fb-post", "A quiet morning by the pool.", "",
                now - timedelta(days=2), 418, 37, 22,
            ),
            ReportingContent(
                21, "101", PlatformId.INSTAGRAM, "demo-ig-post", "reel",
                "https://example.test/demo-ig-post", "Sunset from the terrace.", "",
                now - timedelta(days=3), 912, 64, 118,
            ),
            ReportingContent(
                31, "101", PlatformId.TIKTOK, "demo-tt-video", "video",
                "https://example.test/demo-tt-video", "A day at Demo Resort.", "",
                now - timedelta(days=4), 2240, 143, 305,
            ),
        )
        self.comments = (
            ReportingComment(
                11, PlatformId.FACEBOOK, "demo-fb-post", "demo-comment-1",
                "Demo Guest", "Beautiful view!", 12, 1, True, now - timedelta(days=2),
            ),
            ReportingComment(
                21, PlatformId.INSTAGRAM, "demo-ig-post", "demo-comment-2",
                "Demo Traveler", "Adding this to my list.", 21, 0, False,
                now - timedelta(days=3),
            ),
        )
        self.connections = (
            ReportingConnection(1, "101", PlatformId.FACEBOOK, "connected", None, synced_at),
            ReportingConnection(2, "101", PlatformId.INSTAGRAM, "connected", None, synced_at),
            ReportingConnection(3, "101", PlatformId.TIKTOK, "connected", None, synced_at),
        )
        self.jobs = (
            ReportingSyncJob(
                1, "101", 11, PlatformId.FACEBOOK, "daily", "completed",
                synced_at, synced_at, synced_at + timedelta(minutes=2), None,
            ),
        )
        self.insights = (
            ReportingInsight(
                1, "101", "completed", previous, today,
                "Reach and follower momentum are positive across the demo channels.",
                "Test the account and date filters, then export a dashboard PNG.",
                now - timedelta(minutes=10), now - timedelta(minutes=9),
            ),
        )

    def list_accounts(
        self, *, brand_ids: tuple[str, ...], platform: PlatformId | None = None
    ) -> tuple[ReportingAccount, ...]:
        return tuple(
            row
            for row in self.accounts
            if row.brand_id in brand_ids and (platform is None or row.platform is platform)
        )

    def list_metrics(
        self, *, account_ids: tuple[int, ...], start_on: date, end_on: date
    ) -> tuple[ReportingMetric, ...]:
        return tuple(
            row
            for row in self.metrics
            if row.account_id in account_ids and start_on <= row.observed_on <= end_on
        )

    def list_content(
        self,
        *,
        account_ids: tuple[int, ...],
        start_on: date,
        end_on: date,
        content_type: str | None = None,
    ) -> tuple[ReportingContent, ...]:
        return tuple(
            row
            for row in self.content
            if row.account_id in account_ids
            and row.published_at is not None
            and start_on <= row.published_at.date() <= end_on
            and (content_type is None or row.content_type == content_type)
        )

    def list_comments(
        self, *, account_ids: tuple[int, ...], start_on: date, end_on: date
    ) -> tuple[ReportingComment, ...]:
        return tuple(
            row
            for row in self.comments
            if row.account_id in account_ids
            and row.commented_at is not None
            and start_on <= row.commented_at.date() <= end_on
        )

    def find_media(
        self,
        *,
        brand_ids: tuple[str, ...],
        platform: PlatformId,
        external_content_id: str,
        account_id: int | None = None,
    ) -> ReportingMedia | None:
        del brand_ids, platform, external_content_id, account_id
        return None

    def list_connections(
        self, *, brand_ids: tuple[str, ...]
    ) -> tuple[ReportingConnection, ...]:
        return tuple(row for row in self.connections if row.brand_id in brand_ids)

    def list_sync_jobs(
        self, *, brand_ids: tuple[str, ...]
    ) -> tuple[ReportingSyncJob, ...]:
        return tuple(row for row in self.jobs if row.brand_id in brand_ids)

    def list_insights(
        self,
        *,
        brand_ids: tuple[str, ...],
        start_on: date | None = None,
        end_on: date | None = None,
    ) -> tuple[ReportingInsight, ...]:
        if (start_on is None) is not (end_on is None):
            raise ValueError("insight_range_incomplete")
        return tuple(
            row
            for row in self.insights
            if row.brand_id in brand_ids
            and (
                start_on is None
                or end_on is None
                or row.date_from is None
                or row.date_to is None
                or (row.date_from <= end_on and row.date_to >= start_on)
            )
        )


def create_local_demo_app():
    """Create the local-only application used by ``scripts/dev/start_local.sh``."""

    if os.getenv("SOCIAL_LOCAL_DEMO", "").strip().lower() != "true":
        raise RuntimeError("Local demo runtime requires SOCIAL_LOCAL_DEMO=true")
    authority = LocalDemoAuthority()
    reporting = LocalDemoReporting()
    application = create_app(store=authority, reporting_store=reporting, media_root=Path.cwd())
    settings = application.state.settings
    if settings.app_env != "development" or settings.runtime_mode is not RuntimeMode.DEVELOPMENT:
        raise RuntimeError("Local demo runtime requires development mode")

    @application.post("/api/dev/session", status_code=204, include_in_schema=False)
    @mark_boundary(Boundary.COMMAND)
    async def open_local_demo_session(request: Request, response: Response) -> None:
        if (
            request.url.hostname not in LOCAL_HOSTS
            or request.headers.get(LOCAL_DEMO_HEADER) != "true"
        ):
            raise HTTPException(403, "local_demo_denied")
        raw_session = authority.open_session()
        response.set_cookie(
            COOKIE_NAME,
            raw_session,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=12 * 60 * 60,
            path="/",
        )
        response.headers[LOCAL_DEMO_HEADER] = "true"
        response.headers["Cache-Control"] = "no-store"

    @application.post("/api/dev/logout", status_code=204, include_in_schema=False)
    @mark_boundary(Boundary.COMMAND)
    async def close_local_demo_session(request: Request, response: Response) -> None:
        if (
            request.url.hostname not in LOCAL_HOSTS
            or request.headers.get(LOCAL_DEMO_HEADER) != "true"
        ):
            raise HTTPException(403, "local_demo_denied")
        if raw_session := request.cookies.get(COOKIE_NAME):
            authority.revoke_session(sha256_text(raw_session))
        response.delete_cookie(COOKIE_NAME, path="/", httponly=True, samesite="lax")
        response.headers[LOCAL_DEMO_HEADER] = "true"
        response.headers["Cache-Control"] = "no-store"

    return application


__all__ = ["LocalDemoAuthority", "LocalDemoReporting", "create_local_demo_app"]

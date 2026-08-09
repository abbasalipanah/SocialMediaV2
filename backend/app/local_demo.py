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

    def __init__(self, *, database_backed: bool = False) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.jtis: set[str] = set()
        self.database_backed = database_backed

    def open_session(self) -> str:
        raw_session = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        expires_at = now + timedelta(hours=12)
        if self.database_backed:
            brand_id = "18"
            brand_scope = {
                "version": "v1",
                "default_brand_id": brand_id,
                "brands": [
                    {
                        "brand_id": brand_id,
                        "name": "Pine Beach Belek",
                        "parent_brand_id": None,
                        "visibility": "active",
                        "access_mode": "write",
                        "role": "agency_admin",
                    }
                ],
            }
        else:
            brand_id = "101"
            brand_scope = {
                "version": "v1",
                "default_brand_id": "101",
                "brands": [
                    {
                        "brand_id": "100",
                        "name": "Demo Hotel Group",
                        "parent_brand_id": None,
                        "visibility": "hidden_parent",
                        "access_mode": None,
                        "role": None,
                    },
                    {
                        "brand_id": "101",
                        "name": "Demo Resort",
                        "parent_brand_id": "100",
                        "visibility": "active",
                        "access_mode": "write",
                        "role": "agency_admin",
                    },
                    {
                        "brand_id": "102",
                        "name": "Demo City Hotel",
                        "parent_brand_id": "100",
                        "visibility": "active",
                        "access_mode": "read",
                        "role": "viewer",
                    },
                ],
            }
        self.sessions[sha256_text(raw_session)] = {
            "user_id": "local-demo-user",
            "email": "local.demo@example.test",
            "source_system": "accumulate",
            "brand_id": brand_id,
            "brand_scope": brand_scope,
            "role": "agency_admin",
            "app_role": None,
            "access_mode": "write",
            "settings_visible": True,
            "integrations_visible": True,
            "is_internal_staff": True,
            "expires_at": expires_at.isoformat(),
            "sso_issued_at": now.isoformat(),
            "sso_consumed_at": now.isoformat(),
            "launch_target": None,
            "permissions": (
                "social.connection.manage",
                "tiktok.connection.manage",
            ),
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
        if jti_hash in self.jtis:
            return False
        self.jtis.add(jti_hash)
        self.sessions[session_hash] = dict(payload)
        return True

    def get_session(self, session_hash: str) -> Mapping[str, Any] | None:
        return self.sessions.get(session_hash)

    def revoke_session(self, session_hash: str) -> None:
        if payload := self.sessions.get(session_hash):
            payload["revoked"] = True


def _metric(
    account_id: int,
    brand_id: str,
    platform: PlatformId,
    observed_on: date,
    metric_id: MetricId,
    value: float,
    breakdown_key: str | None = None,
    breakdown_value: str | None = None,
) -> ReportingMetric:
    return ReportingMetric(
        account_id=account_id,
        brand_id=brand_id,
        platform=platform,
        observed_on=observed_on,
        metric_id=metric_id,
        value=value,
        breakdown_key=breakdown_key,
        breakdown_value=breakdown_value,
    )


class LocalDemoReporting:
    """Deterministic social reporting rows for local visual and API testing."""

    def __init__(self) -> None:
        now = datetime.now(UTC)
        today = now.date()
        previous = today - timedelta(days=29)
        recent = today - timedelta(days=1)
        synced_at = now - timedelta(minutes=20)
        facebook_history: list[ReportingMetric] = []
        instagram_history: list[ReportingMetric] = []
        tiktok_history: list[ReportingMetric] = []
        for index in range(180):
            observed_on = recent - timedelta(days=179 - index)
            weekday = index % 7
            facebook_values = {
                MetricId.FOLLOWERS: 4620 + (index * 3) + (index // 10),
                MetricId.FOLLOWS: 10 + weekday,
                MetricId.UNFOLLOWS: 2 + (weekday % 3),
                MetricId.FOLLOWERS_NET: 8 + weekday - (weekday % 3),
                MetricId.VIEWS: 80 + (index // 10) + (weekday * 4),
                MetricId.VIEWS_ORGANIC: 70 + (index // 10) + (weekday * 3),
                MetricId.VIEWS_PAID: 10 + weekday,
                MetricId.REACH: 300 + (index * 2) + (weekday * 10),
                MetricId.REACH_ORGANIC: 270 + (index * 2) + (weekday * 8),
                MetricId.REACH_PAID: 30 + (weekday * 2),
                MetricId.PAGE_VIEWS: 76 + (index // 9) + (weekday * 4),
                MetricId.INTERACTIONS: 25 + (index // 12) + (weekday * 2),
                MetricId.TOTAL_ACTIONS: 7 + (index // 30) + weekday,
                MetricId.REACTIONS: 19 + (index // 15) + (weekday * 2),
            }
            facebook_history.extend(
                _metric(11, "101", PlatformId.FACEBOOK, observed_on, metric_id, value)
                for metric_id, value in facebook_values.items()
            )
            facebook_secondary_values = {
                MetricId.FOLLOWERS: 2710 + (index * 2) + (index // 14),
                MetricId.FOLLOWS: 7 + weekday,
                MetricId.UNFOLLOWS: 2 + (weekday % 2),
                MetricId.FOLLOWERS_NET: 5 + weekday - (weekday % 2),
                MetricId.VIEWS: 49 + (index // 15) + (weekday * 3),
                MetricId.VIEWS_ORGANIC: 43 + (index // 15) + (weekday * 2),
                MetricId.VIEWS_PAID: 6 + weekday,
                MetricId.REACH: 210 + index + (weekday * 7),
                MetricId.REACH_ORGANIC: 190 + index + (weekday * 6),
                MetricId.REACH_PAID: 20 + weekday,
                MetricId.PAGE_VIEWS: 45 + (index // 16) + (weekday * 2),
                MetricId.INTERACTIONS: 16 + (index // 20) + weekday,
                MetricId.TOTAL_ACTIONS: 4 + (index // 45) + (weekday // 2),
                MetricId.REACTIONS: 12 + (index // 20) + weekday,
            }
            facebook_history.extend(
                _metric(12, "102", PlatformId.FACEBOOK, observed_on, metric_id, value)
                for metric_id, value in facebook_secondary_values.items()
            )
            instagram_values = {
                MetricId.FOLLOWERS: 7850 + (index * 5) + (index // 9),
                MetricId.FOLLOWING: 410 + (index // 45),
                MetricId.MEDIA_COUNT: 320 + (index // 4),
                MetricId.NEW_FOLLOWERS: 13 + (index % 5) + (1 if weekday in {5, 6} else 0),
                MetricId.FOLLOWS: 13 + (index % 5) + (1 if weekday in {5, 6} else 0),
                MetricId.UNFOLLOWS: 2 + (weekday % 3),
                MetricId.FOLLOWERS_NET: 11 + (index % 5) - (weekday % 3),
                MetricId.REACH: 600 + (index * 4) + (weekday * 15),
                MetricId.REACH_ORGANIC: 570 + (index * 4) + (weekday * 13),
                MetricId.REACH_PAID: 30 + (weekday * 2),
                MetricId.VIEWS: 1000 + (index * 8) + (weekday * 25),
                MetricId.VIEWS_ORGANIC: 930 + (index * 8) + (weekday * 20),
                MetricId.VIEWS_PAID: 70 + (weekday * 5),
                MetricId.PROFILE_VIEWS: 70 + (index // 8) + (weekday * 3),
                MetricId.WEBSITE_CLICKS: 12 + (index // 30) + (weekday // 2),
                MetricId.INTERACTIONS: 75 + (index // 4) + (weekday * 4),
            }
            instagram_history.extend(
                _metric(21, "101", PlatformId.INSTAGRAM, observed_on, metric_id, value)
                for metric_id, value in instagram_values.items()
            )
            tiktok_values = {
                MetricId.FOLLOWERS: 3165 + (index * 4) + (index // 7),
                MetricId.FOLLOWING: 286 + (index // 30),
                MetricId.FOLLOWS: 12 + weekday,
                MetricId.UNFOLLOWS: 3 + (weekday % 2),
                MetricId.FOLLOWERS_NET: 9 + weekday - (weekday % 2),
                MetricId.VIEWS: 900 + (index * 5) + (weekday * 18),
                MetricId.REACH: 510 + (index * 3) + (weekday * 11),
                MetricId.PROFILE_VIEWS: 45 + (index // 5) + weekday,
                MetricId.INTERACTIONS: 72 + (index // 4) + (weekday * 3),
                MetricId.VIDEO_VIEWS_TOTAL: 72000 + (index * 310) + ((index % 7) * 80),
                MetricId.VIDEO_LIKES_TOTAL: 5100 + (index * 25) + ((index % 5) * 4),
                MetricId.VIDEO_COMMENTS_TOTAL: 310 + (index * 2) + (index % 3),
                MetricId.VIDEO_SHARES_TOTAL: 580 + (index * 4) + (index % 4),
            }
            tiktok_history.extend(
                _metric(31, "101", PlatformId.TIKTOK, observed_on, metric_id, value)
                for metric_id, value in tiktok_values.items()
            )
        tiktok_audience_rows = (
            ("country", "Türkiye", 2187),
            ("country", "Germany", 858),
            ("country", "United Kingdom", 468),
            ("country", "Other", 390),
            ("city", "Istanbul", 1366),
            ("city", "Antalya", 702),
            ("city", "Berlin", 507),
            ("gender_age", "Female 18-24", 690),
            ("gender_age", "Male 18-24", 365),
            ("gender_age", "Other 18-24", 38),
            ("gender_age", "Female 25-34", 1050),
            ("gender_age", "Male 25-34", 614),
            ("gender_age", "Other 25-34", 53),
            ("gender_age", "Female 35-44", 360),
            ("gender_age", "Male 35-44", 220),
            ("gender_age", "Other 35-44", 20),
            ("gender_age", "Female 45-54", 165),
            ("gender_age", "Male 45-54", 125),
            ("gender_age", "Other 45-54", 10),
            ("gender_age", "Female 55-64", 65),
            ("gender_age", "Male 55-64", 80),
            ("gender_age", "Other 55-64", 5),
            ("gender_age", "Female 65+", 12),
            ("gender_age", "Male 65+", 27),
            ("gender_age", "Other 65+", 4),
        )
        tiktok_audience = tuple(
            _metric(
                31,
                "101",
                PlatformId.TIKTOK,
                recent,
                MetricId.FOLLOWERS,
                value,
                dimension,
                label,
            )
            for dimension, label, value in tiktok_audience_rows
        )
        facebook_audience_rows = (
            ("page_fans_country", "Türkiye", 2930),
            ("page_fans_country", "Germany", 895),
            ("page_fans_country", "United Kingdom", 570),
            ("page_fans_country", "Other", 303),
            ("page_fans_city", "Istanbul", 1540),
            ("page_fans_city", "Antalya", 1210),
            ("page_fans_city", "Berlin", 615),
        )
        facebook_audience = tuple(
            _metric(
                11,
                "101",
                PlatformId.FACEBOOK,
                recent,
                MetricId.FOLLOWERS,
                value,
                dimension,
                label,
            )
            for dimension, label, value in facebook_audience_rows
        )
        facebook_card_breakdowns = tuple(
            _metric(11, "101", PlatformId.FACEBOOK, recent, metric_id, value, dimension, label)
            for metric_id, dimension, label, value in (
                (MetricId.VIEWS, "view_type", "Organic", 3040),
                (MetricId.VIEWS, "view_type", "Paid", 155),
                (MetricId.REACH, "reach_type", "Organic", 19100),
                (MetricId.REACH, "reach_type", "Paid", 700),
                (MetricId.FOLLOWERS, "like_type", "Organic", 84),
                (MetricId.FOLLOWERS, "like_type", "Paid", 6),
                (MetricId.REACH, "content_type_reach", "Video", 12840),
                (MetricId.REACH, "content_type_reach", "Photo", 8850),
                (MetricId.INTERACTIONS, "comment_sentiment", "Positive", 14),
                (MetricId.INTERACTIONS, "comment_sentiment", "Neutral", 5),
                (MetricId.INTERACTIONS, "comment_sentiment", "Negative", 1),
            )
        )
        days = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
        instagram_audience_rows = (
            ("follower_demographics_country", "Türkiye", 4890),
            ("follower_demographics_country", "Germany", 1320),
            ("follower_demographics_country", "United Kingdom", 860),
            ("follower_demographics_country", "Other", 430),
            ("follower_demographics_city", "Istanbul", 2350),
            ("follower_demographics_city", "Antalya", 1710),
            ("follower_demographics_city", "Berlin", 780),
            ("follower_demographics_gender_age", "F.18-24", 800),
            ("follower_demographics_gender_age", "M.18-24", 500),
            ("follower_demographics_gender_age", "U.18-24", 100),
            ("follower_demographics_gender_age", "F.25-34", 1500),
            ("follower_demographics_gender_age", "M.25-34", 1000),
            ("follower_demographics_gender_age", "U.25-34", 250),
            ("follower_demographics_gender_age", "F.35-44", 1100),
            ("follower_demographics_gender_age", "M.35-44", 800),
            ("follower_demographics_gender_age", "U.35-44", 200),
            ("follower_demographics_gender_age", "F.45-54", 650),
            ("follower_demographics_gender_age", "M.45-54", 500),
            ("follower_demographics_gender_age", "U.45-54", 120),
            ("follower_demographics_gender_age", "F.55-64", 330),
            ("follower_demographics_gender_age", "M.55-64", 250),
            ("follower_demographics_gender_age", "U.55-64", 70),
            ("follower_demographics_gender_age", "F.65+", 130),
            ("follower_demographics_gender_age", "M.65+", 100),
            ("follower_demographics_gender_age", "U.65+", 30),
        )
        instagram_audience = tuple(
            _metric(
                21,
                "101",
                PlatformId.INSTAGRAM,
                recent,
                MetricId.FOLLOWERS,
                value,
                dimension,
                label,
            )
            for dimension, label, value in instagram_audience_rows
        )
        instagram_card_breakdowns = tuple(
            _metric(21, "101", PlatformId.INSTAGRAM, recent, metric_id, value, dimension, label)
            for metric_id, dimension, label, value in (
                (MetricId.VIEWS, "view_type", "Organic", 70020),
                (MetricId.VIEWS, "view_type", "Paid", 1780),
                (MetricId.REACH, "reach_type", "Organic", 38010),
                (MetricId.REACH, "reach_type", "Paid", 1090),
                (MetricId.REACH, "content_type_reach", "Reels", 12200),
                (MetricId.REACH, "content_type_reach", "Posts", 5600),
                (MetricId.REACH, "content_type_reach", "Stories", 1706),
                (MetricId.INTERACTIONS, "comment_sentiment", "Neutral", 18),
                (MetricId.INTERACTIONS, "comment_sentiment", "Positive", 15),
                (MetricId.INTERACTIONS, "comment_sentiment", "Negative", 5),
                (MetricId.VIEWS, "story_views", "Views", 4000),
                (MetricId.REACH, "story_reach", "Reach", 3200),
                (MetricId.INTERACTIONS, "story_interactions", "Interactions", 3220),
                (MetricId.INTERACTIONS, "story_replies", "Replies", 8),
                (MetricId.INTERACTIONS, "story_completion_rate", "Completion", 18.7),
                (MetricId.INTERACTIONS, "story_navigation", "Forward", 1950),
                (MetricId.INTERACTIONS, "story_navigation", "Back", 420),
                (MetricId.INTERACTIONS, "story_navigation", "Next Story", 570),
                (MetricId.INTERACTIONS, "story_navigation", "Exited", 283),
                (MetricId.INTERACTIONS, "story_actions", "Replies", 31),
                (MetricId.INTERACTIONS, "story_actions", "Profile Visits", 18),
                (MetricId.INTERACTIONS, "story_actions", "Sticker Taps", 20),
                (MetricId.INTERACTIONS, "story_actions", "Shares", 8),
            )
        )
        instagram_heatmap = tuple(
            _metric(
                21,
                "101",
                PlatformId.INSTAGRAM,
                recent,
                MetricId.INTERACTIONS,
                max(1, (13 - abs(hour - (16 + (day_index % 2) * 2))) * (day_index + 3)),
                "best_time_to_engage",
                f"{day}|{hour}",
            )
            for day_index, day in enumerate(days)
            for hour in range(0, 24, 2)
        )
        self.accounts = (
            ReportingAccount(
                11,
                "101",
                PlatformId.FACEBOOK,
                "page-101",
                "Demo Resort Facebook",
                "active",
                "connected",
                "healthy",
                "complete",
                True,
                synced_at,
            ),
            ReportingAccount(
                12,
                "102",
                PlatformId.FACEBOOK,
                "page-102",
                "Demo City Facebook",
                "active",
                "connected",
                "healthy",
                "complete",
                True,
                synced_at,
            ),
            ReportingAccount(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "profile-101",
                "Demo Resort Instagram",
                "active",
                "connected",
                "healthy",
                "complete",
                True,
                synced_at,
            ),
            ReportingAccount(
                31,
                "101",
                PlatformId.TIKTOK,
                "account-101",
                "Demo Resort TikTok",
                "active",
                "connected",
                "healthy",
                "complete",
                False,
                synced_at,
            ),
        )
        self.metrics = (
            *facebook_history,
            *instagram_history,
            *tiktok_history,
            *facebook_audience,
            *facebook_card_breakdowns,
            *instagram_audience,
            *instagram_card_breakdowns,
            *instagram_heatmap,
            *tiktok_audience,
        )
        self.content = (
            ReportingContent(
                11,
                "101",
                PlatformId.FACEBOOK,
                "demo-fb-post",
                "image",
                "https://example.test/demo-fb-post",
                "A quiet morning by the pool. #Antalya #Travel",
                "/branding/follower-avatar-5.jpg",
                now - timedelta(days=2),
                418,
                37,
                22,
            ),
            ReportingContent(
                11,
                "101",
                PlatformId.FACEBOOK,
                "demo-fb-video",
                "video",
                "https://example.test/demo-fb-video",
                "A day by the Mediterranean. #Mediterranean #Travel",
                "/branding/follower-avatar-9.jpg",
                now - timedelta(days=6),
                355,
                29,
                41,
            ),
            ReportingContent(
                11,
                "101",
                PlatformId.FACEBOOK,
                "demo-fb-carousel",
                "carousel",
                "https://example.test/demo-fb-carousel",
                "Seven reasons to visit Antalya. #Antalya #Holiday",
                "/branding/follower-avatar-12.jpg",
                now - timedelta(days=10),
                292,
                24,
                36,
            ),
            ReportingContent(
                11,
                "101",
                PlatformId.FACEBOOK,
                "demo-fb-link",
                "link",
                "https://example.test/demo-fb-link",
                "Plan your next seaside escape. #Travel #Summer",
                "/branding/follower-avatar-5.jpg",
                now - timedelta(days=15),
                228,
                18,
                31,
            ),
            ReportingContent(
                11,
                "101",
                PlatformId.FACEBOOK,
                "demo-fb-post-2",
                "image",
                "https://example.test/demo-fb-post-2",
                "Dinner with a sunset view.",
                "/branding/follower-avatar-9.jpg",
                now - timedelta(days=21),
                336,
                26,
                44,
            ),
            ReportingContent(
                11,
                "101",
                PlatformId.FACEBOOK,
                "demo-fb-post-3",
                "image",
                "https://example.test/demo-fb-post-3",
                "Your summer story starts here.",
                "/branding/follower-avatar-12.jpg",
                now - timedelta(days=27),
                271,
                20,
                29,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-post",
                "reel",
                "https://example.test/demo-ig-post",
                "Sunset from the terrace. #Sunset #Antalya",
                "/branding/follower-avatar-9.jpg",
                now - timedelta(days=3),
                912,
                64,
                118,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-carousel",
                "carousel",
                "https://example.test/demo-ig-carousel",
                "A taste of the Mediterranean. #Mediterranean #Food",
                "/branding/follower-avatar-5.jpg",
                now - timedelta(days=7),
                810,
                51,
                94,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-image",
                "image",
                "https://example.test/demo-ig-image",
                "Poolside mornings are the best. #Poolside #Holiday",
                "/branding/follower-avatar-12.jpg",
                now - timedelta(days=12),
                704,
                43,
                76,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-reel-2",
                "reel",
                "https://example.test/demo-ig-reel-2",
                "Twenty seconds of holiday calm. #Reels #Travel",
                "/branding/follower-avatar-9.jpg",
                now - timedelta(days=18),
                1050,
                72,
                136,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-image-2",
                "image",
                "https://example.test/demo-ig-image-2",
                "Meet us where the sea meets the sky. #Sea #Summer",
                "/branding/follower-avatar-5.jpg",
                now - timedelta(days=25),
                642,
                38,
                69,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-story",
                "story",
                "https://example.test/demo-ig-story",
                "Today by the beach.",
                "/branding/follower-avatar-12.jpg",
                now - timedelta(days=1),
                164,
                12,
                28,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-story-2",
                "story",
                "https://example.test/demo-ig-story-2",
                "Chef's special tonight.",
                "/branding/follower-avatar-5.jpg",
                now - timedelta(days=5),
                143,
                9,
                21,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-story-3",
                "story",
                "https://example.test/demo-ig-story-3",
                "Golden hour on the terrace.",
                "/branding/follower-avatar-9.jpg",
                now - timedelta(days=11),
                181,
                15,
                34,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "demo-ig-story-4",
                "story",
                "https://example.test/demo-ig-story-4",
                "Morning swim, anyone?",
                "/branding/follower-avatar-12.jpg",
                now - timedelta(days=20),
                132,
                8,
                19,
            ),
            ReportingContent(
                31,
                "101",
                PlatformId.TIKTOK,
                "demo-tt-video",
                "video",
                "https://example.test/demo-tt-video",
                "A day at Demo Resort.",
                "",
                now - timedelta(days=4),
                2240,
                143,
                305,
            ),
            ReportingContent(
                31,
                "101",
                PlatformId.TIKTOK,
                "demo-tt-video-2",
                "video",
                "https://example.test/demo-tt-video-2",
                "Summer moments by the sea.",
                "",
                now - timedelta(days=7),
                1840,
                96,
                218,
            ),
            ReportingContent(
                31,
                "101",
                PlatformId.TIKTOK,
                "demo-tt-video-3",
                "video",
                "https://example.test/demo-tt-video-3",
                "A perfect morning in Antalya.",
                "",
                now - timedelta(days=12),
                1510,
                72,
                164,
            ),
            ReportingContent(
                31,
                "101",
                PlatformId.TIKTOK,
                "demo-tt-video-4",
                "video",
                "https://example.test/demo-tt-video-4",
                "Behind the scenes with our team.",
                "",
                now - timedelta(days=18),
                1280,
                58,
                121,
            ),
            ReportingContent(
                31,
                "101",
                PlatformId.TIKTOK,
                "demo-tt-video-5",
                "video",
                "https://example.test/demo-tt-video-5",
                "Sunset dining by the beach.",
                "",
                now - timedelta(days=26),
                1120,
                41,
                95,
            ),
            ReportingContent(
                31,
                "101",
                PlatformId.TIKTOK,
                "demo-tt-video-6",
                "video",
                "https://example.test/demo-tt-video-6",
                "Your next holiday starts here.",
                "",
                now - timedelta(days=44),
                980,
                36,
                81,
            ),
        )
        self.comments = (
            ReportingComment(
                11,
                PlatformId.FACEBOOK,
                "demo-fb-post",
                "demo-comment-1",
                "Demo Guest",
                "Beautiful view!",
                12,
                1,
                True,
                now - timedelta(days=2),
            ),
            ReportingComment(
                21,
                PlatformId.INSTAGRAM,
                "demo-ig-post",
                "demo-comment-2",
                "Demo Traveler",
                "Adding this to my list.",
                21,
                0,
                False,
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
                1,
                "101",
                11,
                PlatformId.FACEBOOK,
                "daily",
                "completed",
                synced_at,
                synced_at,
                synced_at + timedelta(minutes=2),
                None,
            ),
        )
        self.insights = (
            ReportingInsight(
                1,
                "101",
                "completed",
                previous,
                today,
                "Reach and follower momentum are positive across the demo channels.",
                "Test the account and date filters, then export a dashboard PNG.",
                now - timedelta(minutes=10),
                now - timedelta(minutes=9),
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

    def list_connections(self, *, brand_ids: tuple[str, ...]) -> tuple[ReportingConnection, ...]:
        return tuple(row for row in self.connections if row.brand_id in brand_ids)

    def list_sync_jobs(self, *, brand_ids: tuple[str, ...]) -> tuple[ReportingSyncJob, ...]:
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
    database_backed = bool(os.getenv("SOCIAL_DB_URL", "").strip())
    authority = LocalDemoAuthority(database_backed=database_backed)
    reporting = None if database_backed else LocalDemoReporting()
    media_root = Path(os.getenv("SOCIAL_MEDIA_STORAGE_ROOT", "").strip() or Path.cwd())
    application = create_app(store=authority, reporting_store=reporting, media_root=media_root)
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

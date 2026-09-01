from __future__ import annotations

import hashlib
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import COOKIE_NAME
from app.application.ports import AiSummaryLimitStatus
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
from app.application.queries import (
    DashboardQuery,
    build_overview_dashboard,
    build_platform_dashboard,
)
from app.application.queries.dashboard_aggregation import (
    best_time_to_engage_breakdown,
    comment_sentiment_breakdown,
    source_breakdown,
    top_hashtags,
)
from app.core.security import sha256_text
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.domain.reporting import DataStatus, ReportingRange
from app.main import create_app

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)


class FakeAiSummary:
    provider_configured = True

    def __init__(self) -> None:
        self.generated: list[tuple[str, str, str]] = []

    def limit_status(self, *, brand_id: str) -> AiSummaryLimitStatus:
        return AiSummaryLimitStatus(
            provider_configured=True,
            can_generate=True,
            reason="available",
            weekly_limit=1,
            used=0,
            remaining=1,
            window_days=7,
            last_generated_at=None,
            next_available_at=None,
            generation_in_progress=False,
        )

    async def generate(
        self,
        *,
        brand_id: str,
        user_sub: str,
        range_key: str,
        start_on=None,
        end_on=None,
    ) -> ReportingInsight:
        del start_on, end_on
        self.generated.append((brand_id, user_sub, range_key))
        return ReportingInsight(
            2,
            brand_id,
            "completed",
            date(2026, 7, 1),
            date(2026, 7, 30),
            "Generated summary",
            "[]",
            NOW,
            NOW,
            connector_analysis="[]",
            anomalies="[]",
            platform_evaluations="[]",
            model="test-model",
            created_by_user_sub=user_sub,
        )


class MemoryAuthority:
    def __init__(self, raw_session: str = "phase6-session") -> None:
        self.raw_session = raw_session
        self.jtis: set[str] = set()
        self.sessions = {
            sha256_text(raw_session): {
                "user_id": "user-1",
                "brand_id": "101",
                "brand_scope": {
                    "version": "v1",
                    "default_brand_id": "101",
                    "brands": [
                        {
                            "brand_id": "100",
                            "name": "Parent Brand",
                            "parent_brand_id": None,
                            "visibility": "hidden_parent",
                            "access_mode": None,
                            "role": None,
                        },
                        {
                            "brand_id": "101",
                            "name": "Child A",
                            "parent_brand_id": "100",
                            "visibility": "active",
                            "access_mode": "write",
                            "role": "agency_admin",
                        },
                        {
                            "brand_id": "102",
                            "name": "Child B",
                            "parent_brand_id": "100",
                            "visibility": "active",
                            "access_mode": "read",
                            "role": "viewer",
                        },
                    ],
                },
                "role": "agency_admin",
                "access_mode": "write",
                "settings_visible": True,
                "is_internal_staff": True,
                "permissions": ("social.connection.manage", "tiktok.connection.manage"),
                "revoked": False,
                "sso_jti_hash": sha256_text("phase6-jti"),
            }
        }
        self.projections = {
            "v2:brand-shell:100": {
                "active": True,
                "brand_id": "100",
                "name": "Parent Brand",
                "parent_brand_id": None,
                "placeholder": False,
            },
            "v2:brand-shell:101": {
                "active": True,
                "brand_id": "101",
                "name": "Child A",
                "parent_brand_id": "100",
                "placeholder": False,
            },
            "v2:brand-shell:102": {
                "active": True,
                "brand_id": "102",
                "name": "Child B",
                "parent_brand_id": "100",
                "placeholder": False,
            },
            "v2:brand-shell:999": {
                "active": True,
                "brand_id": "999",
                "name": "Other Brand",
                "parent_brand_id": None,
                "placeholder": False,
            },
            "v2:brand-access:user-1:101": {
                "access_mode": "write",
                "active": True,
                "authority_source": "full_snapshot",
                "brand_id": "101",
                "role": "agency_admin",
                "user_id": "user-1",
            },
            "v2:brand-access:user-1:102": {
                "access_mode": "read",
                "active": True,
                "authority_source": "full_snapshot",
                "brand_id": "102",
                "role": "viewer",
                "user_id": "user-1",
            },
        }

    def get_session(self, session_hash: str) -> Mapping[str, Any] | None:
        return self.sessions.get(session_hash)

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

    def revoke_session(self, session_hash: str) -> None:
        if session_hash in self.sessions:
            self.sessions[session_hash]["revoked"] = True

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None:
        return self.projections.get(entity_key)

    def list_projections(self, projection_key_prefix: str) -> list[Mapping[str, Any]]:
        return [
            value
            for key, value in sorted(self.projections.items())
            if key.startswith(projection_key_prefix)
        ]


class MemoryReporting:
    def __init__(self, media_path: Path) -> None:
        self.accounts = (
            ReportingAccount(
                11,
                "101",
                PlatformId.FACEBOOK,
                "fb-a",
                "Facebook A",
                "active",
                "connected",
                "healthy",
                "ready",
                True,
                datetime(2026, 7, 14, 8, tzinfo=UTC),
            ),
            ReportingAccount(
                12,
                "102",
                PlatformId.FACEBOOK,
                "fb-b",
                "Facebook B",
                "active",
                "connected",
                "healthy",
                "ready",
                True,
                datetime(2026, 7, 14, 7, tzinfo=UTC),
            ),
            ReportingAccount(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "ig-a",
                "Instagram A",
                "active",
                "connected",
                "healthy",
                "ready",
                True,
                datetime(2026, 7, 14, 6, tzinfo=UTC),
            ),
            ReportingAccount(
                31,
                "102",
                PlatformId.TIKTOK,
                "tt-b",
                "TikTok B",
                "active",
                "pending_verification",
                "unknown",
                "pending",
                False,
                None,
            ),
        )
        self.metrics = (
            _metric(11, "101", PlatformId.FACEBOOK, date(2026, 7, 1), MetricId.FOLLOWERS, 100),
            _metric(11, "101", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.FOLLOWERS, 110),
            _metric(12, "102", PlatformId.FACEBOOK, date(2026, 7, 1), MetricId.FOLLOWERS, 200),
            _metric(12, "102", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.FOLLOWERS, 220),
            _metric(11, "101", PlatformId.FACEBOOK, date(2026, 7, 1), MetricId.REACH, 10),
            _metric(12, "102", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.REACH, 20),
            _metric(11, "101", PlatformId.FACEBOOK, date(2026, 6, 30), MetricId.FOLLOWERS, 90),
            _metric(12, "102", PlatformId.FACEBOOK, date(2026, 6, 30), MetricId.FOLLOWERS, 190),
            _metric(11, "101", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.INTERACTIONS, 8),
            _metric(21, "101", PlatformId.INSTAGRAM, date(2026, 7, 2), MetricId.FOLLOWERS, 300),
            _metric(21, "101", PlatformId.INSTAGRAM, date(2026, 7, 2), MetricId.REACH, 40),
            _metric(31, "102", PlatformId.TIKTOK, date(2026, 7, 1), MetricId.FOLLOWERS, 400),
            _metric(
                31, "102", PlatformId.TIKTOK, date(2026, 7, 1), MetricId.VIDEO_VIEWS_TOTAL, 1000
            ),
            _metric(
                31, "102", PlatformId.TIKTOK, date(2026, 7, 2), MetricId.VIDEO_VIEWS_TOTAL, 1100
            ),
            _metric(31, "102", PlatformId.TIKTOK, date(2026, 7, 2), MetricId.VIDEO_LIKES_TOTAL, 50),
            _metric(
                31,
                "102",
                PlatformId.TIKTOK,
                date(2026, 7, 2),
                MetricId.VIDEO_COMMENTS_TOTAL,
                5,
            ),
            _metric(31, "102", PlatformId.TIKTOK, date(2026, 7, 2), MetricId.VIDEO_SHARES_TOTAL, 5),
        )
        self.content = (
            ReportingContent(
                11,
                "101",
                PlatformId.FACEBOOK,
                "fb-post",
                "image",
                "https://example.test/fb-post",
                "Facebook post",
                "",
                datetime(2026, 7, 2, 8, tzinfo=UTC),
                5,
                2,
                1,
            ),
            ReportingContent(
                21,
                "101",
                PlatformId.INSTAGRAM,
                "ig-post",
                "image",
                "https://example.test/ig-post",
                "Instagram post",
                "/api/media/instagram/ig-post",
                datetime(2026, 7, 2, 9, tzinfo=UTC),
                7,
                1,
                2,
            ),
        )
        self.comments = (
            ReportingComment(
                11,
                PlatformId.FACEBOOK,
                "fb-post",
                "comment-1",
                "Person",
                "Hello",
                2,
                1,
                True,
                datetime(2026, 7, 2, 10, tzinfo=UTC),
            ),
        )
        payload = media_path.read_bytes()
        self.media = ReportingMedia(
            21,
            "101",
            PlatformId.INSTAGRAM,
            "ig-post",
            "cover",
            Path("instagram/ig-post.jpg"),
            "image/jpeg",
            len(payload),
            hashlib.sha256(payload).hexdigest(),
        )
        self.connections = (
            ReportingConnection(
                1,
                "102",
                PlatformId.TIKTOK,
                "pending_verification",
                None,
                datetime(2026, 7, 14, 1, tzinfo=UTC),
            ),
        )
        self.jobs = (
            ReportingSyncJob(
                1,
                "101",
                11,
                PlatformId.FACEBOOK,
                "initial_30d",
                "pending",
                datetime(2026, 7, 14, 1, tzinfo=UTC),
                None,
                None,
                None,
            ),
        )
        self.insights = (
            ReportingInsight(
                1,
                "101",
                "completed",
                date(2026, 7, 1),
                date(2026, 7, 2),
                "Summary",
                "Recommendation",
                datetime(2026, 7, 3, tzinfo=UTC),
                datetime(2026, 7, 3, 1, tzinfo=UTC),
            ),
        )

    def list_accounts(self, *, brand_ids, platform=None):
        return tuple(
            row
            for row in self.accounts
            if row.brand_id in brand_ids and (platform is None or row.platform is platform)
        )

    def list_metrics(self, *, account_ids, start_on, end_on):
        return tuple(
            row
            for row in self.metrics
            if row.account_id in account_ids and start_on <= row.observed_on <= end_on
        )

    def list_content(self, *, account_ids, start_on, end_on, content_type=None):
        return tuple(
            row
            for row in self.content
            if row.account_id in account_ids
            and row.published_at is not None
            and start_on <= row.published_at.date() <= end_on
            and (content_type is None or row.content_type == content_type)
        )

    def list_comments(self, *, account_ids, start_on, end_on):
        return tuple(
            row
            for row in self.comments
            if row.account_id in account_ids
            and row.commented_at is not None
            and start_on <= row.commented_at.date() <= end_on
        )

    def find_media(self, *, brand_ids, platform, external_content_id, account_id=None):
        row = self.media
        if (
            row.brand_id not in brand_ids
            or row.platform is not platform
            or row.external_content_id != external_content_id
            or (account_id is not None and row.account_id != account_id)
        ):
            return None
        return row

    def list_connections(self, *, brand_ids):
        return tuple(row for row in self.connections if row.brand_id in brand_ids)

    def list_sync_jobs(self, *, brand_ids):
        return tuple(row for row in self.jobs if row.brand_id in brand_ids)

    def list_insights(self, *, brand_ids, start_on=None, end_on=None):
        if (start_on is None) is not (end_on is None):
            raise ValueError("insight_range_incomplete")
        return tuple(row for row in self.insights if row.brand_id in brand_ids)


def _metric(account_id, brand_id, platform, observed_on, metric_id, value):
    return ReportingMetric(
        account_id=account_id,
        brand_id=brand_id,
        platform=platform,
        observed_on=observed_on,
        metric_id=metric_id,
        value=float(value),
    )


@pytest.fixture()
def phase6_fixture(tmp_path: Path):
    media_path = tmp_path / "instagram" / "ig-post.jpg"
    media_path.parent.mkdir()
    media_path.write_bytes(b"phase6-media")
    return MemoryAuthority(), MemoryReporting(media_path), tmp_path


def test_platform_dashboard_rollup_respects_metric_semantics(phase6_fixture) -> None:
    _, reporting, _ = phase6_fixture
    reporting.metrics += (
        _metric(11, "101", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.VIEWS, 100),
        _metric(12, "102", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.VIEWS, 200),
    )
    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.FACEBOOK,
        query=DashboardQuery(
            requested_brand_id="100",
            resolved_brand_ids=("101", "102"),
            rollup=True,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
        ),
        now=NOW,
    )
    cards = {card.metric_id: card for card in dashboard.metrics}
    assert cards[MetricId.FOLLOWERS].value == 330
    assert cards[MetricId.FOLLOWERS].previous_value == 280
    assert cards[MetricId.REACH].value == 30
    assert cards[MetricId.ENGAGEMENT_RATE].value == pytest.approx(8 / 300)
    assert cards[MetricId.ENGAGEMENT_RATE].methodology == (
        "derived:ratio_from_components:v1:selected_period"
    )
    assert cards[MetricId.PAGE_VIEWS].value is None
    assert cards[MetricId.PAGE_VIEWS].data_status is DataStatus.UNAVAILABLE
    assert dashboard.meta.resolved_account_ids == (11, 12)
    assert dashboard.community.total_comments == 1


def test_preset_dashboard_uses_live_profile_and_audience_snapshots(
    phase6_fixture,
) -> None:
    _, reporting, _ = phase6_fixture
    reporting.metrics += (
        _metric(
            11,
            "101",
            PlatformId.FACEBOOK,
            date(2026, 7, 14),
            MetricId.FOLLOWERS,
            150,
        ),
        ReportingMetric(
            account_id=11,
            brand_id="101",
            platform=PlatformId.FACEBOOK,
            observed_on=date(2026, 7, 14),
            metric_id=MetricId.FOLLOWERS,
            value=90,
            breakdown_key="page_fans_country",
            breakdown_value="TR",
        ),
        ReportingMetric(
            account_id=11,
            brand_id="101",
            platform=PlatformId.FACEBOOK,
            observed_on=date(2026, 7, 13),
            metric_id=MetricId.VIEWS,
            value=25,
            breakdown_key="is_from_ads",
            breakdown_value="Organic",
        ),
        ReportingMetric(
            account_id=11,
            brand_id="101",
            platform=PlatformId.FACEBOOK,
            observed_on=date(2026, 7, 14),
            metric_id=MetricId.VIEWS,
            value=0,
            breakdown_key="is_from_ads",
            breakdown_value="Organic",
        ),
    )
    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.FACEBOOK,
        query=DashboardQuery(
            requested_brand_id="101",
            resolved_brand_ids=("101",),
            rollup=False,
            date_range=ReportingRange(date(2026, 6, 15), date(2026, 7, 13), "last_30_days"),
        ),
        now=NOW,
    )

    cards = {card.metric_id: card for card in dashboard.metrics}
    assert cards[MetricId.FOLLOWERS].value == 150
    assert any(
        row.dimension == "page_fans_country"
        and row.items[0].key == "TR"
        and row.items[0].value == 90
        for row in dashboard.breakdowns
    )
    assert dashboard.source_breakdown is not None
    assert dashboard.source_breakdown.views is not None
    assert dashboard.source_breakdown.views.organic == 25
    follower_series = next(row for row in dashboard.series if row.metric_id is MetricId.FOLLOWERS)
    assert all(point.observed_on <= date(2026, 7, 13) for point in follower_series.points)


def test_legacy_source_series_populate_selected_range_distribution() -> None:
    rows = tuple(
        ReportingMetric(
            account_id=11,
            brand_id="101",
            platform=PlatformId.FACEBOOK,
            observed_on=observed_on,
            metric_id=metric_id,
            value=value,
        )
        for observed_on, metric_id, value in (
            (date(2026, 7, 12), MetricId.VIEWS_ORGANIC, 20),
            (date(2026, 7, 13), MetricId.VIEWS_ORGANIC, 25),
            (date(2026, 7, 12), MetricId.VIEWS_PAID, 5),
            (date(2026, 7, 13), MetricId.VIEWS_PAID, 10),
            (date(2026, 7, 12), MetricId.REACH_ORGANIC, 18),
            (date(2026, 7, 13), MetricId.REACH_ORGANIC, 22),
        )
    )

    result = source_breakdown((), rows)

    assert result is not None
    assert result.paid_available is True
    assert result.views is not None
    assert result.views.organic == 45
    assert result.views.paid == 15
    assert result.reach is not None
    assert result.reach.organic == 40
    assert result.reach.paid is None


def test_comment_projection_hides_authors_and_masks_mentions(phase6_fixture) -> None:
    _, reporting, _ = phase6_fixture
    reporting.comments = (
        replace(
            reporting.comments[0],
            author_name="visible-user",
            text=("Hi @_kathistaggl_ @httpx.dilara and @okoeker2254. Mail me@example.com"),
        ),
    )

    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.FACEBOOK,
        query=DashboardQuery(
            requested_brand_id="101",
            resolved_brand_ids=("101",),
            rollup=False,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
        ),
        now=NOW,
    )

    assert dashboard.community.top_commenters[0].name == "Anonymous"
    liked = dashboard.community.top_liked_comments[0]
    assert liked.name == "Anonymous"
    assert liked.comment == ("Hi @_***_ @h***a and @o***4. Mail me@example.com")
    assert "visible-user" not in repr(dashboard.community)


def test_single_day_follower_flow_uses_prior_day_anchor_without_leaking_it(
    phase6_fixture,
) -> None:
    _, reporting, _ = phase6_fixture
    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.FACEBOOK,
        query=DashboardQuery(
            requested_brand_id="100",
            resolved_brand_ids=("101", "102"),
            rollup=True,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 1), "custom"),
        ),
        now=NOW,
    )

    cards = {card.metric_id: card for card in dashboard.metrics}
    assert cards[MetricId.FOLLOWERS].value == 300
    assert cards[MetricId.FOLLOWS].value == 20
    assert cards[MetricId.UNFOLLOWS].value == 0
    assert cards[MetricId.FOLLOWERS_NET].value == 20
    series = {row.metric_id: row for row in dashboard.series}
    assert [(point.observed_on, point.value) for point in series[MetricId.FOLLOWS].points] == [
        (date(2026, 7, 1), 20),
    ]

    with pytest.raises(ValueError, match="dashboard_account_scope_denied"):
        build_platform_dashboard(
            store=reporting,
            catalog=bootstrap_metric_catalog(),
            platform=PlatformId.FACEBOOK,
            query=replace(
                DashboardQuery(
                    requested_brand_id="101",
                    resolved_brand_ids=("101",),
                    rollup=False,
                    date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
                ),
                account_id=12,
            ),
            now=NOW,
        )


def test_tiktok_derived_counters_are_recomputed_without_fake_values(
    phase6_fixture,
) -> None:
    _, reporting, _ = phase6_fixture
    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.TIKTOK,
        query=DashboardQuery(
            requested_brand_id="102",
            resolved_brand_ids=("102",),
            rollup=False,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
        ),
        now=NOW,
    )
    cards = {card.metric_id: card for card in dashboard.metrics}
    assert cards[MetricId.VIDEO_VIEWS_TOTAL].value == 1100
    assert cards[MetricId.VIDEO_VIEWS_CHANGE].value == 100
    assert cards[MetricId.VIDEO_ENGAGEMENTS_TOTAL].value == 60
    assert cards[MetricId.VIDEO_ENGAGEMENTS_TOTAL].methodology == (
        "derived:sum_components:v1:same_sample"
    )
    assert cards[MetricId.VIDEO_ENGAGEMENT_RATE].value == pytest.approx(60 / 1100)
    assert cards[MetricId.VIDEO_ENGAGEMENT_RATE].data_status is DataStatus.AVAILABLE
    series = {item.metric_id: item for item in dashboard.series}
    assert series[MetricId.VIDEO_VIEWS_CHANGE].points[-1].value == 100
    assert series[MetricId.VIDEO_ENGAGEMENTS_TOTAL].points[-1].value == 60
    assert series[MetricId.VIDEO_ENGAGEMENT_RATE].points[-1].value == pytest.approx(60 / 1100)
    assert series[MetricId.VIDEO_ENGAGEMENTS_TOTAL].methodology == (
        "derived:sum_components:v1:same_sample"
    )


def test_overview_exposes_every_metric_consumed_by_its_frontend(phase6_fixture) -> None:
    _, reporting, _ = phase6_fixture
    reporting.metrics += (
        _metric(11, "101", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.VIEWS, 100),
        _metric(21, "101", PlatformId.INSTAGRAM, date(2026, 7, 2), MetricId.VIEWS, 200),
        _metric(31, "102", PlatformId.TIKTOK, date(2026, 7, 2), MetricId.VIEWS, 300),
        _metric(
            21,
            "101",
            PlatformId.INSTAGRAM,
            date(2026, 7, 2),
            MetricId.WEBSITE_CLICKS,
            12,
        ),
        _metric(11, "101", PlatformId.FACEBOOK, date(2026, 7, 2), MetricId.REACTIONS, 9),
    )
    dashboard = build_overview_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        query=DashboardQuery(
            requested_brand_id="100",
            resolved_brand_ids=("101", "102"),
            rollup=True,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
        ),
        now=NOW,
    )

    cards = {card.metric_id: card for card in dashboard.metrics}
    assert set(cards) == {
        MetricId.FOLLOWERS,
        MetricId.NEW_FOLLOWERS,
        MetricId.REACH,
        MetricId.VIEWS,
        MetricId.INTERACTIONS,
        MetricId.WEBSITE_CLICKS,
        MetricId.REACTIONS,
    }
    assert cards[MetricId.NEW_FOLLOWERS].value == 50
    assert cards[MetricId.VIEWS].value == 600
    assert cards[MetricId.WEBSITE_CLICKS].value == 12
    assert cards[MetricId.REACTIONS].value == 9


def test_content_metrics_compare_the_adjacent_equal_length_period(phase6_fixture) -> None:
    _, reporting, _ = phase6_fixture
    current = ReportingContent(
        11,
        "101",
        PlatformId.FACEBOOK,
        "fb-current-comparison",
        "image",
        "https://example.test/fb-current-comparison",
        "Current comparison post",
        "",
        datetime(2026, 7, 1, 8, tzinfo=UTC),
        15,
        4,
        3,
        views_count=200,
        reach_count=150,
    )
    previous = replace(
        current,
        external_content_id="fb-previous-comparison",
        permalink="https://example.test/fb-previous-comparison",
        published_at=datetime(2026, 6, 30, 8, tzinfo=UTC),
        likes_count=10,
        comments_count=3,
        shares_count=2,
        views_count=100,
        reach_count=80,
    )
    reporting.content += (current, previous)

    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.FACEBOOK,
        query=DashboardQuery(
            requested_brand_id="101",
            resolved_brand_ids=("101",),
            rollup=False,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
        ),
        now=NOW,
    )

    # Current totals include the fixture's July 2 post. The previous comparison
    # is exactly June 29-30 and therefore includes only the previous row above.
    comparisons = dashboard.content_metrics
    assert (comparisons.views.value, comparisons.views.previous_value) == (200, 100)
    assert comparisons.views.delta_pct == 100
    assert (comparisons.reach.value, comparisons.reach.previous_value) == (150, 80)
    assert comparisons.reach.delta_pct == pytest.approx(87.5)
    assert (comparisons.likes.value, comparisons.likes.previous_value) == (20, 10)
    assert comparisons.likes.delta_pct == 100
    assert (comparisons.comments.value, comparisons.comments.previous_value) == (6, 3)
    assert comparisons.comments.delta_pct == 100
    assert (comparisons.shares.value, comparisons.shares.previous_value) == (4, 2)
    assert comparisons.shares.delta_pct == 100
    assert (comparisons.interactions.value, comparisons.interactions.previous_value) == (30, 15)
    assert comparisons.interactions.delta_pct == 100
    assert comparisons.engagement_rate.value == pytest.approx(0.15)
    assert comparisons.engagement_rate.previous_value == pytest.approx(0.15)
    assert comparisons.engagement_rate.delta_pct == pytest.approx(0)


def test_instagram_structured_stories_preserve_content_level_metrics(
    phase6_fixture,
) -> None:
    _, reporting, _ = phase6_fixture
    current = ReportingContent(
        21,
        "101",
        PlatformId.INSTAGRAM,
        "ig-story-current",
        "story",
        "https://example.test/ig-story-current",
        "Current story",
        "https://cdn.example.test/ig-story-current.mp4",
        datetime(2026, 7, 2, 11, tzinfo=UTC),
        3,
        2,
        4,
        views_count=120,
        reach_count=90,
        cover_url="https://cdn.example.test/ig-story-current-thumbnail.jpg",
        interactions_count=25,
        replies_count=2,
        profile_visits=7,
        follows_count=3,
        taps_forward=11,
        taps_back=2,
        swipe_forward=4,
        exits=3,
        navigation_count=20,
        completion_rate=76.5,
    )
    previous = replace(
        current,
        external_content_id="ig-story-previous",
        permalink="https://example.test/ig-story-previous",
        published_at=datetime(2026, 6, 30, 11, tzinfo=UTC),
        views_count=100,
        reach_count=80,
        completion_rate=70.0,
    )
    reporting.content += (current, previous)
    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.INSTAGRAM,
        query=DashboardQuery(
            requested_brand_id="101",
            resolved_brand_ids=("101",),
            rollup=False,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
        ),
        now=NOW,
    )

    assert dashboard.stories is not None
    assert dashboard.stories.data_status is DataStatus.AVAILABLE
    assert dashboard.stories.summary.views == 120
    assert dashboard.stories.previous_summary.views == 100
    assert dashboard.stories.trend.views == (0.0, 120.0)
    assert dashboard.stories.navigation.taps_forward == 11
    assert dashboard.stories.actions.profile_visits == 7
    assert dashboard.stories.items[0].views == 120
    assert dashboard.stories.items[0].cover_url.endswith("-thumbnail.jpg")
    assert dashboard.stories.items[0].data_status is DataStatus.AVAILABLE


def test_instagram_story_trend_keeps_known_days_when_one_story_is_unavailable(
    phase6_fixture,
) -> None:
    _, reporting, _ = phase6_fixture
    known = ReportingContent(
        21,
        "101",
        PlatformId.INSTAGRAM,
        "ig-story-known",
        "story",
        "https://example.test/ig-story-known",
        "Known story",
        "",
        datetime(2026, 7, 1, 11, tzinfo=UTC),
        3,
        2,
        1,
        views_count=120,
        reach_count=90,
    )
    unavailable = replace(
        known,
        external_content_id="ig-story-unavailable",
        permalink="https://example.test/ig-story-unavailable",
        published_at=datetime(2026, 7, 2, 11, tzinfo=UTC),
        views_count=None,
        reach_count=None,
    )
    reporting.content += (known, unavailable)
    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.INSTAGRAM,
        query=DashboardQuery(
            requested_brand_id="101",
            resolved_brand_ids=("101",),
            rollup=False,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
            content_type="story",
        ),
        now=NOW,
    )

    assert dashboard.stories is not None
    assert dashboard.stories.trend.views == (120.0, None)
    assert dashboard.stories.trend.reach == (90.0, None)
    assert dashboard.stories.trend.data_status is DataStatus.PARTIAL


def test_instagram_story_preset_includes_today_live_story_without_extending_trend(
    phase6_fixture,
) -> None:
    _, reporting, _ = phase6_fixture
    older = ReportingContent(
        21,
        "101",
        PlatformId.INSTAGRAM,
        "ig-story-yesterday",
        "story",
        "https://example.test/ig-story-yesterday",
        "Yesterday's story",
        "https://cdn.example.test/ig-story-yesterday.jpg",
        datetime(2026, 7, 13, 11, tzinfo=UTC),
        0,
        0,
        0,
        views_count=20,
        reach_count=15,
    )
    live = replace(
        older,
        external_content_id="ig-story-live-today",
        permalink="https://example.test/ig-story-live-today",
        message="Today's live story",
        media_url="https://cdn.example.test/ig-story-live-today.jpg",
        published_at=datetime(2026, 7, 14, 10, tzinfo=UTC),
        views_count=7,
        reach_count=5,
    )
    # Deliberately oldest first: the aggregation contract, rather than a store
    # implementation detail, guarantees which item is the Latest Story.
    reporting.content += (older, live)

    dashboard = build_platform_dashboard(
        store=reporting,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.INSTAGRAM,
        query=DashboardQuery(
            requested_brand_id="101",
            resolved_brand_ids=("101",),
            rollup=False,
            date_range=ReportingRange(
                date(2026, 6, 14), date(2026, 7, 13), "last_30_days"
            ),
            content_type="story",
        ),
        now=NOW,
    )

    assert dashboard.stories is not None
    assert [item.content_id for item in dashboard.stories.items] == [
        "ig-story-live-today",
        "ig-story-yesterday",
    ]
    assert dashboard.stories.trend.labels[-1] == date(2026, 7, 13)
    assert dashboard.stories.trend.views[-1] == 20


def test_best_time_to_engage_uses_average_content_engagement_in_istanbul_time() -> None:
    first = ReportingContent(
        11,
        "101",
        PlatformId.FACEBOOK,
        "post-1",
        "post",
        "https://example.test/post-1",
        "First",
        "",
        # Monday 10:00 in Europe/Istanbul.
        datetime(2026, 7, 6, 7, 15, tzinfo=UTC),
        4,
        3,
        3,
    )
    second = replace(
        first,
        external_content_id="post-2",
        permalink="https://example.test/post-2",
        published_at=datetime(2026, 7, 6, 8, 30, tzinfo=UTC),
        interactions_count=30,
    )
    story = replace(
        first,
        external_content_id="story-1",
        content_type="story",
        published_at=datetime(2026, 7, 6, 7, 45, tzinfo=UTC),
        interactions_count=1000,
    )

    result = best_time_to_engage_breakdown(
        PlatformId.FACEBOOK,
        (first, second, story),
    )

    assert result is not None
    assert result.dimension == "best_time_to_engage"
    assert [(item.key, item.value) for item in result.items] == [("Mon|10", 20.0)]


def test_best_time_to_engage_supports_tiktok_video_content() -> None:
    video = ReportingContent(
        31,
        "102",
        PlatformId.TIKTOK,
        "video-1",
        "video",
        "https://example.test/video-1",
        "Video",
        "",
        # Saturday 18:00 in Europe/Istanbul.
        datetime(2026, 7, 4, 15, 20, tzinfo=UTC),
        12,
        3,
        1,
    )

    result = best_time_to_engage_breakdown(PlatformId.TIKTOK, (video,))

    assert result is not None
    assert [(item.key, item.value) for item in result.items] == [("Sat|18", 16.0)]


def test_top_hashtags_normalizes_meta_punctuation_and_counts_posts() -> None:
    first = ReportingContent(
        11,
        "101",
        PlatformId.FACEBOOK,
        "post-1",
        "post",
        "https://example.test/post-1",
        "#AquaMICE. #Hotel #hotel #İstanbul!",
        "",
        NOW,
        0,
        0,
        0,
    )
    second = replace(
        first,
        external_content_id="post-2",
        message="#aquamice #HOTEL #summer_2026",
    )

    assert [(item.name, item.count) for item in top_hashtags((first, second))] == [
        ("#aquamice", 2),
        ("#hotel", 2),
        ("#i̇stanbul", 1),
        ("#summer_2026", 1),
    ]


def test_comment_sentiment_breakdown_uses_current_classified_comments() -> None:
    first = ReportingComment(
        11,
        PlatformId.FACEBOOK,
        "post-1",
        "comment-1",
        "Person",
        "Great",
        0,
        0,
        False,
        NOW,
        "positive",
    )
    rows = (
        first,
        replace(first, external_comment_id="comment-2", sentiment="negative"),
        replace(first, external_comment_id="comment-3", sentiment="positive"),
        replace(first, external_comment_id="comment-4", sentiment=None),
    )

    result = comment_sentiment_breakdown(rows)

    assert result is not None
    assert result.dimension == "comment_sentiment"
    assert [(item.key, item.value, item.percentage) for item in result.items] == [
        ("Positive", 2.0, pytest.approx(200 / 3)),
        ("Negative", 1.0, pytest.approx(100 / 3)),
    ]


@pytest.mark.asyncio
async def test_instagram_content_tab_excludes_stories_from_every_content_projection(
    phase6_fixture,
) -> None:
    authority, reporting, media_root = phase6_fixture
    reporting.content += (
        ReportingContent(
            21,
            "101",
            PlatformId.INSTAGRAM,
            "ig-story-focused-scope",
            "story",
            "https://example.test/ig-story-focused-scope",
            "Focused story",
            "",
            datetime(2026, 7, 2, 11, tzinfo=UTC),
            3,
            2,
            1,
            views_count=120,
            reach_count=90,
        ),
    )
    app = create_app(authority, reporting, media_root)
    cookies = {COOKIE_NAME: authority.raw_session}
    params = {
        "brand_id": "101",
        "start_date": "2026-07-01",
        "end_date": "2026-07-02",
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        cover = await client.get("/api/dashboards/instagram", params={**params, "tab": "cover"})
        content = await client.get("/api/dashboards/instagram", params={**params, "tab": "content"})
        stories = await client.get("/api/dashboards/instagram", params={**params, "tab": "stories"})

    assert cover.status_code == content.status_code == stories.status_code == 200
    assert {item["content_type"] for item in cover.json()["content"]} == {"image", "story"}
    assert cover.json()["content_metrics"]["likes"]["value"] == 7
    assert [item["content_type"] for item in content.json()["content"]] == ["image"]
    assert content.json()["content_metrics"]["likes"]["value"] == 7
    assert [item["name"] for item in content.json()["content_summary"]["by_type"]] == ["Image"]
    assert [item["content_type"] for item in stories.json()["content"]] == ["story"]


def test_phase6_openapi_publishes_typed_response_contracts() -> None:
    schema = create_app().openapi()
    expected = {
        "/api/dashboards/overview": "OverviewDashboard",
        "/api/dashboards/facebook": "PlatformDashboard",
        "/api/dashboards/instagram": "PlatformDashboard",
        "/api/dashboards/tiktok": "PlatformDashboard",
        "/api/dashboards/x": "PlatformDashboard",
        "/api/dashboards/linkedin": "PlatformDashboard",
        "/api/dashboards/youtube": "PlatformDashboard",
        "/api/platforms/facebook/accounts": "PlatformAccountsResponse",
        "/api/platforms/instagram/accounts": "PlatformAccountsResponse",
        "/api/platforms/tiktok/accounts": "PlatformAccountsResponse",
        "/api/platforms/x/accounts": "PlatformAccountsResponse",
        "/api/platforms/linkedin/accounts": "PlatformAccountsResponse",
        "/api/platforms/youtube/accounts": "PlatformAccountsResponse",
        "/api/settings/brands": "SettingsBrandsResponse",
        "/api/settings/social-accounts": "SocialAccountsResponse",
        "/api/settings/brand-links": "BrandLinksResponse",
        "/api/settings/connections": "ConnectionsResponse",
        "/api/settings/sync-jobs": "SyncJobsResponse",
        "/api/settings/audit": "AuditResponse",
        "/api/settings/tiktok/connection": "TikTokConnectionResponse",
        "/api/settings/tiktok/activation-readiness": "TikTokActivationReadinessResponse",
        "/api/insights": "InsightsResponse",
        "/api/insights/limit": "AiSummaryLimitResponse",
        "/api/operations/readiness": "OperationsReadinessResponse",
        "/api/reports/xlsx/{job_id}": "ReportJobResponse",
        "/api/workspace/capabilities": "WorkspaceCapabilitiesResponse",
    }
    for path, model in expected.items():
        response_schema = schema["paths"][path]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert response_schema == {"$ref": f"#/components/schemas/{model}"}
    generation_schema = schema["paths"]["/api/insights/generate"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]
    assert generation_schema == {"$ref": "#/components/schemas/ReportingInsight"}
    components = schema["components"]["schemas"]
    assert {"semantic_type", "data_status"}.issubset(components["DashboardMetric"]["required"])
    assert {"methodology", "availability_reason"}.issubset(
        components["DashboardMetric"]["required"]
    )
    assert {
        "top_hashtags",
        "content_summary",
        "content_metrics",
        "source_breakdown",
        "metric_methodology",
        "audience_capabilities",
        "stories",
    }.issubset(components["PlatformDashboard"]["required"])
    assert {
        "views",
        "reach",
        "cover_candidates",
        "data_status",
    }.issubset(components["DashboardContent"]["required"])
    assert {"requested_brand_id", "resolved_brand_ids", "resolved_account_ids"}.issubset(
        components["DashboardMeta"]["required"]
    )
    assert set(components["PlatformId"]["enum"]) == PlatformId.exact_set()


@pytest.mark.asyncio
async def test_phase6_routes_are_scoped_read_only_and_honest(phase6_fixture) -> None:
    authority, reporting, media_root = phase6_fixture
    app = create_app(authority, reporting, media_root)
    cookies = {COOKIE_NAME: authority.raw_session}
    before = (authority.sessions.copy(), authority.projections.copy())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        facebook = await client.get(
            "/api/dashboards/facebook",
            params={
                "brand_id": "100",
                "rollup": "true",
                "start_date": "2026-07-01",
                "end_date": "2026-07-02",
            },
        )
        assert facebook.status_code == 200
        body = facebook.json()
        assert body["meta"]["resolved_brand_ids"] == ["101", "102"]
        assert body["audience_capabilities"]["age_gender"] == "provider_unavailable"
        assert body["audience_capabilities"]["activity"] == "provider_unavailable"
        assert body["stories"] is None
        assert body["content"][0]["views"] is None
        assert body["content"][0]["data_status"] == "partial"
        assert body["metrics"][0]["methodology"]
        assert {row["metric_id"]: row["value"] for row in body["metrics"]}[
            MetricId.FOLLOWERS.value
        ] == 330
        assert (
            await client.get(
                "/api/dashboards/facebook",
                params={
                    "brand_id": "999",
                    "start_date": "2026-07-01",
                    "end_date": "2026-07-02",
                },
            )
        ).status_code == 403
        accounts = await client.get(
            "/api/platforms/facebook/accounts",
            params={"brand_id": "100", "rollup": "true"},
        )
        assert [item["account_id"] for item in accounts.json()["accounts"]] == [11, 12]
        capabilities = await client.get(
            "/api/workspace/capabilities",
            params={"selected_brand_id": "100", "rollup": "true"},
        )
        assert capabilities.status_code == 200
        assert capabilities.json()["permissions"]["operation_mutation_available"] is False
        assert {
            item["platform"]: (item["linked_account_count"], item["navigation_available"])
            for item in capabilities.json()["platforms"]
        } == {
            "facebook": (2, True),
            "instagram": (1, True),
            "tiktok": (1, True),
            "x": (0, False),
            "linkedin": (0, False),
            "youtube": (0, False),
        }
        readiness = await client.get(
            "/api/operations/readiness",
            params={"brand_id": "100", "rollup": "true"},
        )
        assert readiness.status_code == 200
        assert {
            item["platform"]: item["account_count"] for item in readiness.json()["platforms"]
        } == {
            "facebook": 2,
            "instagram": 1,
            "tiktok": 1,
            "x": 0,
            "linkedin": 0,
            "youtube": 0,
        }
        assert (
            await client.get(
                "/api/settings/social-accounts",
                params={"brand_id": "100", "rollup": "true"},
            )
        ).status_code == 200
        connection = await client.get(
            "/api/settings/tiktok/connection",
            params={"brand_id": "102"},
        )
        assert connection.json()["state"] == "pending_verification"
        assert "token" not in connection.text.lower()
        insights = await client.get("/api/insights", params={"brand_id": "101"})
        assert insights.json()["items"][0]["summary"] == "Summary"
        media = await client.get(
            "/api/media/instagram/ig-post",
            params={"brand_id": "101", "account_id": 21},
        )
        assert media.status_code == 200
        assert media.content == b"phase6-media"
        blocked = await client.post(
            "/api/operations/sync",
            params={"brand_id": "101", "platform": "facebook", "account_id": 11},
            headers={"Origin": "http://test"},
        )
        assert blocked.status_code == 403
        assert blocked.json() == {"detail": "writes_disabled"}

        authority.sessions[sha256_text(authority.raw_session)]["role"] = "agency_operator"
        authority.sessions[sha256_text(authority.raw_session)]["settings_visible"] = False
        denied = await client.get("/api/settings/brands", params={"brand_id": "101"})
        assert denied.status_code == 403
        authority.sessions[sha256_text(authority.raw_session)]["role"] = "agency_admin"
        authority.sessions[sha256_text(authority.raw_session)]["settings_visible"] = True

    assert authority.sessions == before[0]
    assert authority.projections == before[1]


@pytest.mark.asyncio
async def test_ai_summary_generation_requires_app_role_and_scoped_brand_authority(
    phase6_fixture,
) -> None:
    authority, reporting, media_root = phase6_fixture
    runtime = FakeAiSummary()
    app = create_app(authority, reporting, media_root, ai_summary=runtime)
    session = authority.sessions[sha256_text(authority.raw_session)]
    cookies = {COOKIE_NAME: authority.raw_session}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test", cookies=cookies
    ) as client:
        denied = await client.get("/api/insights/limit", params={"brand_id": "101"})
        assert denied.status_code == 403

        session.update(
            {
                "role": "viewer",
                "app_role": "operator",
                "source_system": "accumulate",
                "access_mode": "read",
            }
        )
        session["brand_scope"]["brands"][1].update({"role": "viewer", "access_mode": "read"})
        authority.projections["v2:brand-access:user-1:101"].update(
            {"role": "viewer", "access_mode": "read"}
        )

        limit = await client.get("/api/insights/limit", params={"brand_id": "101"})
        assert limit.status_code == 200
        assert limit.json()["weekly_limit"] == 1
        assert limit.json()["window_days"] == 7

        missing_origin = await client.post(
            "/api/insights/generate",
            params={"brand_id": "101", "range": "last_30_days"},
        )
        assert missing_origin.status_code == 403
        generated = await client.post(
            "/api/insights/generate",
            params={"brand_id": "101", "range": "last_30_days"},
            headers={"Origin": "http://test"},
        )
        assert generated.status_code == 200
        assert generated.json()["summary"] == "Generated summary"
        assert runtime.generated == [("101", "user-1", "last_30_days")]

        scoped_brand = await client.get("/api/insights/limit", params={"brand_id": "102"})
        assert scoped_brand.status_code == 200
        assert scoped_brand.json()["can_generate"] is True
        session["app_role"] = "admin"
        assert (
            await client.get("/api/insights/limit", params={"brand_id": "101"})
        ).status_code == 200
        session["app_role"] = "viewer"
        assert (
            await client.get("/api/insights/limit", params={"brand_id": "101"})
        ).status_code == 403


@pytest.mark.asyncio
async def test_signed_accumulate_viewer_operator_sso_reaches_ai_summary_limit(
    phase6_fixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority, reporting, media_root = phase6_fixture
    secret = "phase6-signed-sso-secret-with-32-bytes"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "development")
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("SOCIAL_DB_NAME", "social_media_v2_test")
    monkeypatch.setenv("SOCIAL_SSO_HS256_SECRET", secret)
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "iss": "accumulate",
            "sub": "signed-viewer-operator",
            "aud": "social_media",
            "token_type": "app_sso",
            "jti": "signed-viewer-operator-jti",
            "exp": int((now + timedelta(hours=1)).timestamp()),
            "sso_contract": {
                "version": "v1",
                "issued_at": now.isoformat(),
                "user_id": "signed-viewer-operator",
                "email": "viewer.operator@example.test",
                "brand_id": "101",
                "brand_name": "Child A",
                "brand_status": "active",
                "role": "viewer",
                "platform_role": "viewer",
                "effective_role": "operator",
                "app_role": "operator",
                "app_id": "social_media",
                "entitlement_status": "enabled",
                "access_mode": "read",
                "access_start_at": None,
                "access_expires_at": None,
                "allowed_apps": ["social_media"],
                "is_internal_staff": False,
                "settings_visible": False,
                "platform_branch_scope_mode": "all",
                "platform_branches": [],
            },
        },
        secret,
        algorithm="HS256",
    )
    runtime = FakeAiSummary()
    app = create_app(authority, reporting, media_root, ai_summary=runtime)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        follow_redirects=False,
    ) as client:
        consumed = await client.get("/sso/consume", params={"token": token})
        assert consumed.status_code == 303
        me = await client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["role"] == "viewer"
        assert me.json()["app_role"] == "operator"
        assert me.json()["settings_visible"] is False
        assert me.json()["integrations_visible"] is True
        limit = await client.get("/api/insights/limit", params={"brand_id": "101"})
        assert limit.status_code == 200
        assert limit.json()["can_generate"] is True
        generated = await client.post(
            "/api/insights/generate",
            params={"brand_id": "101", "range": "last_30_days"},
            headers={"Origin": "http://test"},
        )
        assert generated.status_code == 200
        assert runtime.generated == [("101", "signed-viewer-operator", "last_30_days")]


@pytest.mark.asyncio
async def test_tiktok_activation_handoff_requires_fresh_targeted_sso_and_is_read_only(
    phase6_fixture,
) -> None:
    authority, reporting, media_root = phase6_fixture
    app = create_app(authority, reporting, media_root)
    session = authority.sessions[sha256_text(authority.raw_session)]
    before = (deepcopy(authority.sessions), deepcopy(authority.projections))
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as client:
        untargeted = await client.get(
            "/api/settings/tiktok/activation-readiness",
            params={"brand_id": "101"},
        )
        assert untargeted.status_code == 403
        assert untargeted.json() == {"detail": "tiktok_owner_launch_required"}

        current = datetime.now(UTC)
        session.update(
            {
                "launch_target": "tiktok_owner_activation",
                "sso_issued_at": (current - timedelta(minutes=1)).isoformat(),
                "sso_consumed_at": current.isoformat(),
            }
        )
        ready = await client.get(
            "/api/settings/tiktok/activation-readiness",
            params={"brand_id": "101"},
        )
        assert ready.status_code == 200
        assert ready.json() | {
            "fresh_until": "ignored",
            "checked_at": "ignored",
        } == {
            "handoff_ready": True,
            "brand_id": "101",
            "launch_target": "tiktok_owner_activation",
            "fresh_until": "ignored",
            "runtime_mode": "development",
            "writes_enabled": False,
            "connection_state": "disconnected",
            "oauth_start_available": False,
            "reason": "oauth_start_disabled_by_runtime_policy",
            "checked_at": "ignored",
        }
        assert ready.headers["cache-control"] == "no-store"
        assert ready.headers["referrer-policy"] == "no-referrer"

        session["sso_issued_at"] = (current - timedelta(minutes=6)).isoformat()
        stale = await client.get(
            "/api/settings/tiktok/activation-readiness",
            params={"brand_id": "101"},
        )
        assert stale.status_code == 403
        assert stale.json() == {"detail": "fresh_owner_sso_required"}

    expected_sessions = deepcopy(before[0])
    expected_sessions[sha256_text(authority.raw_session)].update(
        {
            "launch_target": "tiktok_owner_activation",
            "sso_issued_at": (current - timedelta(minutes=6)).isoformat(),
            "sso_consumed_at": current.isoformat(),
        }
    )
    assert authority.sessions == expected_sessions
    assert authority.projections == before[1]


@pytest.mark.asyncio
async def test_media_proxy_rejects_paths_outside_root(phase6_fixture, tmp_path: Path) -> None:
    authority, reporting, media_root = phase6_fixture
    outside = tmp_path.parent / "phase6-outside.jpg"
    outside.write_bytes(b"outside")
    reporting.media = replace(
        reporting.media,
        storage_path=Path("../phase6-outside.jpg"),
        size_bytes=len(b"outside"),
        checksum=hashlib.sha256(b"outside").hexdigest(),
    )
    app = create_app(authority, reporting, media_root)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        cookies={COOKIE_NAME: authority.raw_session},
    ) as client:
        response = await client.get(
            "/api/media/instagram/ig-post",
            params={"brand_id": "101"},
        )
    assert response.status_code == 404

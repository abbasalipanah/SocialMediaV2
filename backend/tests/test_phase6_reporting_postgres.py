from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, create_engine, text

from app.application.queries import DashboardQuery, build_platform_dashboard
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.domain.reporting import ReportingRange
from app.infrastructure.persistence.legacy_socialmedia import LegacyReportingStore

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")

TABLES = (
    "brand_ai_insights",
    "social_backfill_jobs",
    "content_comments",
    "media_assets",
    "metrics_daily",
    "content_items",
    "asset_sync_state",
    "linked_social_accounts",
    "platform_connections",
    "assets",
    "brands",
)


@pytest.fixture()
def reporting_store() -> Iterator[LegacyReportingStore]:
    assert DATABASE_URL
    engine = create_engine(DATABASE_URL)
    _drop(engine)
    with engine.begin() as connection:
        for statement in _schema():
            connection.execute(text(statement))
        _seed(connection)
    yield LegacyReportingStore(engine)
    _drop(engine)
    engine.dispose()


def test_reporting_adapter_is_scope_safe_and_side_effect_free(
    reporting_store: LegacyReportingStore,
) -> None:
    before = _counts(reporting_store.engine)
    accounts = reporting_store.list_accounts(
        brand_ids=("101", "102"), platform=PlatformId.FACEBOOK
    )
    assert tuple(row.account_id for row in accounts) == (11, 12)
    assert all(row.brand_id != "999" for row in accounts)
    metrics = reporting_store.list_metrics(
        account_ids=(11, 12), start_on=date(2026, 7, 1), end_on=date(2026, 7, 2)
    )
    assert {row.metric_id for row in metrics} == {MetricId.FOLLOWERS, MetricId.REACH}
    assert reporting_store.list_content(
        account_ids=(11,), start_on=date(2026, 7, 1), end_on=date(2026, 7, 2)
    )[0].external_content_id == "post-1"
    assert reporting_store.list_comments(
        account_ids=(11,), start_on=date(2026, 7, 1), end_on=date(2026, 7, 2)
    )[0].external_comment_id == "comment-1"
    assert reporting_store.find_media(
        brand_ids=("101",),
        platform=PlatformId.FACEBOOK,
        external_content_id="post-1",
    ) is not None
    assert reporting_store.find_media(
        brand_ids=("102",),
        platform=PlatformId.FACEBOOK,
        external_content_id="post-1",
    ) is None
    assert reporting_store.list_connections(brand_ids=("101",))[0].state == "connected"
    assert reporting_store.list_sync_jobs(brand_ids=("101",))[0].status == "pending"
    assert reporting_store.list_insights(brand_ids=("101",))[0].summary == "Stored summary"
    assert _counts(reporting_store.engine) == before


def test_postgres_parent_rollup_uses_catalog_semantics(
    reporting_store: LegacyReportingStore,
) -> None:
    dashboard = build_platform_dashboard(
        store=reporting_store,
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.FACEBOOK,
        query=DashboardQuery(
            requested_brand_id="100",
            resolved_brand_ids=("101", "102"),
            rollup=True,
            date_range=ReportingRange(date(2026, 7, 1), date(2026, 7, 2), "custom"),
        ),
        now=datetime(2026, 7, 14, 12, tzinfo=UTC),
    )
    cards = {row.metric_id: row.value for row in dashboard.metrics}
    assert dashboard.meta.resolved_account_ids == (11, 12)
    assert cards[MetricId.FOLLOWERS] == 330
    assert cards[MetricId.REACH] == 30


def _drop(engine: Engine) -> None:
    with engine.begin() as connection:
        for table_name in TABLES:
            connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))


def _counts(engine: Engine) -> tuple[int, ...]:
    with engine.connect() as connection:
        return tuple(
            int(connection.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one())
            for table_name in TABLES
        )


def _schema() -> tuple[str, ...]:
    return (
        "CREATE TABLE brands (id integer PRIMARY KEY)",
        """CREATE TABLE assets (
            id integer PRIMARY KEY, brand_id integer NOT NULL, platform varchar(64) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255) NOT NULL,
            status varchar(64) NOT NULL
        )""",
        """CREATE TABLE platform_connections (
            id integer PRIMARY KEY, brand_id integer, platform varchar(64) NOT NULL,
            status varchar(64) NOT NULL, expires_at timestamptz,
            projected_at timestamptz, access_token_enc varchar(2048)
        )""",
        """CREATE TABLE linked_social_accounts (
            id integer PRIMARY KEY, brand_id integer NOT NULL, platform varchar(64) NOT NULL,
            asset_id integer, connection_id integer, status varchar(64) NOT NULL,
            health_status varchar(64) NOT NULL, backfill_status varchar(64) NOT NULL,
            nightly_enabled boolean NOT NULL, last_synced_at timestamptz
        )""",
        """CREATE TABLE asset_sync_state (
            asset_id integer PRIMARY KEY, last_synced_at timestamptz, last_error varchar(1024)
        )""",
        """CREATE TABLE metrics_daily (
            id serial, asset_id integer NOT NULL, brand_id integer NOT NULL, date date NOT NULL,
            metric_id varchar(64) NOT NULL, value_numeric double precision NOT NULL,
            breakdown_key varchar(64), breakdown_value varchar(128)
        )""",
        """CREATE TABLE content_items (
            id serial PRIMARY KEY, asset_id integer NOT NULL, brand_id integer NOT NULL,
            content_id varchar(128) NOT NULL, content_type varchar(32) NOT NULL,
            permalink varchar(512) NOT NULL, message varchar(4096) NOT NULL,
            media_url varchar(512) NOT NULL, created_time timestamptz,
            likes_count integer NOT NULL, comments_count integer NOT NULL,
            shares_count integer NOT NULL
        )""",
        """CREATE TABLE media_assets (
            id serial PRIMARY KEY, brand_id integer NOT NULL, asset_id integer NOT NULL,
            content_id varchar(128) NOT NULL, platform varchar(32) NOT NULL,
            media_kind varchar(32) NOT NULL, storage_path varchar(1024) NOT NULL,
            mime_type varchar(128) NOT NULL, size_bytes integer NOT NULL,
            checksum varchar(64) NOT NULL
        )""",
        """CREATE TABLE content_comments (
            id serial PRIMARY KEY, asset_id integer NOT NULL, platform varchar(32) NOT NULL,
            content_id varchar(255) NOT NULL, comment_id varchar(255) NOT NULL,
            user_name varchar(255), text text NOT NULL, like_count integer NOT NULL,
            reply_count integer NOT NULL, answered boolean NOT NULL, commented_at timestamptz
        )""",
        """CREATE TABLE social_backfill_jobs (
            id integer PRIMARY KEY, brand_id integer NOT NULL, asset_id integer,
            platform varchar(64) NOT NULL, stage varchar(64) NOT NULL,
            status varchar(32) NOT NULL, scheduled_for timestamptz NOT NULL,
            started_at timestamptz, finished_at timestamptz, error_code varchar(64)
        )""",
        """CREATE TABLE brand_ai_insights (
            id integer PRIMARY KEY, brand_id integer NOT NULL, status varchar(16) NOT NULL,
            date_from date, date_to date, strategic_summary text,
            action_recommendations text, created_at timestamptz NOT NULL,
            completed_at timestamptz
        )""",
    )


def _seed(connection) -> None:
    statements = (
        "INSERT INTO brands (id) VALUES (101), (102), (999)",
        """INSERT INTO assets VALUES
            (11, 101, 'facebook', 'fb-a', 'Facebook A', 'active'),
            (12, 102, 'facebook_organic', 'fb-b', 'Facebook B', 'active'),
            (99, 999, 'facebook', 'fb-other', 'Facebook Other', 'active')""",
        """INSERT INTO platform_connections VALUES
            (1, 101, 'facebook', 'connected', NULL, '2026-07-02T10:00:00Z', 'secret')""",
        """INSERT INTO linked_social_accounts VALUES
            (1, 101, 'facebook', 11, 1, 'active', 'healthy', 'ready', true,
             '2026-07-02T10:00:00Z'),
            (2, 102, 'facebook', 12, NULL, 'active', 'healthy', 'ready', true,
             '2026-07-02T09:00:00Z')""",
        "INSERT INTO asset_sync_state VALUES (11, '2026-07-02T10:00:00Z', NULL)",
        """INSERT INTO metrics_daily
            (asset_id, brand_id, date, metric_id, value_numeric) VALUES
            (11, 101, '2026-07-01', 'followers', 100),
            (11, 101, '2026-07-02', 'followers', 110),
            (12, 102, '2026-07-02', 'followers', 220),
            (11, 101, '2026-07-01', 'reach', 10),
            (12, 102, '2026-07-02', 'reach', 20),
            (99, 999, '2026-07-02', 'followers', 9999)""",
        """INSERT INTO content_items
            (asset_id, brand_id, content_id, content_type, permalink, message, media_url,
             created_time, likes_count, comments_count, shares_count) VALUES
            (11, 101, 'post-1', 'image', 'https://example.test/post-1', 'message', '',
             '2026-07-02T08:00:00Z', 4, 1, 2)""",
        """INSERT INTO content_comments
            (asset_id, platform, content_id, comment_id, user_name, text, like_count,
             reply_count, answered, commented_at) VALUES
            (11, 'facebook', 'post-1', 'comment-1', 'Person', 'Hello', 2, 1, true,
             '2026-07-02T09:00:00Z')""",
        """INSERT INTO media_assets
            (brand_id, asset_id, content_id, platform, media_kind, storage_path, mime_type,
             size_bytes, checksum) VALUES
            (101, 11, 'post-1', 'facebook', 'cover', 'facebook/post-1.jpg', 'image/jpeg',
             3, 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')""",
        """INSERT INTO social_backfill_jobs VALUES
            (1, 101, 11, 'facebook', 'initial_30d', 'pending',
             '2026-07-02T10:00:00Z', NULL, NULL, NULL)""",
        """INSERT INTO brand_ai_insights VALUES
            (1, 101, 'completed', '2026-07-01', '2026-07-02', 'Stored summary',
             'Stored recommendation', '2026-07-03T10:00:00Z', '2026-07-03T11:00:00Z')""",
    )
    for statement in statements:
        connection.execute(text(statement))

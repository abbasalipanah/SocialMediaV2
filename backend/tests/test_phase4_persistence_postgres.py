from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine, text

from app.application.ports.persistence import (
    CommentRecord,
    ContentRecord,
    MediaRecord,
    MetricPoint,
)
from app.application.queries.metrics import MetricQuery
from app.core.config import RuntimeMode
from app.core.write_policy import WritePolicy
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2 import (
    SocialCommentStore,
    SocialContentStore,
    SocialMediaStore,
    SocialMetricStore,
)

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")


@pytest.fixture()
def stores() -> Iterator[
    tuple[SocialMetricStore, SocialContentStore, SocialCommentStore, SocialMediaStore]
]:
    assert DATABASE_URL
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        for table_name in (
            "content_comments",
            "media_assets",
            "metrics_daily",
            "content_items",
            "assets",
            "brands",
        ):
            connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
        connection.execute(text("CREATE TABLE brands (id integer PRIMARY KEY)"))
        connection.execute(
            text(
                """CREATE TABLE assets (
                    id integer PRIMARY KEY,
                    brand_id integer NOT NULL REFERENCES brands(id),
                    platform varchar(64) NOT NULL
                )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE content_items (
                    id serial PRIMARY KEY,
                    asset_id integer NOT NULL REFERENCES assets(id),
                    brand_id integer NOT NULL REFERENCES brands(id),
                    content_id varchar(128) NOT NULL,
                    content_type varchar(32) NOT NULL DEFAULT '',
                    permalink varchar(512) NOT NULL DEFAULT '',
                    message varchar(4096) NOT NULL DEFAULT '',
                    media_url varchar(2048) NOT NULL DEFAULT '',
                    created_time timestamptz NULL,
                    likes_count integer NOT NULL DEFAULT 0,
                    comments_count integer NOT NULL DEFAULT 0,
                    shares_count integer NOT NULL DEFAULT 0,
                    views_count double precision,
                    reach_count double precision,
                    cover_url varchar(2048),
                    thumbnail_url varchar(2048),
                    cover_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
                    thumbnail_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
                    media_url_candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
                    full_video_watched_rate double precision,
                    total_time_watched double precision,
                    average_time_watched double precision,
                    interactions_count double precision,
                    replies_count double precision,
                    profile_visits double precision,
                    follows_count double precision,
                    taps_forward double precision,
                    taps_back double precision,
                    swipe_forward double precision,
                    exits double precision,
                    navigation_count double precision,
                    completion_rate double precision,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    updated_at timestamptz NOT NULL DEFAULT now(),
                    CONSTRAINT uq_content_items_asset_content UNIQUE (asset_id, content_id)
                )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE metrics_daily (
                    id serial NOT NULL,
                    asset_id integer NOT NULL REFERENCES assets(id),
                    brand_id integer NOT NULL REFERENCES brands(id),
                    date date NOT NULL,
                    metric_id varchar(64) NOT NULL,
                    value_numeric double precision NOT NULL,
                    breakdown_key varchar(64) NULL,
                    breakdown_value varchar(128) NULL,
                    PRIMARY KEY (id, date)
                )"""
            )
        )
        connection.execute(
            text(
                """CREATE UNIQUE INDEX uq_metrics_daily_account_rows
                   ON metrics_daily (asset_id, date, metric_id)
                   WHERE breakdown_key IS NULL AND breakdown_value IS NULL"""
            )
        )
        connection.execute(
            text(
                """CREATE UNIQUE INDEX uq_metrics_daily_breakdown_rows
                   ON metrics_daily (
                       asset_id, date, metric_id, breakdown_key, breakdown_value
                   ) WHERE breakdown_key IS NOT NULL AND breakdown_value IS NOT NULL"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE content_comments (
                    id serial PRIMARY KEY,
                    asset_id integer NOT NULL REFERENCES assets(id),
                    content_id varchar(255) NOT NULL,
                    platform varchar(32) NOT NULL,
                    comment_id varchar(255) NOT NULL,
                    user_id varchar(255) NULL,
                    user_name varchar(255) NULL,
                    text text NOT NULL DEFAULT '',
                    like_count integer NOT NULL DEFAULT 0,
                    reply_count integer NOT NULL DEFAULT 0,
                    answered boolean NOT NULL DEFAULT false,
                    attachment_type varchar(64) NULL,
                    attachment_media_type varchar(64) NULL,
                    attachment_url varchar(1024) NULL,
                    commented_at timestamptz NULL,
                    created_at timestamptz NOT NULL,
                    updated_at timestamptz NOT NULL,
                    CONSTRAINT uq_content_comments_asset_comment UNIQUE (asset_id, comment_id)
                )"""
            )
        )
        connection.execute(
            text(
                """CREATE TABLE media_assets (
                    id serial PRIMARY KEY,
                    brand_id integer NOT NULL REFERENCES brands(id),
                    asset_id integer NOT NULL REFERENCES assets(id),
                    content_id varchar(128) NOT NULL,
                    platform varchar(32) NOT NULL,
                    media_kind varchar(32) NOT NULL,
                    storage_path varchar(1024) NOT NULL,
                    source_url varchar(2048) NOT NULL,
                    source_status integer NULL,
                    mime_type varchar(128) NOT NULL,
                    size_bytes integer NOT NULL,
                    checksum varchar(64) NOT NULL,
                    last_verified_at timestamptz NULL,
                    created_at timestamptz NOT NULL,
                    updated_at timestamptz NOT NULL,
                    CONSTRAINT uq_media_assets_asset_content_kind
                        UNIQUE (asset_id, content_id, media_kind)
                )"""
            )
        )
        connection.execute(text("INSERT INTO brands (id) VALUES (7)"))
        connection.execute(
            text("INSERT INTO assets (id, brand_id, platform) VALUES (11, 7, 'instagram')")
        )
    policy = WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True)
    result = (
        SocialMetricStore(engine, policy, bootstrap_metric_catalog()),
        SocialContentStore(engine, policy),
        SocialCommentStore(engine, policy),
        SocialMediaStore(engine, policy),
    )
    yield result
    with engine.begin() as connection:
        for table_name in (
            "content_comments",
            "media_assets",
            "metrics_daily",
            "content_items",
            "assets",
            "brands",
        ):
            connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
    engine.dispose()


def test_social_data_stores_are_idempotent_and_query_side_effect_free(
    stores: tuple[
        SocialMetricStore,
        SocialContentStore,
        SocialCommentStore,
        SocialMediaStore,
    ],
) -> None:
    metric_store, content_store, comment_store, media_store = stores
    point = MetricPoint(
        platform=PlatformId.INSTAGRAM,
        account_id=11,
        brand_id=7,
        observed_on=date(2026, 7, 14),
        metric_id=MetricId.FOLLOWERS,
        value=120,
    )
    metric_store.upsert(point)
    metric_store.upsert(MetricPoint(**{**point.__dict__, "value": 125}))

    content = ContentRecord(
        platform=PlatformId.INSTAGRAM,
        account_id=11,
        brand_id=7,
        external_content_id="post-1",
        content_type="image",
        permalink="https://example.test/post-1",
        message="first",
        media_url="https://example.test/media-1",
        published_at=datetime(2026, 7, 14, 8, tzinfo=UTC),
        likes_count=3,
        comments_count=1,
        shares_count=0,
        views_count=91,
        reach_count=73,
        cover_url="https://example.test/cover-1",
        cover_candidates=("https://example.test/cover-1",),
        media_url_candidates=("https://example.test/media-1",),
        interactions_count=4,
    )
    content_store.upsert(content)
    content_store.upsert(ContentRecord(**{**content.__dict__, "likes_count": 4}))

    comment = CommentRecord(
        platform=PlatformId.INSTAGRAM,
        account_id=11,
        external_content_id="post-1",
        external_comment_id="comment-1",
        author_id="author-1",
        author_name="Author",
        text="hello",
        like_count=1,
        reply_count=0,
        answered=False,
        attachment_type=None,
        attachment_media_type=None,
        attachment_url=None,
        commented_at=datetime(2026, 7, 14, 9, tzinfo=UTC),
    )
    comment_store.upsert(comment)
    comment_store.upsert(CommentRecord(**{**comment.__dict__, "answered": True}))

    media = MediaRecord(
        platform=PlatformId.INSTAGRAM,
        account_id=11,
        brand_id=7,
        external_content_id="post-1",
        media_kind="cover",
        storage_path="instagram/11/post-1.jpg",
        source_url="https://example.test/media-1",
        source_status=200,
        mime_type="image/jpeg",
        size_bytes=12,
        checksum="a" * 64,
        verified_at=datetime(2026, 7, 14, 10, tzinfo=UTC),
    )
    media_store.upsert(media)
    media_store.upsert(MediaRecord(**{**media.__dict__, "size_bytes": 14}))

    query = MetricQuery(
        catalog=bootstrap_metric_catalog(),
        platform=PlatformId.INSTAGRAM,
        metric_ids=(MetricId.FOLLOWERS,),
    )
    before = _row_counts(metric_store)
    metric_rows = metric_store.read(
        account_id=11,
        start_on=date(2026, 7, 14),
        end_on=date(2026, 7, 14),
        query=query,
    )
    assert metric_rows[0].value == 125
    stored_content = content_store.list_for_account(11)[0]
    assert stored_content.likes_count == 4
    assert stored_content.views_count == 91
    assert stored_content.cover_candidates == ("https://example.test/cover-1",)
    assert comment_store.list_for_content(11, "post-1")[0].answered is True
    assert media_store.get(11, "post-1", "cover").size_bytes == 14  # type: ignore[union-attr]
    assert _row_counts(metric_store) == before == (1, 1, 1, 1)


def _row_counts(store: SocialMetricStore) -> tuple[int, int, int, int]:
    with store.engine.connect() as connection:
        return tuple(
            int(connection.execute(text(f"SELECT count(*) FROM {table_name}")).scalar_one())
            for table_name in (
                "metrics_daily",
                "content_items",
                "content_comments",
                "media_assets",
            )
        )  # type: ignore[return-value]


def test_dormant_policy_rejects_every_social_data_mutation(
    stores: tuple[
        SocialMetricStore,
        SocialContentStore,
        SocialCommentStore,
        SocialMediaStore,
    ],
) -> None:
    metric_store = stores[0]
    blocked = SocialMetricStore(
        metric_store.engine,
        WritePolicy(runtime_mode=RuntimeMode.DORMANT, writes_enabled=False),
        bootstrap_metric_catalog(),
    )
    with pytest.raises(PermissionError, match="Mutation is disabled"):
        blocked.upsert(
            MetricPoint(
                platform=PlatformId.INSTAGRAM,
                account_id=11,
                brand_id=7,
                observed_on=date(2026, 7, 14),
                metric_id=MetricId.FOLLOWERS,
                value=1,
            )
        )
    assert _row_counts(metric_store) == (0, 0, 0, 0)


def test_metric_breakdown_replacement_removes_stale_dimension_rows(
    stores: tuple[
        SocialMetricStore,
        SocialContentStore,
        SocialCommentStore,
        SocialMediaStore,
    ],
) -> None:
    metric_store = stores[0]
    arguments = {
        "platform": PlatformId.INSTAGRAM,
        "account_id": 11,
        "brand_id": 7,
        "observed_on": date(2026, 7, 14),
        "metric_id": MetricId.FOLLOWERS,
        "breakdown_key": "follower_demographics_country",
    }
    metric_store.replace_breakdown(**arguments, values={"TR": 70, "DE": 20})
    metric_store.replace_breakdown(**arguments, values={"TR": 75})

    with metric_store.engine.connect() as connection:
        rows = connection.execute(
            text(
                """SELECT breakdown_value, value_numeric
                   FROM metrics_daily
                   WHERE asset_id=11 AND breakdown_key='follower_demographics_country'
                   ORDER BY breakdown_value"""
            )
        ).all()
    assert rows == [("TR", 75.0)]


def test_persistence_rejects_cross_brand_or_platform_account_scope(
    stores: tuple[
        SocialMetricStore,
        SocialContentStore,
        SocialCommentStore,
        SocialMediaStore,
    ],
) -> None:
    metric_store = stores[0]
    with pytest.raises(ValueError, match="account_scope_mismatch"):
        metric_store.upsert(
            MetricPoint(
                platform=PlatformId.INSTAGRAM,
                account_id=11,
                brand_id=8,
                observed_on=date(2026, 7, 14),
                metric_id=MetricId.FOLLOWERS,
                value=1,
            )
        )
    with pytest.raises(ValueError, match="account_scope_mismatch"):
        metric_store.upsert(
            MetricPoint(
                platform=PlatformId.FACEBOOK,
                account_id=11,
                brand_id=7,
                observed_on=date(2026, 7, 14),
                metric_id=MetricId.FOLLOWERS,
                value=1,
            )
        )
    assert _row_counts(metric_store) == (0, 0, 0, 0)

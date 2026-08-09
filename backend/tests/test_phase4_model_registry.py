from __future__ import annotations

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String

from app.infrastructure.persistence.model_registry import (
    registered_metadata,
    registered_tables,
)


def test_explicit_model_registry_is_local_and_complete_for_social_data() -> None:
    tables = registered_tables()
    assert tuple(table.name for table in tables) == (
        "metrics_daily",
        "content_items",
        "content_comments",
        "media_assets",
    )
    assert set(registered_metadata().tables) == {table.name for table in tables}
    assert all(
        table.metadata is registered_metadata()
        and table.__class__.__module__.startswith("sqlalchemy")
        for table in tables
    )


def test_metric_registry_contract_tracks_composite_key_and_partial_indexes() -> None:
    metric_table = registered_metadata().tables["metrics_daily"]
    assert [column.name for column in metric_table.primary_key.columns] == ["id", "date"]
    assert isinstance(metric_table.c.date.type, Date)
    assert isinstance(metric_table.c.value_numeric.type, Float)
    assert isinstance(metric_table.c.metric_id.type, String)
    assert metric_table.c.metric_id.type.length == 64
    assert {index.name for index in metric_table.indexes} == {
        "uq_metrics_daily_account_rows",
        "uq_metrics_daily_breakdown_rows",
    }
    assert all(index.unique for index in metric_table.indexes)
    assert all(
        index.dialect_options["postgresql"]["where"] is not None
        for index in metric_table.indexes
    )


def test_content_comment_and_media_registry_types_are_explicit() -> None:
    metadata = registered_metadata()
    content = metadata.tables["content_items"]
    comments = metadata.tables["content_comments"]
    media = metadata.tables["media_assets"]

    assert isinstance(content.c.created_time.type, DateTime)
    assert content.c.created_time.type.timezone is True
    assert isinstance(content.c.likes_count.type, Integer)
    assert content.c.media_url.type.length == 2048
    assert isinstance(content.c.views_count.type, Float)
    assert content.c.views_count.nullable is True
    assert isinstance(content.c.cover_candidates.type, JSON)
    assert content.c.cover_candidates.nullable is False
    assert comments.c.attachment_url.type.length == 1024
    assert media.c.source_url.type.length == 2048
    assert media.c.last_verified_at.nullable is True
    assert media.c.size_bytes.nullable is False

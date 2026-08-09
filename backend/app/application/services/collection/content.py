"""Idempotent page-at-a-time content collection with durable cursor advancement."""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import datetime
from typing import Any

from app.application.ports.checkpoints import (
    CheckpointKey,
    CheckpointStore,
    ProviderCheckpoint,
)
from app.application.ports.persistence import ContentRecord, ContentStore
from app.application.ports.platforms import ProviderRecord
from app.application.ports.platforms.content import ContentReader
from app.domain.platforms import CapabilityId

from .contracts import CollectionOutcome, CollectionStatus, CollectionTarget


def collect_content(
    *,
    target: CollectionTarget,
    reader: ContentReader,
    content_store: ContentStore,
    checkpoint_store: CheckpointStore,
    record_sink: Callable[[ProviderRecord], int] | None = None,
    after_record: Callable[[int], None] | None = None,
    checkpoint_account_id: str | None = None,
    max_pages: int = 100,
) -> CollectionOutcome:
    if max_pages < 1 or max_pages > 1000:
        raise ValueError("collection_page_limit_invalid")
    key = CheckpointKey(
        platform=target.account.platform,
        capability=CapabilityId.CONTENT,
        account_id=checkpoint_account_id or target.account.account_id,
    )
    checkpoint = checkpoint_store.get(key)
    cursor = checkpoint.cursor if checkpoint is not None else None
    content_count = 0
    media_count = 0
    page_count = 0
    while page_count < max_pages:
        page = reader.list_content(target.account, cursor=cursor)
        for item in page.items:
            content_store.upsert(_content_record(target, item))
            if record_sink is not None:
                media_count += record_sink(item)
            content_count += 1
            if after_record is not None:
                after_record(content_count)
        next_version = 1 if checkpoint is None else checkpoint.version + 1
        next_checkpoint = ProviderCheckpoint(
            key=key,
            version=next_version,
            cursor=page.next_cursor,
            watermark=_watermark(page.items),
            observed_through=page.observed_at,
        )
        expected_version = checkpoint.version if checkpoint is not None else None
        if not checkpoint_store.put(next_checkpoint, expected_version=expected_version):
            raise RuntimeError("checkpoint_concurrent_update")
        checkpoint = next_checkpoint
        page_count += 1
        cursor = page.next_cursor
        if cursor is None:
            return CollectionOutcome(
                status=CollectionStatus.SUCCESS,
                content_count=content_count,
                media_count=media_count,
                page_count=page_count,
            )
    return CollectionOutcome(
        status=CollectionStatus.PARTIAL,
        content_count=content_count,
        media_count=media_count,
        page_count=page_count,
        next_cursor=cursor,
        error_code="page_limit_reached",
    )


def _content_record(target: CollectionTarget, item: ProviderRecord) -> ContentRecord:
    fields = item.fields
    return ContentRecord(
        platform=target.account.platform,
        account_id=target.local_account_id,
        brand_id=target.brand_id,
        external_content_id=item.external_id,
        content_type=_text(fields, "content_type"),
        permalink=_text(fields, "permalink", required=False),
        message=_text(fields, "message", required=False),
        media_url=_text(fields, "media_url", required=False),
        published_at=_datetime(fields, "published_at"),
        likes_count=_count(fields, "likes_count"),
        comments_count=_count(fields, "comments_count"),
        shares_count=_count(fields, "shares_count"),
        views_count=_optional_number(fields, "views_count"),
        reach_count=_optional_number(fields, "reach_count"),
        cover_url=_optional_text(fields, "cover_url"),
        thumbnail_url=_optional_text(fields, "thumbnail_url"),
        cover_candidates=_candidates(fields, "cover_candidates"),
        thumbnail_candidates=_candidates(fields, "thumbnail_candidates"),
        media_url_candidates=_candidates(fields, "media_url_candidates"),
        full_video_watched_rate=_optional_number(fields, "full_video_watched_rate"),
        total_time_watched=_optional_number(fields, "total_time_watched"),
        average_time_watched=_optional_number(fields, "average_time_watched"),
        interactions_count=_optional_number(fields, "interactions_count"),
        replies_count=_optional_number(fields, "replies_count"),
        saves_count=_optional_number(fields, "saves_count"),
        sticker_taps=_optional_number(fields, "sticker_taps"),
        profile_visits=_optional_number(fields, "profile_visits"),
        follows_count=_optional_number(fields, "follows_count"),
        taps_forward=_optional_number(fields, "taps_forward"),
        taps_back=_optional_number(fields, "taps_back"),
        swipe_forward=_optional_number(fields, "swipe_forward"),
        exits=_optional_number(fields, "exits"),
        navigation_count=_optional_number(fields, "navigation_count"),
        completion_rate=_optional_number(fields, "completion_rate"),
    )


def _text(fields: dict[str, Any], key: str, *, required: bool = True) -> str:
    value = fields.get(key)
    if not isinstance(value, str) or (required and not value):
        raise ValueError("provider_content_field_invalid")
    return value


def _count(fields: dict[str, Any], key: str) -> int:
    value = fields.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("provider_content_field_invalid")
    return value


def _optional_text(fields: dict[str, Any], key: str) -> str | None:
    value = fields.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError("provider_content_field_invalid")
    return value or None


def _optional_number(fields: dict[str, Any], key: str) -> float | None:
    value = fields.get(key)
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not math.isfinite(float(value))
        or float(value) < 0
    ):
        raise ValueError("provider_content_field_invalid")
    return float(value)


def _candidates(fields: dict[str, Any], key: str) -> tuple[str, ...]:
    value = fields.get(key, ())
    if not isinstance(value, tuple | list):
        raise ValueError("provider_content_field_invalid")
    normalized: list[str] = []
    for candidate in value:
        if not isinstance(candidate, str) or not candidate.strip():
            raise ValueError("provider_content_field_invalid")
        if candidate not in normalized:
            normalized.append(candidate)
    return tuple(normalized)


def _datetime(fields: dict[str, Any], key: str) -> datetime | None:
    value = fields.get(key)
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
        raise ValueError("provider_content_field_invalid")
    return value


def _watermark(items: tuple[ProviderRecord, ...]) -> str | None:
    return max((item.external_id for item in items), default=None)


__all__ = ["collect_content"]

"""Comment page collection with idempotent persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.application.ports.persistence import CommentRecord, CommentStore
from app.application.ports.platforms import ProviderRecord
from app.application.ports.platforms.comments import CommentsReader

from .contracts import CollectionOutcome, CollectionStatus, CollectionTarget


def collect_comments(
    *,
    target: CollectionTarget,
    content_id: str,
    reader: CommentsReader,
    comment_store: CommentStore,
    max_pages: int = 100,
) -> CollectionOutcome:
    if not content_id or max_pages < 1 or max_pages > 1000:
        raise ValueError("comment_collection_input_invalid")
    cursor = None
    comment_count = 0
    page_count = 0
    while page_count < max_pages:
        page = reader.list_comments(target.account, content_id=content_id, cursor=cursor)
        if page.content_id != content_id:
            raise ValueError("provider_content_mismatch")
        for item in page.items:
            comment_store.upsert(_comment_record(target, content_id, item))
            comment_count += 1
        cursor = page.next_cursor
        page_count += 1
        if cursor is None:
            return CollectionOutcome(
                status=CollectionStatus.SUCCESS,
                comment_count=comment_count,
                page_count=page_count,
            )
    return CollectionOutcome(
        status=CollectionStatus.PARTIAL,
        comment_count=comment_count,
        page_count=page_count,
        next_cursor=cursor,
        error_code="page_limit_reached",
    )


def _comment_record(
    target: CollectionTarget, content_id: str, item: ProviderRecord
) -> CommentRecord:
    fields = item.fields
    return CommentRecord(
        platform=target.account.platform,
        account_id=target.local_account_id,
        external_content_id=content_id,
        external_comment_id=item.external_id,
        author_id=_optional_text(fields, "author_id"),
        author_name=_optional_text(fields, "author_name"),
        text=_text(fields, "text"),
        like_count=_count(fields, "like_count"),
        reply_count=_count(fields, "reply_count"),
        answered=False,
        attachment_type=_optional_text(fields, "attachment_type"),
        attachment_media_type=_optional_text(fields, "attachment_media_type"),
        attachment_url=_optional_text(fields, "attachment_url"),
        commented_at=_datetime(fields, "commented_at"),
    )


def _text(fields: dict[str, Any], key: str) -> str:
    value = fields.get(key)
    if not isinstance(value, str):
        raise ValueError("provider_comment_field_invalid")
    return value


def _optional_text(fields: dict[str, Any], key: str) -> str | None:
    value = fields.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError("provider_comment_field_invalid")
    return value


def _count(fields: dict[str, Any], key: str) -> int:
    value = fields.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("provider_comment_field_invalid")
    return value


def _datetime(fields: dict[str, Any], key: str) -> datetime | None:
    value = fields.get(key)
    if value is not None and (not isinstance(value, datetime) or value.tzinfo is None):
        raise ValueError("provider_comment_field_invalid")
    return value


__all__ = ["collect_comments"]

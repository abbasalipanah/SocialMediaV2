"""YouTube top-level comment-thread normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.comments import CommentPage
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .identifiers import resource_id
from .responses import (
    YouTubeResponseError,
    optional_text,
    required_count,
    required_mapping,
    required_text,
)


class YouTubeCommentsReader:
    def __init__(
        self,
        fetch: Callable[
            [ProviderAccount, str, str | None], Mapping[str, Any]
        ],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def list_comments(
        self,
        account: ProviderAccount,
        *,
        content_id: str,
        cursor: str | None = None,
    ) -> CommentPage:
        if account.platform is not PlatformId.YOUTUBE:
            raise ValueError("provider_family_mismatch")
        video_id = resource_id(content_id, error_code="content_id_invalid")
        observed_at = self._clock()
        payload = self._fetch(account, video_id, cursor)
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise YouTubeResponseError("comment_response_invalid")
        return CommentPage(
            content_id=video_id,
            items=tuple(_record(item, observed_at) for item in items),
            next_cursor=_next_cursor(payload),
            observed_at=observed_at,
        )


def _record(payload: object, observed_at: datetime) -> ProviderRecord:
    if not isinstance(payload, Mapping):
        raise YouTubeResponseError("comment_response_invalid")
    thread_id = resource_id(payload.get("id"), error_code="comment_response_invalid")
    thread_snippet = required_mapping(payload, "snippet")
    top_level = required_mapping(thread_snippet, "topLevelComment")
    comment_id = resource_id(
        top_level.get("id"), error_code="comment_response_invalid"
    )
    snippet = required_mapping(top_level, "snippet")
    return ProviderRecord(
        external_id=comment_id,
        observed_at=observed_at,
        fields={
            "author_id": _author_channel_id(snippet),
            "author_name": optional_text(snippet, "authorDisplayName"),
            "text": required_text(snippet, "textDisplay"),
            "like_count": required_count(snippet, "likeCount"),
            "reply_count": required_count(thread_snippet, "totalReplyCount"),
            "attachment_type": None,
            "attachment_media_type": None,
            "attachment_url": None,
            "commented_at": _timestamp(snippet.get("publishedAt")),
            "thread_id": thread_id,
        },
    )


def _author_channel_id(payload: Mapping[str, Any]) -> str | None:
    raw = payload.get("authorChannelId")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise YouTubeResponseError("response_field_invalid")
    return optional_text(raw, "value")


def _next_cursor(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("nextPageToken")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise YouTubeResponseError("comment_response_invalid")
    return value.strip()


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise YouTubeResponseError("response_field_invalid")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise YouTubeResponseError("response_field_invalid") from exc
    if parsed.tzinfo is None:
        raise YouTubeResponseError("response_field_invalid")
    return parsed.astimezone(UTC)


__all__ = ["YouTubeCommentsReader"]

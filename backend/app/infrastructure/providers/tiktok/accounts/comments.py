"""TikTok Business comments capability reader."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.comments import CommentPage
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .responses import TikTokResponseError, success_data


class TikTokCommentsReader:
    def __init__(
        self,
        fetch: Callable[[str, str, str | None], Mapping[str, Any]],
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
        if account.platform is not PlatformId.TIKTOK:
            raise ValueError("provider_family_mismatch")
        if not content_id:
            raise ValueError("content_id_required")
        observed_at = self._clock()
        data = success_data(self._fetch(account.account_id, content_id, cursor))
        raw_comments = data.get("comments") or []
        if not isinstance(raw_comments, list):
            raise TikTokResponseError("comment_list_invalid")
        has_more = data.get("has_more", False)
        if not isinstance(has_more, bool):
            raise TikTokResponseError("comment_page_invalid")
        next_cursor = data.get("cursor")
        if has_more and (not isinstance(next_cursor, str) or not next_cursor):
            raise TikTokResponseError("comment_page_invalid")
        if not has_more:
            next_cursor = None
        return CommentPage(
            content_id=content_id,
            items=tuple(_record(row, observed_at) for row in raw_comments),
            next_cursor=next_cursor,
            observed_at=observed_at,
        )


def _record(payload: object, observed_at: datetime) -> ProviderRecord:
    if not isinstance(payload, Mapping):
        raise TikTokResponseError("comment_item_invalid")
    return ProviderRecord(
        external_id=_required_text(payload, "comment_id"),
        observed_at=observed_at,
        fields={
            "author_id": _optional_text(payload, "user_id"),
            "author_name": _optional_text(payload, "username"),
            "text": _optional_text(payload, "text") or "",
            "like_count": _count(payload, "likes"),
            "reply_count": _count(payload, "reply_comment_total"),
            "attachment_type": None,
            "attachment_media_type": None,
            "attachment_url": None,
            "commented_at": _timestamp(payload.get("create_time")),
        },
    )


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = _optional_text(payload, key)
    if value is None:
        raise TikTokResponseError("response_field_invalid")
    return value


def _optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TikTokResponseError("response_field_invalid")
    return value.strip() or None


def _count(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TikTokResponseError("response_field_invalid")
    return value


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TikTokResponseError("response_field_invalid")
    if isinstance(value, int | float):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OSError, OverflowError, ValueError) as exc:
            raise TikTokResponseError("response_field_invalid") from exc
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TikTokResponseError("response_field_invalid") from exc
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    raise TikTokResponseError("response_field_invalid")


__all__ = ["TikTokCommentsReader"]

"""TikTok public-video fixture reader."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentPage
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId

from .responses import TikTokResponseError, success_data


class TikTokContentReader:
    def __init__(
        self,
        fetch: Callable[[str, str | None], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def list_content(
        self,
        account: ProviderAccount,
        *,
        cursor: str | None = None,
    ) -> ContentPage:
        if account.platform is not PlatformId.TIKTOK:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock()
        data = success_data(self._fetch(account.account_id, cursor))
        raw_videos = data.get("videos") or []
        if not isinstance(raw_videos, list):
            raise TikTokResponseError("video_list_invalid")
        items = tuple(_record(row, observed_at) for row in raw_videos)
        has_more = data.get("has_more", False)
        if not isinstance(has_more, bool):
            raise TikTokResponseError("video_page_invalid")
        next_cursor = data.get("cursor")
        if has_more and (not isinstance(next_cursor, str) or not next_cursor):
            raise TikTokResponseError("video_page_invalid")
        if not has_more:
            next_cursor = None
        return ContentPage(items=items, next_cursor=next_cursor, observed_at=observed_at)


def _record(payload: object, observed_at: datetime) -> ProviderRecord:
    if not isinstance(payload, Mapping):
        raise TikTokResponseError("video_item_invalid")
    item_id = _text(payload, "item_id")
    likes = _count(payload, "likes")
    comments = _count(payload, "comments")
    shares = _count(payload, "shares")
    views = _count(payload, "video_views")
    return ProviderRecord(
        external_id=item_id,
        observed_at=observed_at,
        fields={
            "content_type": "video",
            "permalink": "",
            "message": _optional_text(payload, "caption") or "",
            "media_url": _optional_text(payload, "thumbnail_url") or "",
            "published_at": _timestamp(payload.get("create_time")),
            "likes_count": likes,
            "comments_count": comments,
            "shares_count": shares,
            "metric_values": {
                MetricId.VIDEO_VIEWS_TOTAL: views,
                MetricId.VIDEO_LIKES_TOTAL: likes,
                MetricId.VIDEO_COMMENTS_TOTAL: comments,
                MetricId.VIDEO_SHARES_TOTAL: shares,
            },
        },
    )


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TikTokResponseError("response_field_invalid")
    return value


def _optional_text(payload: Mapping[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise TikTokResponseError("response_field_invalid")
    return value or None


def _count(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TikTokResponseError("response_field_invalid")
    return value


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise TikTokResponseError("response_field_invalid")
    if isinstance(value, int):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TikTokResponseError("response_field_invalid") from exc
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC)
    raise TikTokResponseError("response_field_invalid")


__all__ = ["TikTokContentReader"]

"""YouTube uploads-playlist content normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentPage
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .identifiers import resource_id
from .responses import (
    YouTubeResponseError,
    optional_count,
    optional_text,
    required_mapping,
    required_text,
    single_channel,
)

_THUMBNAIL_ORDER = ("maxres", "standard", "high", "medium", "default")


class YouTubeContentReader:
    def __init__(
        self,
        fetch_channel: Callable[[ProviderAccount], Mapping[str, Any]],
        fetch_playlist: Callable[
            [ProviderAccount, str, str | None], Mapping[str, Any]
        ],
        fetch_videos: Callable[
            [ProviderAccount, tuple[str, ...]], Mapping[str, Any]
        ],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch_channel = fetch_channel
        self._fetch_playlist = fetch_playlist
        self._fetch_videos = fetch_videos
        self._clock = clock
        self._playlist_by_account: dict[str, str] = {}

    def list_content(
        self,
        account: ProviderAccount,
        *,
        cursor: str | None = None,
    ) -> ContentPage:
        if account.platform is not PlatformId.YOUTUBE:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock()
        playlist_id = self._uploads_playlist(account)
        page = self._fetch_playlist(account, playlist_id, cursor)
        video_ids = _playlist_video_ids(page)
        videos = self._fetch_videos(account, video_ids) if video_ids else {"items": []}
        by_id = _videos_by_id(videos)
        if set(by_id) != set(video_ids):
            raise YouTubeResponseError("video_response_incomplete")
        return ContentPage(
            items=tuple(_record(by_id[video_id], observed_at) for video_id in video_ids),
            next_cursor=_next_cursor(page),
            observed_at=observed_at,
        )

    def _uploads_playlist(self, account: ProviderAccount) -> str:
        if cached := self._playlist_by_account.get(account.account_id):
            return cached
        channel = single_channel(
            self._fetch_channel(account), channel_id=account.account_id
        )
        content_details = required_mapping(channel, "contentDetails")
        related = required_mapping(content_details, "relatedPlaylists")
        playlist_id = required_text(related, "uploads")
        self._playlist_by_account[account.account_id] = playlist_id
        return playlist_id


def _playlist_video_ids(payload: Mapping[str, Any]) -> tuple[str, ...]:
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise YouTubeResponseError("playlist_response_invalid")
    video_ids: list[str] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise YouTubeResponseError("playlist_response_invalid")
        details = required_mapping(item, "contentDetails")
        video_id = resource_id(
            details.get("videoId"), error_code="playlist_response_invalid"
        )
        if video_id in video_ids:
            raise YouTubeResponseError("playlist_response_invalid")
        video_ids.append(video_id)
    if len(video_ids) > 50:
        raise YouTubeResponseError("playlist_response_invalid")
    return tuple(video_ids)


def _videos_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise YouTubeResponseError("video_response_invalid")
    mapped: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise YouTubeResponseError("video_response_invalid")
        video_id = resource_id(item.get("id"), error_code="video_response_invalid")
        if video_id in mapped:
            raise YouTubeResponseError("video_response_invalid")
        mapped[video_id] = item
    return mapped


def _record(payload: Mapping[str, Any], observed_at: datetime) -> ProviderRecord:
    video_id = required_text(payload, "id")
    snippet = required_mapping(payload, "snippet")
    statistics = required_mapping(payload, "statistics")
    thumbnail = _thumbnail(snippet)
    likes = optional_count(statistics, "likeCount")
    comments = optional_count(statistics, "commentCount")
    visible_interactions = (
        likes + comments if likes is not None and comments is not None else None
    )
    candidates = (thumbnail,) if thumbnail else ()
    return ProviderRecord(
        external_id=video_id,
        observed_at=observed_at,
        fields={
            "content_type": "video",
            "permalink": f"https://www.youtube.com/watch?v={video_id}",
            "message": required_text(snippet, "title"),
            "media_url": thumbnail or "",
            "cover_url": thumbnail,
            "thumbnail_url": thumbnail,
            "cover_candidates": candidates,
            "thumbnail_candidates": candidates,
            "media_url_candidates": candidates,
            "published_at": _timestamp(snippet.get("publishedAt")),
            "likes_count": likes,
            "comments_count": comments,
            # The Data API deliberately exposes no per-video share counter.
            # Preserve absence; a later boundary must never invent a zero.
            "shares_count": None,
            "views_count": optional_count(statistics, "viewCount"),
            "reach_count": None,
            # The Data API exposes lifetime likes and comments but no
            # per-video share count. Preserve shares as unavailable while
            # making the sum of the two visible counters explicit.
            "interactions_count": visible_interactions,
        },
    )


def _thumbnail(snippet: Mapping[str, Any]) -> str | None:
    thumbnails = snippet.get("thumbnails")
    if thumbnails is None:
        return None
    if not isinstance(thumbnails, Mapping):
        raise YouTubeResponseError("response_field_invalid")
    for key in _THUMBNAIL_ORDER:
        candidate = thumbnails.get(key)
        if isinstance(candidate, Mapping) and (url := optional_text(candidate, "url")):
            return url
    return None


def _next_cursor(payload: Mapping[str, Any]) -> str | None:
    value = payload.get("nextPageToken")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise YouTubeResponseError("playlist_response_invalid")
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


__all__ = ["YouTubeContentReader"]

"""X user-post timeline normalization."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentPage
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .responses import XResponseError, optional_count, optional_text, required_mapping


class XContentReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount, str | None], Mapping[str, Any]],
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
        if account.platform is not PlatformId.X:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock()
        payload = self._fetch(account, cursor)
        items = payload.get("data", [])
        if not isinstance(items, list) or len(items) > 100:
            raise XResponseError("x_timeline_response_invalid")
        media = _media_by_key(payload)
        records = tuple(_record(item, media, observed_at) for item in items)
        if len({item.external_id for item in records}) != len(records):
            raise XResponseError("x_timeline_response_invalid")
        return ContentPage(
            items=records,
            next_cursor=_next_cursor(payload),
            observed_at=observed_at,
        )


def _record(
    raw: object,
    media: Mapping[str, Mapping[str, Any]],
    observed_at: datetime,
) -> ProviderRecord:
    if not isinstance(raw, Mapping):
        raise XResponseError("x_timeline_response_invalid")
    tweet_id = _numeric_id(raw.get("id"))
    public = required_mapping(raw, "public_metrics")
    private = raw.get("non_public_metrics", {})
    if not isinstance(private, Mapping):
        raise XResponseError("x_timeline_response_invalid")
    attached = _attached_media(raw, media)
    candidates = tuple(
        value
        for item in attached
        if (value := optional_text(item, "url") or optional_text(item, "preview_image_url"))
    )
    likes = optional_count(public, "like_count")
    replies = optional_count(public, "reply_count")
    reposts = optional_count(public, "retweet_count")
    quotes = optional_count(public, "quote_count")
    bookmarks = optional_count(public, "bookmark_count")
    interactions = optional_count(private, "engagements")
    if interactions is None:
        values = (likes, replies, reposts, quotes, bookmarks)
        interactions = sum(value or 0 for value in values) if any(
            value is not None for value in values
        ) else None
    media_url = candidates[0] if candidates else ""
    return ProviderRecord(
        external_id=tweet_id,
        observed_at=observed_at,
        fields={
            "content_type": _content_type(attached),
            "permalink": f"https://x.com/i/web/status/{tweet_id}",
            "message": optional_text(raw, "text") or "",
            "media_url": media_url,
            "cover_url": media_url or None,
            "thumbnail_url": media_url or None,
            "cover_candidates": candidates,
            "thumbnail_candidates": candidates,
            "media_url_candidates": candidates,
            "published_at": _timestamp(raw.get("created_at")),
            "likes_count": likes,
            "comments_count": replies,
            "replies_count": replies,
            "shares_count": _sum_optional(reposts, quotes),
            "views_count": optional_count(public, "impression_count"),
            "reach_count": None,
            "interactions_count": interactions,
            "saves_count": bookmarks,
            "profile_visits": optional_count(private, "user_profile_clicks"),
        },
    )


def _media_by_key(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    includes = payload.get("includes", {})
    if not isinstance(includes, Mapping):
        raise XResponseError("x_timeline_response_invalid")
    items = includes.get("media", [])
    if not isinstance(items, list) or len(items) > 400:
        raise XResponseError("x_timeline_response_invalid")
    mapped: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise XResponseError("x_timeline_response_invalid")
        key = str(item.get("media_key") or "").strip()
        if not key or key in mapped:
            raise XResponseError("x_timeline_response_invalid")
        mapped[key] = item
    return mapped


def _attached_media(
    tweet: Mapping[str, Any],
    media: Mapping[str, Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    attachments = tweet.get("attachments", {})
    if not isinstance(attachments, Mapping):
        raise XResponseError("x_timeline_response_invalid")
    keys = attachments.get("media_keys", [])
    if not isinstance(keys, list) or any(not isinstance(key, str) for key in keys):
        raise XResponseError("x_timeline_response_invalid")
    try:
        return tuple(media[key] for key in keys)
    except KeyError as exc:
        raise XResponseError("x_timeline_response_invalid") from exc


def _content_type(items: tuple[Mapping[str, Any], ...]) -> str:
    kinds = {optional_text(item, "type") for item in items}
    if "video" in kinds or "animated_gif" in kinds:
        return "video"
    if "photo" in kinds:
        return "image"
    return "post"


def _next_cursor(payload: Mapping[str, Any]) -> str | None:
    meta = payload.get("meta", {})
    if not isinstance(meta, Mapping):
        raise XResponseError("x_timeline_response_invalid")
    return optional_text(meta, "next_token")


def _numeric_id(value: object) -> str:
    if not isinstance(value, str) or not value.isdigit() or len(value) > 32:
        raise XResponseError("x_timeline_response_invalid")
    return value


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise XResponseError("x_timeline_response_invalid")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise XResponseError("x_timeline_response_invalid") from exc
    if parsed.tzinfo is None:
        raise XResponseError("x_timeline_response_invalid")
    return parsed.astimezone(UTC)


def _sum_optional(*values: int | None) -> int | None:
    return sum(value or 0 for value in values) if any(
        value is not None for value in values
    ) else None


__all__ = ["XContentReader"]

"""Instagram content and story capability reader."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentPage
from app.core.time import utc_now
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.fields import (
    nonnegative_int,
    optional_text,
    required_text,
    timestamp,
)
from app.infrastructure.providers.meta.transport import MetaTransport

from .content_insights import fetch_content_insights, map_content_insights

MEDIA_FIELDS = ",".join(
    (
        "id",
        "caption",
        "media_type",
        "media_product_type",
        "media_url",
        "thumbnail_url",
        "permalink",
        "timestamp",
        "like_count",
        "comments_count",
    )
)
STORY_FIELDS = ",".join(
    ("id", "media_type", "media_url", "thumbnail_url", "permalink", "timestamp")
)
class InstagramContentReader:
    def __init__(
        self,
        transport: MetaTransport,
        *,
        stories: bool = False,
        insights: bool = False,
        page_size: int = 100,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not 1 <= page_size <= 100:
            raise ValueError("content_page_size_invalid")
        self._transport = transport
        self._stories = stories
        self._insights = insights
        self._page_size = page_size
        self._clock = clock

    def list_content(
        self,
        account: ProviderAccount,
        *,
        cursor: str | None = None,
    ) -> ContentPage:
        if account.platform is not PlatformId.INSTAGRAM:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock()
        edge = "stories" if self._stories else "media"
        page = self._transport.page(
            f"{account.account_id}/{edge}",
            {"fields": STORY_FIELDS if self._stories else MEDIA_FIELDS, "limit": self._page_size},
            cursor=cursor,
        )
        items = tuple(_record(row, observed_at, story=self._stories) for row in page.items)
        if self._insights:
            items = tuple(self._with_insights(item, story=self._stories) for item in items)
        return ContentPage(
            items=items,
            next_cursor=page.next_cursor,
            observed_at=observed_at,
        )

    def _with_insights(self, item: ProviderRecord, *, story: bool) -> ProviderRecord:
        metrics = fetch_content_insights(self._transport, item.external_id, story=story)
        mapped = map_content_insights(metrics, story=story)
        fields = {**item.fields, **mapped}
        for count_field, metric_field in (
            ("likes_count", "likes"),
            ("comments_count", "comments"),
            ("shares_count", "shares"),
        ):
            if metric_field in metrics:
                fields[count_field] = int(metrics[metric_field])
        return ProviderRecord(
            external_id=item.external_id,
            observed_at=item.observed_at,
            fields=fields,
        )


def _record(
    payload: Mapping[str, Any], observed_at: datetime, *, story: bool
) -> ProviderRecord:
    media_url = optional_text(payload, "media_url") or optional_text(payload, "thumbnail_url")
    thumbnail_url = optional_text(payload, "thumbnail_url")
    direct_media_url = optional_text(payload, "media_url")
    media_type = (optional_text(payload, "media_type") or "post").lower()
    cover_candidates = _unique_texts(
        thumbnail_url if media_type == "video" else direct_media_url,
        direct_media_url,
        thumbnail_url,
    )
    return ProviderRecord(
        external_id=required_text(payload, "id"),
        observed_at=observed_at,
        fields={
            "content_type": (
                "story"
                if story
                else media_type
            ),
            "permalink": optional_text(payload, "permalink") or "",
            "message": optional_text(payload, "caption") or "",
            "media_url": media_url or "",
            "cover_url": cover_candidates[0] if cover_candidates else None,
            "thumbnail_url": thumbnail_url,
            "cover_candidates": cover_candidates,
            "thumbnail_candidates": _unique_texts(thumbnail_url),
            "media_url_candidates": _unique_texts(direct_media_url, thumbnail_url),
            "published_at": timestamp(payload, "timestamp"),
            "likes_count": nonnegative_int(payload, "like_count") or 0,
            "comments_count": nonnegative_int(payload, "comments_count") or 0,
            "shares_count": 0,
        },
    )


def _unique_texts(*values: str | None) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


__all__ = ["InstagramContentReader"]

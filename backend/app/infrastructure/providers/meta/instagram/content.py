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
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._transport = transport
        self._stories = stories
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
            {"fields": STORY_FIELDS if self._stories else MEDIA_FIELDS, "limit": 100},
            cursor=cursor,
        )
        return ContentPage(
            items=tuple(_record(row, observed_at, story=self._stories) for row in page.items),
            next_cursor=page.next_cursor,
            observed_at=observed_at,
        )


def _record(
    payload: Mapping[str, Any], observed_at: datetime, *, story: bool
) -> ProviderRecord:
    media_url = optional_text(payload, "media_url") or optional_text(payload, "thumbnail_url")
    return ProviderRecord(
        external_id=required_text(payload, "id"),
        observed_at=observed_at,
        fields={
            "content_type": (
                "story"
                if story
                else (optional_text(payload, "media_type") or "post").lower()
            ),
            "permalink": optional_text(payload, "permalink") or "",
            "message": optional_text(payload, "caption") or "",
            "media_url": media_url or "",
            "published_at": timestamp(payload, "timestamp"),
            "likes_count": nonnegative_int(payload, "like_count") or 0,
            "comments_count": nonnegative_int(payload, "comments_count") or 0,
            "shares_count": 0,
        },
    )


__all__ = ["InstagramContentReader"]

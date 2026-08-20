"""Facebook content capability reader."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentPage
from app.core.time import utc_now
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.fields import (
    nested_count,
    optional_text,
    required_text,
    timestamp,
)
from app.infrastructure.providers.meta.transport import MetaTransport

from .content_insights import fetch_content_insights, map_content_insights

FIELDS = ",".join(
    (
        "id",
        "created_time",
        "status_type",
        "message",
        "permalink_url",
        "full_picture",
        "reactions.summary(true).limit(0)",
        "comments.summary(true).limit(0)",
        "shares",
    )
)


class FacebookContentReader:
    def __init__(
        self,
        transport: MetaTransport,
        *,
        insights: bool = False,
        page_size: int = 100,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not 1 <= page_size <= 100:
            raise ValueError("content_page_size_invalid")
        self._transport = transport
        self._insights = insights
        self._page_size = page_size
        self._clock = clock

    def list_content(
        self,
        account: ProviderAccount,
        *,
        cursor: str | None = None,
    ) -> ContentPage:
        if account.platform is not PlatformId.FACEBOOK:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock()
        page = self._transport.page(
            f"{account.account_id}/published_posts",
            {"fields": FIELDS, "limit": self._page_size},
            cursor=cursor,
        )
        items = tuple(_record(row, observed_at) for row in page.items)
        if self._insights:
            items = tuple(self._with_insights(item) for item in items)
        return ContentPage(
            items=items,
            next_cursor=page.next_cursor,
            observed_at=observed_at,
        )

    def _with_insights(self, item: ProviderRecord) -> ProviderRecord:
        metrics = fetch_content_insights(self._transport, item.external_id)
        return ProviderRecord(
            external_id=item.external_id,
            observed_at=item.observed_at,
            fields={**item.fields, **map_content_insights(metrics)},
        )


def _record(payload: Mapping[str, Any], observed_at: datetime) -> ProviderRecord:
    shares = payload.get("shares")
    if shares is not None and not isinstance(shares, Mapping):
        raise ValueError("provider_count_field_invalid")
    media_url = optional_text(payload, "full_picture") or ""
    media_candidates = (media_url,) if media_url else ()
    return ProviderRecord(
        external_id=required_text(payload, "id"),
        observed_at=observed_at,
        fields={
            "content_type": optional_text(payload, "status_type") or "post",
            "permalink": optional_text(payload, "permalink_url") or "",
            "message": optional_text(payload, "message") or "",
            "media_url": media_url,
            "cover_url": media_url or None,
            "thumbnail_url": None,
            "cover_candidates": media_candidates,
            "thumbnail_candidates": (),
            "media_url_candidates": media_candidates,
            "published_at": timestamp(payload, "created_time"),
            "likes_count": nested_count(payload, MetricId.REACTIONS.value),
            "comments_count": nested_count(payload, "comments"),
            "shares_count": nested_count(payload, "shares"),
            "views_count": _optional_number(payload, "views_count"),
            "reach_count": _optional_number(payload, "reach_count"),
        },
    )


def _optional_number(payload: Mapping[str, Any], field: str) -> float | None:
    value = payload.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise ValueError("provider_numeric_field_invalid")
    return float(value)


__all__ = ["FacebookContentReader"]

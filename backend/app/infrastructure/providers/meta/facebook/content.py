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
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._transport = transport
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
            {"fields": FIELDS, "limit": 100},
            cursor=cursor,
        )
        return ContentPage(
            items=tuple(_record(row, observed_at) for row in page.items),
            next_cursor=page.next_cursor,
            observed_at=observed_at,
        )


def _record(payload: Mapping[str, Any], observed_at: datetime) -> ProviderRecord:
    shares = payload.get("shares")
    if shares is not None and not isinstance(shares, Mapping):
        raise ValueError("provider_count_field_invalid")
    return ProviderRecord(
        external_id=required_text(payload, "id"),
        observed_at=observed_at,
        fields={
            "content_type": optional_text(payload, "status_type") or "post",
            "permalink": optional_text(payload, "permalink_url") or "",
            "message": optional_text(payload, "message") or "",
            "media_url": optional_text(payload, "full_picture") or "",
            "published_at": timestamp(payload, "created_time"),
            "likes_count": nested_count(payload, MetricId.REACTIONS.value),
            "comments_count": nested_count(payload, "comments"),
            "shares_count": nested_count(payload, "shares"),
        },
    )


__all__ = ["FacebookContentReader"]

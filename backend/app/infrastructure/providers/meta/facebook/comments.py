"""Facebook comments capability reader."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.comments import CommentPage
from app.core.time import utc_now
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta.fields import (
    nonnegative_int,
    optional_text,
    required_text,
    timestamp,
)
from app.infrastructure.providers.meta.transport import MetaTransport


class FacebookCommentsReader:
    def __init__(
        self, transport: MetaTransport, *, clock: Callable[[], datetime] = utc_now
    ) -> None:
        self._transport = transport
        self._clock = clock

    def list_comments(
        self,
        account: ProviderAccount,
        *,
        content_id: str,
        cursor: str | None = None,
    ) -> CommentPage:
        if account.platform is not PlatformId.FACEBOOK:
            raise ValueError("provider_family_mismatch")
        if not content_id:
            raise ValueError("content_id_required")
        observed_at = self._clock()
        page = self._transport.page(
            f"{content_id}/comments",
            {
                "fields": (
                    "id,from,message,like_count,comment_count,created_time,attachment"
                ),
                "limit": 100,
            },
            cursor=cursor,
        )
        return CommentPage(
            content_id=content_id,
            items=tuple(_record(row, observed_at) for row in page.items),
            next_cursor=page.next_cursor,
            observed_at=observed_at,
        )


def _record(payload: Mapping[str, Any], observed_at: datetime) -> ProviderRecord:
    author = payload.get("from") or {}
    attachment = payload.get("attachment") or {}
    if not isinstance(author, Mapping) or not isinstance(attachment, Mapping):
        raise ValueError("provider_comment_shape_invalid")
    media = attachment.get("media") or {}
    image = media.get("image") if isinstance(media, Mapping) else {}
    if not isinstance(image, Mapping):
        image = {}
    return ProviderRecord(
        external_id=required_text(payload, "id"),
        observed_at=observed_at,
        fields={
            "author_id": optional_text(author, "id"),
            "author_name": optional_text(author, "name"),
            "text": optional_text(payload, "message") or "",
            "like_count": nonnegative_int(payload, "like_count") or 0,
            "reply_count": nonnegative_int(payload, "comment_count") or 0,
            "attachment_type": optional_text(attachment, "type"),
            "attachment_media_type": (
                optional_text(media, "type") if isinstance(media, Mapping) else None
            ),
            "attachment_url": optional_text(image, "src"),
            "commented_at": timestamp(payload, "created_time"),
        },
    )


__all__ = ["FacebookCommentsReader"]

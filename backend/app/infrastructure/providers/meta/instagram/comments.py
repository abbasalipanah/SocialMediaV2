"""Instagram comments capability reader."""

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


class InstagramCommentsReader:
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
        if account.platform is not PlatformId.INSTAGRAM:
            raise ValueError("provider_family_mismatch")
        if not content_id:
            raise ValueError("content_id_required")
        observed_at = self._clock()
        page = self._transport.page(
            f"{content_id}/comments",
            {"fields": "id,from,username,text,like_count,replies,timestamp", "limit": 100},
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
    replies = payload.get("replies") or {}
    if not isinstance(author, Mapping) or not isinstance(replies, Mapping):
        raise ValueError("provider_comment_shape_invalid")
    reply_rows = replies.get("data") or []
    if not isinstance(reply_rows, list):
        raise ValueError("provider_comment_shape_invalid")
    return ProviderRecord(
        external_id=required_text(payload, "id"),
        observed_at=observed_at,
        fields={
            "author_id": optional_text(author, "id"),
            "author_name": optional_text(payload, "username") or optional_text(author, "username"),
            "text": optional_text(payload, "text") or "",
            "like_count": nonnegative_int(payload, "like_count") or 0,
            "reply_count": len(reply_rows),
            "attachment_type": None,
            "attachment_media_type": None,
            "attachment_url": None,
            "commented_at": timestamp(payload, "timestamp"),
        },
    )


__all__ = ["InstagramCommentsReader"]

"""Comments capability port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.application.ports.platforms import ProviderAccount, ProviderRecord


@dataclass(frozen=True)
class CommentPage:
    content_id: str
    items: tuple[ProviderRecord, ...]
    next_cursor: str | None
    observed_at: datetime


class CommentsReader(Protocol):
    def list_comments(
        self,
        account: ProviderAccount,
        *,
        content_id: str,
        cursor: str | None = None,
    ) -> CommentPage: ...


__all__ = ["CommentPage", "CommentsReader"]

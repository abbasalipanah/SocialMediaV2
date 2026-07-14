"""Content capability port."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.application.ports.platforms import ProviderAccount, ProviderRecord


@dataclass(frozen=True)
class ContentPage:
    items: tuple[ProviderRecord, ...]
    next_cursor: str | None
    observed_at: datetime


class ContentReader(Protocol):
    def list_content(
        self, account: ProviderAccount, *, cursor: str | None = None
    ) -> ContentPage: ...


__all__ = ["ContentPage", "ContentReader"]

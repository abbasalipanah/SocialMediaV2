"""X account-mention normalization kept separate from owned-post analytics."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.core.time import utc_now
from app.domain.platforms import PlatformId

from .responses import XResponseError, optional_count, optional_text, required_mapping
from .wire import X_MENTIONS_PAGE_SIZE


@dataclass(frozen=True)
class XMentionPage:
    items: tuple[ProviderRecord, ...]
    next_cursor: str | None
    observed_at: datetime


class XMentionsReader:
    def __init__(
        self,
        fetch: Callable[[ProviderAccount, str | None], Mapping[str, Any]],
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._fetch = fetch
        self._clock = clock

    def list_mentions(
        self,
        account: ProviderAccount,
        *,
        cursor: str | None = None,
    ) -> XMentionPage:
        if account.platform is not PlatformId.X:
            raise ValueError("provider_family_mismatch")
        observed_at = self._clock()
        payload = self._fetch(account, cursor)
        items = payload.get("data", [])
        if not isinstance(items, list) or len(items) > X_MENTIONS_PAGE_SIZE:
            raise XResponseError("x_mentions_response_invalid")
        authors = _authors_by_id(payload)
        records = tuple(_record(item, authors, observed_at) for item in items)
        if len({item.external_id for item in records}) != len(records):
            raise XResponseError("x_mentions_response_invalid")
        return XMentionPage(
            items=records,
            next_cursor=_next_cursor(payload),
            observed_at=observed_at,
        )


def _record(
    raw: object,
    authors: Mapping[str, Mapping[str, Any]],
    observed_at: datetime,
) -> ProviderRecord:
    if not isinstance(raw, Mapping):
        raise XResponseError("x_mentions_response_invalid")
    mention_id = _numeric_id(raw.get("id"))
    author_id = optional_text(raw, "author_id")
    author = authors.get(author_id or "", {})
    username = optional_text(author, "username")
    metrics = required_mapping(raw, "public_metrics")
    return ProviderRecord(
        external_id=mention_id,
        observed_at=observed_at,
        fields={
            "author_id": author_id,
            "author_name": username or optional_text(author, "name"),
            "text": optional_text(raw, "text") or "",
            "like_count": optional_count(metrics, "like_count") or 0,
            "reply_count": optional_count(metrics, "reply_count") or 0,
            "commented_at": _timestamp(raw.get("created_at")),
        },
    )


def _authors_by_id(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    includes = payload.get("includes", {})
    if not isinstance(includes, Mapping):
        raise XResponseError("x_mentions_response_invalid")
    items = includes.get("users", [])
    if not isinstance(items, list) or len(items) > X_MENTIONS_PAGE_SIZE:
        raise XResponseError("x_mentions_response_invalid")
    mapped: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise XResponseError("x_mentions_response_invalid")
        user_id = _numeric_id(item.get("id"))
        if user_id in mapped:
            raise XResponseError("x_mentions_response_invalid")
        mapped[user_id] = item
    return mapped


def _next_cursor(payload: Mapping[str, Any]) -> str | None:
    meta = payload.get("meta", {})
    if not isinstance(meta, Mapping):
        raise XResponseError("x_mentions_response_invalid")
    return optional_text(meta, "next_token")


def _numeric_id(value: object) -> str:
    if not isinstance(value, str) or not value.isdigit() or len(value) > 32:
        raise XResponseError("x_mentions_response_invalid")
    return value


def _timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise XResponseError("x_mentions_response_invalid")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise XResponseError("x_mentions_response_invalid") from exc
    if parsed.tzinfo is None:
        raise XResponseError("x_mentions_response_invalid")
    return parsed.astimezone(UTC)


__all__ = ["XMentionPage", "XMentionsReader"]

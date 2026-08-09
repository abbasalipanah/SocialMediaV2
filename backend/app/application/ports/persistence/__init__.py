"""Backend-owned metric, content, comment, and media persistence ports."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from app.application.queries.metrics import MetricQuery
from app.domain.metrics import MetricId
from app.domain.platforms import PlatformId


def _positive(value: int, label: str) -> None:
    if value < 1:
        raise ValueError(f"{label}_invalid")


def _required(value: str, label: str) -> None:
    if not value.strip():
        raise ValueError(f"{label}_required")


@dataclass(frozen=True)
class MetricPoint:
    platform: PlatformId
    account_id: int
    brand_id: int
    observed_on: date
    metric_id: MetricId
    value: float | int
    breakdown_key: str | None = None
    breakdown_value: str | None = None

    def __post_init__(self) -> None:
        _positive(self.account_id, "account_id")
        _positive(self.brand_id, "brand_id")
        if isinstance(self.value, bool) or not math.isfinite(float(self.value)):
            raise ValueError("metric_value_invalid")
        if (self.breakdown_key is None) is not (self.breakdown_value is None):
            raise ValueError("metric_breakdown_incomplete")


@dataclass(frozen=True)
class ContentRecord:
    platform: PlatformId
    account_id: int
    brand_id: int
    external_content_id: str
    content_type: str
    permalink: str
    message: str
    media_url: str
    published_at: datetime | None
    likes_count: int
    comments_count: int
    shares_count: int
    views_count: float | None = None
    reach_count: float | None = None
    cover_url: str | None = None
    thumbnail_url: str | None = None
    cover_candidates: tuple[str, ...] = ()
    thumbnail_candidates: tuple[str, ...] = ()
    media_url_candidates: tuple[str, ...] = ()
    full_video_watched_rate: float | None = None
    total_time_watched: float | None = None
    average_time_watched: float | None = None
    interactions_count: float | None = None
    replies_count: float | None = None
    saves_count: float | None = None
    sticker_taps: float | None = None
    profile_visits: float | None = None
    follows_count: float | None = None
    taps_forward: float | None = None
    taps_back: float | None = None
    swipe_forward: float | None = None
    exits: float | None = None
    navigation_count: float | None = None
    completion_rate: float | None = None

    def __post_init__(self) -> None:
        _positive(self.account_id, "account_id")
        _positive(self.brand_id, "brand_id")
        _required(self.external_content_id, "external_content_id")
        if min(self.likes_count, self.comments_count, self.shares_count) < 0:
            raise ValueError("content_count_invalid")
        optional_values = (
            self.views_count,
            self.reach_count,
            self.full_video_watched_rate,
            self.total_time_watched,
            self.average_time_watched,
            self.interactions_count,
            self.replies_count,
            self.saves_count,
            self.sticker_taps,
            self.profile_visits,
            self.follows_count,
            self.taps_forward,
            self.taps_back,
            self.swipe_forward,
            self.exits,
            self.navigation_count,
            self.completion_rate,
        )
        if any(
            value is not None
            and (isinstance(value, bool) or not math.isfinite(float(value)) or float(value) < 0)
            for value in optional_values
        ):
            raise ValueError("content_metric_invalid")
        for candidates in (
            self.cover_candidates,
            self.thumbnail_candidates,
            self.media_url_candidates,
        ):
            if len(candidates) != len(set(candidates)) or any(
                not isinstance(value, str) or not value.strip() for value in candidates
            ):
                raise ValueError("content_media_candidates_invalid")


@dataclass(frozen=True)
class CommentRecord:
    platform: PlatformId
    account_id: int
    external_content_id: str
    external_comment_id: str
    author_id: str | None
    author_name: str | None
    text: str
    like_count: int
    reply_count: int
    answered: bool
    attachment_type: str | None
    attachment_media_type: str | None
    attachment_url: str | None
    commented_at: datetime | None

    def __post_init__(self) -> None:
        _positive(self.account_id, "account_id")
        _required(self.external_content_id, "external_content_id")
        _required(self.external_comment_id, "external_comment_id")
        if min(self.like_count, self.reply_count) < 0:
            raise ValueError("comment_count_invalid")


@dataclass(frozen=True)
class MediaRecord:
    platform: PlatformId
    account_id: int
    brand_id: int
    external_content_id: str
    media_kind: str
    storage_path: str
    source_url: str
    source_status: int | None
    mime_type: str
    size_bytes: int
    checksum: str
    verified_at: datetime | None

    def __post_init__(self) -> None:
        _positive(self.account_id, "account_id")
        _positive(self.brand_id, "brand_id")
        _required(self.external_content_id, "external_content_id")
        _required(self.media_kind, "media_kind")
        if self.size_bytes < 0:
            raise ValueError("media_size_invalid")


class MetricStore(Protocol):
    def upsert(self, point: MetricPoint) -> None: ...

    def read(
        self,
        *,
        account_id: int,
        start_on: date,
        end_on: date,
        query: MetricQuery,
    ) -> tuple[MetricPoint, ...]: ...

    def replace_breakdown(
        self,
        *,
        platform: PlatformId,
        account_id: int,
        brand_id: int,
        observed_on: date,
        metric_id: MetricId,
        breakdown_key: str,
        values: Mapping[str, float | int],
    ) -> None: ...


class ContentStore(Protocol):
    def upsert(self, record: ContentRecord) -> None: ...

    def list_for_account(self, account_id: int) -> tuple[ContentRecord, ...]: ...


class CommentStore(Protocol):
    def upsert(self, record: CommentRecord) -> None: ...

    def list_for_content(
        self, account_id: int, external_content_id: str
    ) -> tuple[CommentRecord, ...]: ...


class MediaStore(Protocol):
    def upsert(self, record: MediaRecord) -> None: ...

    def get(
        self, account_id: int, external_content_id: str, media_kind: str
    ) -> MediaRecord | None: ...


__all__ = [
    "CommentRecord",
    "CommentStore",
    "ContentRecord",
    "ContentStore",
    "MediaRecord",
    "MediaStore",
    "MetricPoint",
    "MetricStore",
]

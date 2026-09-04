"""Bounded collection orchestration for X profiles and user posts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.ports.checkpoints import CheckpointKey, CheckpointStore, ProviderCheckpoint
from app.application.ports.persistence import CommentRecord, CommentStore, ContentStore, MetricStore
from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentReader
from app.application.ports.platforms.profile import ProfileReader
from app.application.services.collection import (
    CollectionOutcome,
    CollectionStatus,
    CollectionTarget,
    collect_content,
    collect_profile,
)
from app.core import XConfig
from app.domain.platforms import X_MENTIONS_CONTENT_ID, CapabilityId, PlatformId
from app.infrastructure.providers.x import (
    XContentReader,
    XHttpTransport,
    XMentionsReader,
    XProfileReader,
    authenticated_user_query,
    user_mentions_query,
    user_mentions_url,
    user_posts_query,
    user_posts_url,
)

X_CONTENT_PAGES_PER_RUN = 1
X_MENTION_PAGES_PER_RUN = 1


@dataclass(frozen=True)
class XReaders:
    profile: ProfileReader
    content: ContentReader
    mentions: XMentionsReader


@dataclass(frozen=True)
class XCollectionResult:
    status: str
    metric_count: int
    content_count: int
    comment_count: int
    media_count: int
    error_code: str | None
    backfill_complete: bool


def create_x_readers(
    *,
    config: XConfig,
    account: ProviderAccount,
    timeout_seconds: float,
) -> XReaders:
    if account.platform is not PlatformId.X:
        raise ValueError("provider_family_mismatch")
    posts_url = user_posts_url(config.api_base_url, account.account_id)
    mentions_url = user_mentions_url(config.api_base_url, account.account_id)
    transport = XHttpTransport(
        get_urls=(config.users_me_url, posts_url, mentions_url),
        timeout_seconds=timeout_seconds,
        max_retries=3,
        request_budget=100,
    )
    token = account.credential.access_token

    def get(url: str, params: dict[str, str]):
        return transport.get(url, access_token=token, params=params)

    return XReaders(
        profile=XProfileReader(
            lambda _selected: get(config.users_me_url, authenticated_user_query())
        ),
        content=XContentReader(
            lambda _selected, cursor: get(
                posts_url,
                user_posts_query(cursor=cursor),
            )
        ),
        mentions=XMentionsReader(
            lambda _selected, cursor: get(
                mentions_url,
                user_mentions_query(cursor=cursor),
            )
        ),
    )


def collect_x_mentions(
    *,
    target: CollectionTarget,
    reader: XMentionsReader,
    comment_store: CommentStore,
    checkpoint_store: CheckpointStore,
    max_pages: int = X_MENTION_PAGES_PER_RUN,
) -> CollectionOutcome:
    """Persist a bounded mention stream without mixing it with owned posts."""
    if max_pages < 1 or max_pages > 100:
        raise ValueError("x_mentions_page_limit_invalid")
    key = CheckpointKey(
        platform=PlatformId.X,
        capability=CapabilityId.COMMENTS,
        account_id=f"{target.account.account_id}.mentions",
    )
    checkpoint = checkpoint_store.get(key)
    cursor = checkpoint.cursor if checkpoint is not None else None
    comment_count = 0
    page_count = 0
    while page_count < max_pages:
        page = reader.list_mentions(target.account, cursor=cursor)
        for item in page.items:
            comment_store.upsert(_mention_record(target, item))
            comment_count += 1
        next_checkpoint = ProviderCheckpoint(
            key=key,
            version=1 if checkpoint is None else checkpoint.version + 1,
            cursor=page.next_cursor,
            watermark=max((item.external_id for item in page.items), default=None),
            observed_through=page.observed_at,
        )
        expected_version = checkpoint.version if checkpoint is not None else None
        if not checkpoint_store.put(next_checkpoint, expected_version=expected_version):
            return CollectionOutcome(
                status=CollectionStatus.PARTIAL,
                comment_count=comment_count,
                page_count=page_count + 1,
                next_cursor=page.next_cursor,
                error_code="checkpoint_retry_required",
            )
        checkpoint = next_checkpoint
        cursor = checkpoint.cursor
        page_count += 1
        if cursor is None:
            return CollectionOutcome(
                status=CollectionStatus.SUCCESS,
                comment_count=comment_count,
                page_count=page_count,
            )
    return CollectionOutcome(
        status=CollectionStatus.PARTIAL,
        comment_count=comment_count,
        page_count=page_count,
        next_cursor=cursor,
        error_code="page_limit_reached",
    )


def _mention_record(target: CollectionTarget, item: ProviderRecord) -> CommentRecord:
    fields = item.fields
    author_id = fields.get("author_id")
    author_name = fields.get("author_name")
    text = fields.get("text")
    like_count = fields.get("like_count")
    reply_count = fields.get("reply_count")
    commented_at = fields.get("commented_at")
    if (
        (author_id is not None and not isinstance(author_id, str))
        or (author_name is not None and not isinstance(author_name, str))
        or not isinstance(text, str)
        or isinstance(like_count, bool)
        or not isinstance(like_count, int)
        or isinstance(reply_count, bool)
        or not isinstance(reply_count, int)
        or (
            commented_at is not None
            and (
                not isinstance(commented_at, datetime)
                or commented_at.tzinfo is None
            )
        )
    ):
        raise ValueError("provider_mention_field_invalid")
    return CommentRecord(
        platform=PlatformId.X,
        account_id=target.local_account_id,
        external_content_id=X_MENTIONS_CONTENT_ID,
        external_comment_id=item.external_id,
        author_id=author_id,
        author_name=author_name,
        text=text,
        like_count=like_count,
        reply_count=reply_count,
        answered=False,
        attachment_type=None,
        attachment_media_type=None,
        attachment_url=None,
        commented_at=commented_at,
    )


def collect_x_account(
    *,
    account: ProviderAccount,
    local_account_id: int,
    brand_id: int,
    readers: XReaders,
    metric_store: MetricStore,
    content_store: ContentStore,
    comment_store: CommentStore,
    checkpoint_store: CheckpointStore,
    persist_media: Callable[[CollectionTarget, ProviderRecord], int],
    backfill_complete: bool,
) -> XCollectionResult:
    if account.platform is not PlatformId.X:
        raise ValueError("provider_family_mismatch")
    target = CollectionTarget(
        account=account,
        local_account_id=local_account_id,
        brand_id=brand_id,
    )
    partial_errors: set[str] = set()
    metric_count = 0
    try:
        profile = collect_profile(
            target=target,
            reader=readers.profile,
            metric_store=metric_store,
        )
        metric_count = profile.metric_count
        if profile.status is not CollectionStatus.SUCCESS:
            partial_errors.add("profile_partial")
    except Exception:
        partial_errors.add("profile_unavailable")

    media_count = 0

    def persist_related(item: ProviderRecord) -> int:
        try:
            return persist_media(target, item)
        except Exception:
            partial_errors.add("media_unavailable")
            return 0

    content_count = 0
    archive_complete = backfill_complete
    try:
        content = collect_content(
            target=target,
            reader=readers.content,
            content_store=content_store,
            checkpoint_store=checkpoint_store,
            record_sink=persist_related,
            max_pages=X_CONTENT_PAGES_PER_RUN,
            refresh_only=backfill_complete,
        )
        content_count = content.content_count
        media_count = content.media_count
        archive_complete = backfill_complete or content.status is CollectionStatus.SUCCESS
        if content.status is not CollectionStatus.SUCCESS:
            partial_errors.add("content_partial")
    except Exception:
        partial_errors.add("content_unavailable")
    comment_count = 0
    try:
        mentions = collect_x_mentions(
            target=target,
            reader=readers.mentions,
            comment_store=comment_store,
            checkpoint_store=checkpoint_store,
        )
        comment_count = mentions.comment_count
        if mentions.status is not CollectionStatus.SUCCESS:
            partial_errors.add("mentions_partial")
    except Exception:
        partial_errors.add("mentions_unavailable")
    return XCollectionResult(
        status="partial" if partial_errors else "success",
        metric_count=metric_count,
        content_count=content_count,
        comment_count=comment_count,
        media_count=media_count,
        error_code=",".join(sorted(partial_errors))[:256] or None,
        backfill_complete=archive_complete,
    )


__all__ = [
    "X_CONTENT_PAGES_PER_RUN",
    "X_MENTION_PAGES_PER_RUN",
    "X_MENTIONS_CONTENT_ID",
    "XCollectionResult",
    "XReaders",
    "collect_x_account",
    "collect_x_mentions",
    "create_x_readers",
]

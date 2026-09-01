"""Bounded collection orchestration for X profiles and user posts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.application.ports.checkpoints import CheckpointStore
from app.application.ports.persistence import ContentStore, MetricStore
from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.content import ContentReader
from app.application.ports.platforms.profile import ProfileReader
from app.application.services.collection import (
    CollectionStatus,
    CollectionTarget,
    collect_content,
    collect_profile,
)
from app.core import XConfig
from app.domain.platforms import PlatformId
from app.infrastructure.providers.x import (
    XContentReader,
    XHttpTransport,
    XProfileReader,
    authenticated_user_query,
    user_posts_query,
    user_posts_url,
)

X_CONTENT_PAGES_PER_RUN = 1


@dataclass(frozen=True)
class XReaders:
    profile: ProfileReader
    content: ContentReader


@dataclass(frozen=True)
class XCollectionResult:
    status: str
    metric_count: int
    content_count: int
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
    transport = XHttpTransport(
        get_urls=(config.users_me_url, posts_url),
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
    )


def collect_x_account(
    *,
    account: ProviderAccount,
    local_account_id: int,
    brand_id: int,
    readers: XReaders,
    metric_store: MetricStore,
    content_store: ContentStore,
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
    return XCollectionResult(
        status="partial" if partial_errors else "success",
        metric_count=metric_count,
        content_count=content_count,
        media_count=media_count,
        error_code=",".join(sorted(partial_errors))[:256] or None,
        backfill_complete=archive_complete,
    )


__all__ = [
    "X_CONTENT_PAGES_PER_RUN",
    "XCollectionResult",
    "XReaders",
    "collect_x_account",
    "create_x_readers",
]

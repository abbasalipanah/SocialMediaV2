"""Bounded YouTube collection orchestration outside the shared worker shell."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.application.ports.checkpoints import (
    CheckpointKey,
    CheckpointStore,
    ProviderCheckpoint,
)
from app.application.ports.persistence import CommentStore, ContentStore, MetricStore
from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.comments import CommentsReader
from app.application.ports.platforms.content import ContentReader
from app.application.ports.platforms.profile import DailyMetricsReader, ProfileReader
from app.application.services.collection import (
    CollectionStatus,
    CollectionTarget,
    collect_comments,
    collect_content,
    collect_daily_metrics,
    collect_profile,
)
from app.core import YouTubeConfig
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.providers.youtube import (
    YouTubeCommentsReader,
    YouTubeContentReader,
    YouTubeDailyMetricsReader,
    YouTubeHttpTransport,
    YouTubeProfileReader,
    channel_query,
    comment_threads_query,
    daily_metrics_query,
    playlist_items_query,
    uploads_playlist_query,
    videos_query,
)

YOUTUBE_DAILY_CHECKPOINT_SUFFIX = "daily-metrics-v1"
YOUTUBE_DAILY_BACKFILL_DAYS = 30
YOUTUBE_CONTENT_PAGES_PER_RUN = 1
YOUTUBE_COMMENTED_CONTENT_PER_RUN = 10
YOUTUBE_COMMENT_PAGES_PER_CONTENT = 5


@dataclass(frozen=True)
class YouTubeReaders:
    profile: ProfileReader
    daily: DailyMetricsReader
    content: ContentReader
    comments: CommentsReader


@dataclass(frozen=True)
class YouTubeCollectionResult:
    status: str
    metric_count: int
    content_count: int
    comment_count: int
    media_count: int
    error_code: str | None
    backfill_complete: bool


def create_youtube_readers(
    *,
    config: YouTubeConfig,
    account: ProviderAccount,
    timeout_seconds: float,
) -> YouTubeReaders:
    if account.platform is not PlatformId.YOUTUBE:
        raise ValueError("provider_family_mismatch")
    transport = YouTubeHttpTransport(
        get_urls=(
            config.channels_url,
            config.playlist_items_url,
            config.videos_url,
            config.comment_threads_url,
            config.analytics_reports_url,
        ),
        timeout_seconds=timeout_seconds,
        max_retries=3,
        request_budget=500,
    )
    token = account.credential.access_token

    def get(url: str, params: dict[str, str]):
        return transport.get(url, access_token=token, params=params)

    return YouTubeReaders(
        profile=YouTubeProfileReader(
            lambda selected: get(config.channels_url, channel_query(selected.account_id))
        ),
        daily=YouTubeDailyMetricsReader(
            lambda _selected, since, until: get(
                config.analytics_reports_url,
                daily_metrics_query(since=since, until=until),
            )
        ),
        content=YouTubeContentReader(
            lambda selected: get(
                config.channels_url,
                uploads_playlist_query(selected.account_id),
            ),
            lambda _selected, playlist_id, cursor: get(
                config.playlist_items_url,
                playlist_items_query(playlist_id, cursor=cursor),
            ),
            lambda _selected, video_ids: get(
                config.videos_url,
                videos_query(video_ids),
            ),
        ),
        comments=YouTubeCommentsReader(
            lambda _selected, video_id, cursor: get(
                config.comment_threads_url,
                comment_threads_query(video_id, cursor=cursor),
            )
        ),
    )


def collect_youtube_account(
    *,
    account: ProviderAccount,
    local_account_id: int,
    brand_id: int,
    readers: YouTubeReaders,
    metric_store: MetricStore,
    content_store: ContentStore,
    comment_store: CommentStore,
    checkpoint_store: CheckpointStore,
    persist_media: Callable[[CollectionTarget, ProviderRecord], int],
    backfill_complete: bool,
    today: date | None = None,
) -> YouTubeCollectionResult:
    if account.platform is not PlatformId.YOUTUBE:
        raise ValueError("provider_family_mismatch")
    target = CollectionTarget(
        account=account,
        local_account_id=local_account_id,
        brand_id=brand_id,
    )
    partial_errors: set[str] = set()
    profile = collect_profile(target=target, reader=readers.profile, metric_store=metric_store)
    if profile.status is not CollectionStatus.SUCCESS:
        partial_errors.add("profile_partial")

    observed_today = today or date.today()
    daily_count = _collect_daily(
        target=target,
        reader=readers.daily,
        metric_store=metric_store,
        checkpoint_store=checkpoint_store,
        today=observed_today,
        partial_errors=partial_errors,
    )
    comment_count = 0
    commented = 0

    def persist_related(item: ProviderRecord) -> int:
        nonlocal comment_count, commented
        if commented < YOUTUBE_COMMENTED_CONTENT_PER_RUN:
            commented += 1
            try:
                outcome = collect_comments(
                    target=target,
                    content_id=item.external_id,
                    reader=readers.comments,
                    comment_store=comment_store,
                    max_pages=YOUTUBE_COMMENT_PAGES_PER_CONTENT,
                )
                comment_count += outcome.comment_count
                if outcome.status is not CollectionStatus.SUCCESS:
                    partial_errors.add("comments_partial")
            except Exception:
                partial_errors.add("comments_unavailable")
        try:
            return persist_media(target, item)
        except Exception:
            partial_errors.add("media_unavailable")
            return 0

    content_count = 0
    media_count = 0
    archive_complete = backfill_complete
    try:
        content = collect_content(
            target=target,
            reader=readers.content,
            content_store=content_store,
            checkpoint_store=checkpoint_store,
            record_sink=persist_related,
            max_pages=YOUTUBE_CONTENT_PAGES_PER_RUN,
            refresh_only=backfill_complete,
        )
        content_count = content.content_count
        media_count = content.media_count
        archive_complete = backfill_complete or content.status is CollectionStatus.SUCCESS
        if content.status is not CollectionStatus.SUCCESS:
            partial_errors.add("content_partial")
    except Exception:
        partial_errors.add("content_unavailable")
    return YouTubeCollectionResult(
        status="partial" if partial_errors else "success",
        metric_count=profile.metric_count + daily_count,
        content_count=content_count,
        comment_count=comment_count,
        media_count=media_count,
        error_code=",".join(sorted(partial_errors))[:256] or None,
        backfill_complete=archive_complete,
    )


def _collect_daily(
    *,
    target: CollectionTarget,
    reader: DailyMetricsReader,
    metric_store: MetricStore,
    checkpoint_store: CheckpointStore,
    today: date,
    partial_errors: set[str],
) -> int:
    until = today - timedelta(days=1)
    key = CheckpointKey(
        platform=PlatformId.YOUTUBE,
        capability=CapabilityId.PROFILE,
        account_id=f"{target.account.account_id}.{YOUTUBE_DAILY_CHECKPOINT_SUFFIX}",
    )
    checkpoint = checkpoint_store.get(key)
    lower_bound = today - timedelta(days=YOUTUBE_DAILY_BACKFILL_DAYS)
    since = lower_bound
    if checkpoint is not None and checkpoint.observed_through is not None:
        since = max(
            lower_bound,
            min(until, checkpoint.observed_through.astimezone(UTC).date()),
        )
    try:
        outcome = collect_daily_metrics(
            target=target,
            reader=reader,
            metric_store=metric_store,
            since=since,
            until=until,
        )
        if outcome.status is not CollectionStatus.SUCCESS:
            partial_errors.add("daily_partial")
        next_checkpoint = ProviderCheckpoint(
            key=key,
            version=1 if checkpoint is None else checkpoint.version + 1,
            cursor=None,
            watermark=until.isoformat(),
            observed_through=datetime.combine(until, datetime.min.time(), tzinfo=UTC),
        )
        checkpoint_store.put(
            next_checkpoint,
            expected_version=checkpoint.version if checkpoint is not None else None,
        )
        return outcome.metric_count
    except Exception:
        partial_errors.add("daily_unavailable")
        return 0


__all__ = [
    "YOUTUBE_COMMENTED_CONTENT_PER_RUN",
    "YOUTUBE_CONTENT_PAGES_PER_RUN",
    "YOUTUBE_DAILY_BACKFILL_DAYS",
    "YouTubeCollectionResult",
    "YouTubeReaders",
    "collect_youtube_account",
    "create_youtube_readers",
]

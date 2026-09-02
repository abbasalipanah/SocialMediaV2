"""Bounded collection orchestration for LinkedIn Company Pages."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.application.ports.checkpoints import CheckpointKey, CheckpointStore, ProviderCheckpoint
from app.application.ports.persistence import ContentStore, MetricStore
from app.application.ports.platforms import ProviderAccount, ProviderRecord
from app.application.ports.platforms.audience import AudienceReader
from app.application.ports.platforms.content import ContentReader
from app.application.ports.platforms.profile import DailyMetricsReader, ProfileReader
from app.application.services.collection import (
    CollectionStatus,
    CollectionTarget,
    collect_audience,
    collect_content,
    collect_daily_metrics,
    collect_profile,
)
from app.core import LinkedInConfig
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.providers.linkedin import (
    LinkedInAudienceReader,
    LinkedInContentReader,
    LinkedInDailyMetricsReader,
    LinkedInHttpTransport,
    LinkedInProfileReader,
    follower_statistics_query,
    network_size_query,
    network_size_url,
    organization_url,
    page_statistics_query,
    post_statistics_queries,
    posts_query,
    share_statistics_query,
)

LINKEDIN_DAILY_CHECKPOINT_SUFFIX = "daily-metrics-v1"
LINKEDIN_DAILY_BACKFILL_DAYS = 30
LINKEDIN_CONTENT_PAGES_PER_RUN = 1


@dataclass(frozen=True)
class LinkedInReaders:
    profile: ProfileReader
    daily: DailyMetricsReader
    content: ContentReader
    audience: AudienceReader


@dataclass(frozen=True)
class LinkedInCollectionResult:
    status: str
    metric_count: int
    content_count: int
    media_count: int
    error_code: str | None
    backfill_complete: bool


def create_linkedin_readers(
    *,
    config: LinkedInConfig,
    account: ProviderAccount,
    timeout_seconds: float,
) -> LinkedInReaders:
    if account.platform is not PlatformId.LINKEDIN:
        raise ValueError("provider_family_mismatch")
    selected_organization_url = organization_url(config.organizations_url, account.account_id)
    selected_network_url = network_size_url(config.network_sizes_url, account.account_id)
    transport = LinkedInHttpTransport(
        get_urls=(
            selected_organization_url,
            selected_network_url,
            config.posts_url,
            config.share_statistics_url,
            config.follower_statistics_url,
            config.page_statistics_url,
        ),
        api_version=config.api_version,
        timeout_seconds=timeout_seconds,
        max_retries=3,
        # Development tier allows only 500 calls per app/day. This is a hard
        # per-account safety ceiling; a normal run uses at most nine calls.
        request_budget=20,
    )
    token = account.credential.access_token

    def get(url: str, params: dict[str, str], *, finder: bool = False):
        return transport.get(
            url,
            access_token=token,
            params=params,
            finder=finder,
        )

    def fetch_post_statistics(
        selected: ProviderAccount,
        post_urns: tuple[str, ...],
    ):
        return tuple(
            get(config.share_statistics_url, query, finder=True)
            for query in post_statistics_queries(selected.account_id, post_urns)
        )

    return LinkedInReaders(
        profile=LinkedInProfileReader(
            lambda _selected: get(selected_organization_url, {}),
            lambda _selected: get(selected_network_url, network_size_query()),
        ),
        daily=LinkedInDailyMetricsReader(
            lambda selected, since, until: get(
                config.share_statistics_url,
                share_statistics_query(selected.account_id, since=since, until=until),
                finder=True,
            ),
            lambda selected, since, until: get(
                config.follower_statistics_url,
                follower_statistics_query(selected.account_id, since=since, until=until),
                finder=True,
            ),
            lambda selected, since, until: get(
                config.page_statistics_url,
                page_statistics_query(selected.account_id, since=since, until=until),
                finder=True,
            ),
        ),
        content=LinkedInContentReader(
            lambda selected, cursor: get(
                config.posts_url,
                posts_query(selected.account_id, cursor=cursor),
                finder=True,
            ),
            fetch_post_statistics,
        ),
        audience=LinkedInAudienceReader(
            lambda selected: get(
                config.follower_statistics_url,
                follower_statistics_query(selected.account_id),
                finder=True,
            )
        ),
    )


def collect_linkedin_account(
    *,
    account: ProviderAccount,
    local_account_id: int,
    brand_id: int,
    readers: LinkedInReaders,
    metric_store: MetricStore,
    content_store: ContentStore,
    checkpoint_store: CheckpointStore,
    persist_media: Callable[[CollectionTarget, ProviderRecord], int],
    backfill_complete: bool,
    today: date | None = None,
) -> LinkedInCollectionResult:
    if account.platform is not PlatformId.LINKEDIN:
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
    metric_count = profile.metric_count
    metric_count += _collect_daily(
        target=target,
        reader=readers.daily,
        metric_store=metric_store,
        checkpoint_store=checkpoint_store,
        today=today or date.today(),
        partial_errors=partial_errors,
    )
    try:
        audience = collect_audience(
            target=target,
            reader=readers.audience,
            metric_store=metric_store,
        )
        metric_count += audience.metric_count
        if audience.status is not CollectionStatus.SUCCESS:
            partial_errors.add("audience_partial")
    except Exception:
        partial_errors.add("audience_unavailable")

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
            max_pages=LINKEDIN_CONTENT_PAGES_PER_RUN,
            refresh_only=backfill_complete,
        )
        content_count = content.content_count
        media_count = content.media_count
        archive_complete = backfill_complete or content.status is CollectionStatus.SUCCESS
        if content.status is not CollectionStatus.SUCCESS:
            partial_errors.add("content_partial")
    except Exception:
        partial_errors.add("content_unavailable")
    return LinkedInCollectionResult(
        status="partial" if partial_errors else "success",
        metric_count=metric_count,
        content_count=content_count,
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
        platform=PlatformId.LINKEDIN,
        capability=CapabilityId.PROFILE,
        account_id=(f"{target.account.account_id}.{LINKEDIN_DAILY_CHECKPOINT_SUFFIX}"),
    )
    checkpoint = checkpoint_store.get(key)
    lower_bound = today - timedelta(days=LINKEDIN_DAILY_BACKFILL_DAYS)
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
        if not checkpoint_store.put(
            next_checkpoint,
            expected_version=checkpoint.version if checkpoint is not None else None,
        ):
            partial_errors.add("daily_checkpoint_retry_required")
        return outcome.metric_count
    except Exception:
        partial_errors.add("daily_unavailable")
        return 0


__all__ = [
    "LINKEDIN_CONTENT_PAGES_PER_RUN",
    "LINKEDIN_DAILY_BACKFILL_DAYS",
    "LinkedInCollectionResult",
    "LinkedInReaders",
    "collect_linkedin_account",
    "create_linkedin_readers",
]

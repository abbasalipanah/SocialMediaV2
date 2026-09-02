"""Standalone V2 collection runner for linked Meta and TikTok accounts."""

from __future__ import annotations

import argparse
import json
import logging
import re
import signal
import threading
import time
import traceback
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import Engine, create_engine, text

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.credentials import CredentialRef, SecretToken, TokenKind
from app.application.ports.persistence import ContentRecord
from app.application.ports.platforms import (
    ProviderAccount,
    ProviderCredential,
    ProviderRecord,
)
from app.application.ports.platforms.comments import CommentsReader
from app.application.ports.platforms.content import ContentReader
from app.application.ports.platforms.profile import DailyMetricsReader, ProfileReader
from app.application.services.collection import (
    CollectionStatus,
    CollectionTarget,
    collect_audience,
    collect_comments,
    collect_content,
    collect_daily_metrics,
    collect_profile,
)
from app.application.services.collection.media import (
    ContentMediaWriter,
    FetchedMedia,
    MediaBudgetDeferred,
)
from app.core import AppSettings, ConfigurationError, WritePolicy, load_settings
from app.domain.metrics import (
    FACEBOOK_DAILY_SOURCE_METRICS,
    INSTAGRAM_DAILY_SOURCE_METRICS,
    MetricId,
    bootstrap_metric_catalog,
)
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore
from app.infrastructure.persistence.media_files import AtomicMediaFiles
from app.infrastructure.persistence.social_v2 import (
    SocialCollectionTargetStore,
    SocialCommentStore,
    SocialContentStore,
    SocialMediaStore,
    SocialMetricStore,
)
from app.infrastructure.persistence.social_v2.collection_targets import (
    CollectionTargetRow,
)
from app.infrastructure.providers.meta.audience import MetaAudienceReader
from app.infrastructure.providers.meta.facebook.comments import FacebookCommentsReader
from app.infrastructure.providers.meta.facebook.content import FacebookContentReader
from app.infrastructure.providers.meta.facebook.daily_metrics import (
    FacebookDailyMetricsReader,
)
from app.infrastructure.providers.meta.facebook.profile import FacebookProfileReader
from app.infrastructure.providers.meta.instagram.comments import InstagramCommentsReader
from app.infrastructure.providers.meta.instagram.content import InstagramContentReader
from app.infrastructure.providers.meta.instagram.daily_metrics import (
    InstagramDailyMetricsReader,
)
from app.infrastructure.providers.meta.instagram.profile import InstagramProfileReader
from app.infrastructure.providers.meta.page_token import resolve_page_access_token
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard
from app.infrastructure.providers.meta.transport import MetaTransport
from app.infrastructure.providers.tiktok.accounts import (
    TikTokAccountsWireMapper,
    TikTokAudienceReader,
    TikTokCommentsReader,
    TikTokContentReader,
    TikTokDailyMetricsReader,
    TikTokHttpTransport,
    TikTokProfileReader,
    parse_token,
    parse_token_info,
)

logger = logging.getLogger(__name__)

MAX_MEDIA_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class WorkerAccountResult:
    platform: str
    brand_id: int
    asset_id: int
    status: str
    metric_count: int = 0
    content_count: int = 0
    comment_count: int = 0
    media_count: int = 0
    error_code: str | None = None
    backfill_complete: bool = True


@dataclass(frozen=True)
class TikTokAccessContext:
    access_token: str
    scopes: frozenset[str]


# V2 writes `complete`; the V1 import wrote `completed`. Comparing against one
# spelling meant every imported account looked mid-backfill forever, so each run
# re-read a thirty-day window for it instead of yesterday. That is what made a
# pass outlast its own service timeout, and because the account was then never
# marked finished, the state could never correct itself.
BACKFILL_COMPLETE_STATUSES = frozenset({"complete", "completed"})


def _backfill_complete(status: str) -> bool:
    return status.strip().lower() in BACKFILL_COMPLETE_STATUSES


# The collection service is given 1500s before systemd terminates it. Stopping
# at 1200s leaves the account in flight room to finish and be committed, so a
# long pass ends with a complete record rather than a half-written one.
DEFAULT_RUN_BUDGET_SECONDS = 1200
# One account must not be able to consume the whole window. Provider calls have
# their own timeouts, but a request that trickles rather than stalls outlives
# them, and a single account then held the run until systemd killed it -- taking
# every account queued behind it with it.
#
# Five minutes, because the heaviest measured account legitimately needs 233s:
# it carries around sixty live Stories and the provider is asked about each one
# separately, at roughly two seconds a call. Four minutes left it finishing with
# seven seconds to spare, which is not a margin. Still a fraction of the run
# budget, so a genuinely stuck account cannot take the window with it.
DEFAULT_ACCOUNT_BUDGET_SECONDS = 300
# The scheduled orchestrator snapshots every Instagram Story feed before any
# slow content/audience work. Discovery is one bounded feed read per account;
# enrichment is allowed a larger slice only for accounts that actually have a
# live Story. A permanently slow account therefore cannot hide every account
# queued behind it.
STORY_DISCOVERY_ACCOUNT_BUDGET_SECONDS = 30
STORY_ENRICHMENT_ACCOUNT_BUDGET_SECONDS = 180
STORY_ENRICHMENT_RUN_BUDGET_SECONDS = 600
STORY_DISCOVERY_PAGE_SIZE = 100
STORY_ENRICHMENT_PAGE_SIZE = 10
# How many of an account's most recent posts get their comments re-read
# each run. Older posts keep whatever was collected when they were new.
COMMENTED_CONTENT_PER_RUN = 25
# How far back a routine refresh walks. Once an account is backfilled its
# archive is already stored, and the provider is asked for per-item insights on
# every item a page yields, at roughly a second each. A page is a hundred posts,
# which is already more than any dashboard shows as recent, and three pages did
# not fit in an account's share of a run. Older posts keep the numbers they were
# collected with; engagement on them has long settled.
CONTENT_PAGES_PER_RUN = 1
FULL_CONTENT_PAGES = 100
# A backfill reads the archive in pages of a hundred. A refresh cannot: the
# provider is asked for insights on every item a page yields, and that call
# takes seconds, so a hundred of them outlast the account's whole turn. Twenty
# five is more recent posts than any dashboard shows at once.
REFRESH_PAGE_SIZE = 25
FULL_PAGE_SIZE = 100
# A newly linked Meta account must not attempt its whole archive in one turn.
# Each successful page advances a durable cursor; later timer turns continue
# until the provider reaches the end, then nightly collection is enabled.
META_BACKFILL_CONTENT_PAGES_PER_RUN = 1
META_BACKFILL_PAGE_SIZE = 25
# Media is valuable but must never consume the account's complete 300-second
# budget after metrics have already succeeded. If this slice is exhausted the
# page is replayed next turn and already-held files are reused.
MEDIA_PHASE_BUDGET_SECONDS = 30
MEDIA_FETCH_TIMEOUT_SECONDS = 10
# Preset dashboards end yesterday.  A first collection therefore needs the
# thirty completed reporting days plus today's live profile snapshot.  The old
# `today - 29` window omitted the oldest day of "Last 30 Days".
DAILY_METRIC_BACKFILL_DAYS = 30
DAILY_METRIC_CHECKPOINT_SUFFIX = "daily-metrics"
# Version TikTok's daily checkpoint when the persisted daily schema expands.
# Existing accounts then prove the complete reporting window once, instead of
# advancing an old watermark while the newly supported components stay empty.
TIKTOK_DAILY_METRIC_CHECKPOINT_SUFFIX = "daily-metrics-v2"


def _meta_daily_metric_ids(platform: PlatformId) -> tuple[MetricId, ...]:
    source_metrics = (
        FACEBOOK_DAILY_SOURCE_METRICS
        if platform is PlatformId.FACEBOOK
        else INSTAGRAM_DAILY_SOURCE_METRICS
    )
    return tuple(
        dict.fromkeys(
            (
                *(metric_id for _source_field, metric_id in source_metrics),
                MetricId.FOLLOWS,
                MetricId.UNFOLLOWS,
            )
        )
    )


def _daily_metric_window_start(
    *,
    today: date,
    checkpoint: ProviderCheckpoint | None,
    inferred_observed_on: date | None = None,
) -> date:
    """Return a bounded, overlap-safe start for a Meta daily metric read.

    Imported accounts and newly connected TikTok accounts can be marked
    backfill-complete before every late provider day has settled. With no V2
    daily watermark, treating them as routine refreshes reads only yesterday
    and permanently skips an interior gap. Absence of this namespaced
    checkpoint now means "prove the reporting window once", for old and newly
    linked accounts alike.

    Once a watermark exists, overlap its observed day.  That lets a metric
    Meta had not finalized on the previous pass settle without turning every
    routine refresh back into a thirty-day request.
    """
    lower_bound = today - timedelta(days=DAILY_METRIC_BACKFILL_DAYS)
    observed_on = (
        checkpoint.observed_through.astimezone(UTC).date()
        if checkpoint is not None and checkpoint.observed_through is not None
        else inferred_observed_on
    )
    if observed_on is None:
        return lower_bound
    return max(lower_bound, min(today - timedelta(days=1), observed_on))


@contextmanager
def _phase(timings: dict[str, float], name: str) -> Iterator[None]:
    """Time one collection phase.

    An account that used its whole budget said only that it was slow. Knowing
    which phase spent the time turned three rounds of guessing into one look.
    """
    started = time.monotonic()
    try:
        yield
    finally:
        timings[name] = timings.get(name, 0.0) + time.monotonic() - started


def _lazy_phase_budget(
    seconds: float,
    *,
    clock=time.monotonic,
):
    """Start a soft phase budget when the phase first does actual work.

    Content and Story readers resolve provider insights before returning the
    first item to the media sink. Starting the media deadline before that read
    meant the deadline had already expired by the first thumbnail, so no media
    fetch was even attempted on slower accounts.
    """
    started_at: float | None = None

    def available() -> bool:
        nonlocal started_at
        now = clock()
        if started_at is None:
            started_at = now
        return now - started_at < seconds

    return available


class _StorySnapshotContentStore:
    """Persist expiring Story identity without erasing held insight values."""

    def __init__(self, store: SocialContentStore) -> None:
        self._store = store

    def upsert(self, record: ContentRecord) -> None:
        self._store.upsert(record, preserve_insights=True)

    def list_for_account(self, account_id: int) -> tuple[ContentRecord, ...]:
        return self._store.list_for_account(account_id)


class AccountBudgetExceeded(BaseException):
    """Raised in the collector's own thread when an account outstays its budget.

    Deliberately not an `Exception`: the collection phases catch broadly so one
    provider fault cannot lose the rest of an account's data, and any of those
    handlers would otherwise swallow the interrupt and let the stall continue.
    Like `KeyboardInterrupt`, this is an instruction to stop, not a fault to be
    recovered from.
    """


def _raise_account_budget(signum: int, frame: object) -> None:
    raise AccountBudgetExceeded("account_budget_exceeded")


class StandaloneCollector:
    def __init__(
        self,
        settings: AppSettings,
        engine: Engine,
        *,
        run_budget_seconds: int | None = DEFAULT_RUN_BUDGET_SECONDS,
        account_budget_seconds: int | None = DEFAULT_ACCOUNT_BUDGET_SECONDS,
    ) -> None:
        self.settings = settings
        self.engine = engine
        self._run_budget_seconds = run_budget_seconds
        self._account_budget_seconds = account_budget_seconds
        self.story_hot_lane_complete = True
        self.story_hot_lane_failures = 0
        self.policy = WritePolicy.from_settings(settings)
        self.policy.assert_allows_mutation("standalone_collection")
        try:
            vault = AesGcmTokenVault.from_json(
                active_key_id=settings.meta_activation.credential_active_key_id,
                keyring_json=settings.meta_activation.credential_keyring_json,
            )
        except Exception as exc:
            raise ConfigurationError("Worker credential keyring is invalid") from exc
        catalog = bootstrap_metric_catalog()
        self.credentials = ProjectionCredentialStore(engine, self.policy, vault)
        self.targets = SocialCollectionTargetStore(engine, self.policy)
        self.metrics = SocialMetricStore(engine, self.policy, catalog)
        self.content = SocialContentStore(engine, self.policy)
        self.comments = SocialCommentStore(engine, self.policy)
        self.checkpoints = ProjectionCheckpointStore(engine, self.policy)
        self.media_store = SocialMediaStore(engine, self.policy)
        self.media_files = (
            AtomicMediaFiles(Path(settings.media_storage_root))
            if settings.media_storage_root
            else None
        )
        self.media_fetcher = _MediaFetcher() if self.media_files is not None else None

    def close(self) -> None:
        if self.media_fetcher is not None:
            self.media_fetcher.close()

    @contextmanager
    def _account_budget(self, seconds: int | None = None) -> Iterator[None]:
        """Interrupt one account that outstays its share of the run.

        SIGALRM is only usable from the main thread, which is where the worker
        runs; anywhere else the budget is skipped rather than pretended.
        """
        seconds = self._account_budget_seconds if seconds is None else seconds
        if not seconds or threading.current_thread() is not threading.main_thread():
            yield
            return
        previous = signal.signal(signal.SIGALRM, _raise_account_budget)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    def collect_connected(
        self,
        *,
        platforms: tuple[PlatformId, ...],
        brand_id: int | None,
        asset_id: int | None,
        only_new: bool = False,
        durable_round: bool = False,
    ) -> tuple[WorkerAccountResult, ...]:
        selected = tuple(
            platform
            for platform in platforms
            if (
                platform in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}
                and self.settings.meta.collection_enabled
            )
            or (platform is PlatformId.TIKTOK and self.settings.tiktok.collection_enabled)
        )
        if not selected:
            raise ConfigurationError("No requested V2 collector is enabled")
        rows = self.targets.list_connected(
            platforms=selected,
            brand_id=brand_id,
            asset_id=asset_id,
            only_new=only_new,
        )
        deadline = time.monotonic() + self._run_budget_seconds if self._run_budget_seconds else None
        if durable_round and PlatformId.INSTAGRAM in selected:
            self._collect_story_hot_lane(rows, deadline=deadline)
        scheduled_round = self.targets.scheduled_round(rows) if durable_round else None
        collection_rows = scheduled_round.targets if scheduled_round is not None else rows
        results: list[WorkerAccountResult] = []
        logger.info(
            "collection_started accounts=%s%s",
            len(collection_rows),
            (
                f" round={scheduled_round.round_id} "
                f"round_progress={scheduled_round.completed_count}/{scheduled_round.total_count}"
                if scheduled_round is not None
                else ""
            ),
        )
        for index, row in enumerate(collection_rows, start=1):
            if deadline is not None and time.monotonic() >= deadline:
                # Stop on our own terms. Being killed by the service timeout
                # aborts whichever account is mid-write, and because the next
                # run starts from the stalest account it resumes here anyway.
                logger.warning(
                    "collection_budget_exhausted collected=%s remaining=%s",
                    index - 1,
                    len(collection_rows) - index + 1,
                )
                break
            started = time.monotonic()
            timings: dict[str, float] = {}
            try:
                with self._account_budget():
                    result = self._collect(
                        row,
                        timings,
                        # The scheduled hot lane already captured and enriched
                        # Stories for every Instagram account before this slow
                        # phase. Manual/targeted runs retain the self-contained
                        # account behavior.
                        include_stories=not durable_round,
                    )
                self.targets.mark_success(
                    row,
                    datetime.now(UTC),
                    backfill_complete=result.backfill_complete,
                )
            except AccountBudgetExceeded as exc:
                error_code = _error_code(exc)
                # Record where the account was blocked. The interrupt lands on
                # whichever call is waiting, so the innermost frames name the
                # phase; without them a stall is only ever "took too long".
                logger.warning(
                    "collection_account_stalled link_id=%s at=%s",
                    row.link_id,
                    # Our own frames, not the socket layer's. The innermost
                    # frames are always an SSL read, which says the account was
                    # waiting on the provider but never which phase was asking.
                    " <- ".join(
                        f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno}:{frame.name}"
                        for frame in traceback.extract_tb(exc.__traceback__)
                        if "/app/" in frame.filename
                    )[-300:],
                )
                if "core_complete" in timings:
                    # Profile and daily metrics are durable. Preserve that
                    # progress and retry the unfinished backfill next turn
                    # rather than disabling an otherwise accessible account.
                    self.targets.mark_success(row, datetime.now(UTC), backfill_complete=False)
                    result = WorkerAccountResult(
                        platform=row.platform.value,
                        brand_id=row.brand_id,
                        asset_id=row.asset_id,
                        status="partial",
                        error_code=error_code,
                        backfill_complete=False,
                    )
                else:
                    self.targets.mark_failure(row, error_code)
                    result = WorkerAccountResult(
                        platform=row.platform.value,
                        brand_id=row.brand_id,
                        asset_id=row.asset_id,
                        status="failed",
                        error_code=error_code,
                        backfill_complete=False,
                    )
            except Exception as exc:
                error_code = _error_code(exc)
                self.targets.mark_failure(row, error_code)
                result = WorkerAccountResult(
                    platform=row.platform.value,
                    brand_id=row.brand_id,
                    asset_id=row.asset_id,
                    status="failed",
                    error_code=error_code,
                )
            logger.info(
                "collection_account_done index=%s/%s platform=%s brand_id=%s "
                "link_id=%s status=%s seconds=%.1f phases=%s",
                index,
                len(collection_rows),
                row.platform.value,
                row.brand_id,
                row.link_id,
                result.status,
                time.monotonic() - started,
                ",".join(
                    f"{name}={seconds:.0f}"
                    for name, seconds in sorted(timings.items(), key=lambda item: -item[1])
                    if seconds >= 1 and name != "provider_pressure_pct"
                )
                or "-",
            )
            results.append(result)
            if scheduled_round is not None:
                completed, total = self.targets.advance_scheduled_round(
                    round_id=scheduled_round.round_id,
                    link_id=row.link_id,
                )
                if completed == total:
                    logger.info(
                        "collection_round_complete round=%s accounts=%s",
                        scheduled_round.round_id,
                        total,
                    )
        return tuple(results)

    def _collect_story_hot_lane(
        self,
        rows: tuple[CollectionTargetRow, ...],
        *,
        deadline: float | None,
    ) -> None:
        """Capture every live Story feed, then enrich accounts with live rows.

        The first pass deliberately avoids per-item insights and media files.
        It makes the expiring provider records durable for all accounts in a
        few bounded requests. The second pass adds insights and owned media,
        oldest-enriched account first, within its own checkpointed time slice.
        """
        instagram_rows = tuple(
            row for row in rows if row.platform is PlatformId.INSTAGRAM
        )
        self.story_hot_lane_complete = True
        self.story_hot_lane_failures = 0
        if not instagram_rows:
            return
        logger.info("story_hot_lane_started accounts=%s", len(instagram_rows))
        active: list[CollectionTargetRow] = []
        captured = 0
        for index, row in enumerate(instagram_rows, start=1):
            discovery_budget = STORY_DISCOVERY_ACCOUNT_BUDGET_SECONDS
            if deadline is not None:
                remaining_seconds = int(deadline - time.monotonic())
                if remaining_seconds < 1:
                    remaining = len(instagram_rows) - index + 1
                    self.story_hot_lane_failures += remaining
                    logger.warning(
                        "story_discovery_budget_exhausted remaining=%s", remaining
                    )
                    break
                discovery_budget = min(discovery_budget, remaining_seconds)
            try:
                with self._account_budget(discovery_budget):
                    result = self._collect_instagram_stories(
                        row,
                        insights=False,
                        persist_media=False,
                        checkpoint_suffix="stories.discovery",
                        page_size=STORY_DISCOVERY_PAGE_SIZE,
                    )
            except AccountBudgetExceeded:
                result = WorkerAccountResult(
                    platform=row.platform.value,
                    brand_id=row.brand_id,
                    asset_id=row.asset_id,
                    status="failed",
                    error_code="story_discovery_budget_exceeded",
                )
            except Exception as exc:
                result = WorkerAccountResult(
                    platform=row.platform.value,
                    brand_id=row.brand_id,
                    asset_id=row.asset_id,
                    status="failed",
                    error_code=_error_code(exc),
                )
            if result.status != "success":
                self.story_hot_lane_failures += 1
                logger.warning(
                    "story_discovery_failed index=%s/%s link_id=%s reason=%s",
                    index,
                    len(instagram_rows),
                    row.link_id,
                    result.error_code or result.status,
                )
                continue
            captured += result.content_count
            if result.content_count:
                active.append(row)

        # The existing `.stories` checkpoint records completed enrichment and
        # survives deploys. Oldest first makes an unfinished enrichment round
        # resume on the next half-hour tick instead of restarting at one brand.
        oldest = datetime.min.replace(tzinfo=UTC)

        def last_enriched(target_row: CollectionTargetRow) -> datetime:
            checkpoint = self.checkpoints.get(
                CheckpointKey(
                    platform=PlatformId.INSTAGRAM,
                    capability=CapabilityId.CONTENT,
                    account_id=f"{target_row.external_id}.stories",
                )
            )
            return (
                checkpoint.observed_through
                if checkpoint and checkpoint.observed_through
                else oldest
            )

        active.sort(key=lambda row: (last_enriched(row), row.link_id))
        enrichment_deadline = time.monotonic() + STORY_ENRICHMENT_RUN_BUDGET_SECONDS
        if deadline is not None:
            enrichment_deadline = min(enrichment_deadline, deadline)
        enriched = 0
        for index, row in enumerate(active, start=1):
            if time.monotonic() >= enrichment_deadline:
                remaining = len(active) - index + 1
                self.story_hot_lane_failures += remaining
                logger.warning("story_enrichment_budget_exhausted remaining=%s", remaining)
                break
            try:
                with self._account_budget(STORY_ENRICHMENT_ACCOUNT_BUDGET_SECONDS):
                    result = self._collect_instagram_stories(
                        row,
                        insights=True,
                        persist_media=True,
                        checkpoint_suffix="stories",
                        page_size=STORY_ENRICHMENT_PAGE_SIZE,
                    )
            except AccountBudgetExceeded:
                result = WorkerAccountResult(
                    platform=row.platform.value,
                    brand_id=row.brand_id,
                    asset_id=row.asset_id,
                    status="failed",
                    error_code="story_enrichment_budget_exceeded",
                )
            except Exception as exc:
                result = WorkerAccountResult(
                    platform=row.platform.value,
                    brand_id=row.brand_id,
                    asset_id=row.asset_id,
                    status="failed",
                    error_code=_error_code(exc),
                )
            if result.status == "success":
                enriched += result.content_count
            else:
                self.story_hot_lane_failures += 1
                logger.warning(
                    "story_enrichment_failed link_id=%s reason=%s",
                    row.link_id,
                    result.error_code or result.status,
                )
        self.story_hot_lane_complete = self.story_hot_lane_failures == 0
        logger.info(
            "story_hot_lane_done accounts=%s active_accounts=%s captured=%s "
            "enriched=%s failures=%s",
            len(instagram_rows),
            len(active),
            captured,
            enriched,
            self.story_hot_lane_failures,
        )

    def _collect_instagram_stories(
        self,
        row: CollectionTargetRow,
        *,
        insights: bool,
        persist_media: bool,
        checkpoint_suffix: str,
        page_size: int,
    ) -> WorkerAccountResult:
        token = self._access_token(row.platform, row.credential_reference)
        account = ProviderAccount(
            platform=PlatformId.INSTAGRAM,
            account_id=row.external_id,
            credential=ProviderCredential(access_token=token),
        )
        transport = MetaTransport(
            credential=account.credential,
            rate_guard=MetaRateGuard(sleeper=time.sleep),
            base_url=self.settings.meta.graph_base_url,
            api_version=self.settings.meta.graph_version,
            timeout_seconds=self.settings.meta_activation.provider_timeout_seconds,
            egress_enabled=True,
        )
        target = CollectionTarget(
            account=account,
            local_account_id=row.asset_id,
            brand_id=row.brand_id,
        )
        media_available = _lazy_phase_budget(MEDIA_PHASE_BUDGET_SECONDS)

        def persist_story_media(item: ProviderRecord) -> int:
            try:
                return self._persist_media(target, item, can_fetch=media_available)
            except Exception:
                # The expiring Story record and its insights are more important
                # than a file copy. A CDN/file fault must not roll back the feed
                # checkpoint or make later Stories wait behind this one.
                return 0

        try:
            outcome = collect_content(
                target=target,
                reader=InstagramContentReader(
                    transport,
                    stories=True,
                    insights=insights,
                    page_size=page_size,
                ),
                content_store=(
                    self.content
                    if insights
                    else _StorySnapshotContentStore(self.content)
                ),
                checkpoint_store=self.checkpoints,
                record_sink=persist_story_media if persist_media else None,
                checkpoint_account_id=f"{account.account_id}.{checkpoint_suffix}",
                max_pages=20,
                refresh_only=True,
            )
            return WorkerAccountResult(
                platform=row.platform.value,
                brand_id=row.brand_id,
                asset_id=row.asset_id,
                status=(
                    "success" if outcome.status is CollectionStatus.SUCCESS else "partial"
                ),
                content_count=outcome.content_count,
                media_count=outcome.media_count,
                error_code=outcome.error_code,
            )
        finally:
            transport.close()

    def verify_pending_tiktok(self, connection_id: int) -> WorkerAccountResult:
        pending = self.targets.pending_tiktok(connection_id)
        if pending is None:
            raise ValueError("pending_tiktok_connection_not_found")
        context = self._tiktok_access_context(pending.credential_reference, pending.external_id)
        provider_account = ProviderAccount(
            platform=PlatformId.TIKTOK,
            account_id=pending.external_id,
            credential=ProviderCredential(access_token=context.access_token),
        )
        profile_reader, _, _, _, _ = self._tiktok_readers(provider_account, scopes=context.scopes)
        snapshot = profile_reader.fetch_profile(provider_account)
        asset_id = self.targets.create_tiktok_asset(pending, snapshot.display_name)
        row = CollectionTargetRow(
            link_id=pending.link_id,
            connection_id=pending.connection_id,
            asset_id=asset_id,
            brand_id=pending.brand_id,
            platform=PlatformId.TIKTOK,
            external_id=pending.external_id,
            display_name=snapshot.display_name,
            credential_reference=pending.credential_reference,
            backfill_status="pending",
        )
        result = self._collect_tiktok(
            row,
            provider_account=provider_account,
            granted_scopes=context.scopes,
        )
        completed_at = datetime.now(UTC)
        self.targets.complete_tiktok_canary(
            pending,
            asset_id=asset_id,
            synced_at=completed_at,
        )
        return result

    def _collect(
        self,
        row: CollectionTargetRow,
        timings: dict[str, float] | None = None,
        *,
        include_stories: bool = True,
    ) -> WorkerAccountResult:
        timings = {} if timings is None else timings
        if row.platform is PlatformId.TIKTOK:
            return self._collect_tiktok(row, timings)
        return self._collect_meta(row, timings, include_stories=include_stories)

    def _collect_meta(
        self,
        row: CollectionTargetRow,
        timings: dict[str, float],
        *,
        include_stories: bool = True,
    ) -> WorkerAccountResult:
        token = self._access_token(row.platform, row.credential_reference)
        if row.platform is PlatformId.FACEBOOK:
            # Published posts and Page insights are refused with the connected
            # user's token even though the Page profile answers, so a healthy
            # looking credential still collected nothing.
            lookup = MetaTransport(
                credential=ProviderCredential(access_token=token),
                rate_guard=MetaRateGuard(sleeper=time.sleep),
                base_url=self.settings.meta.graph_base_url,
                api_version=self.settings.meta.graph_version,
                timeout_seconds=self.settings.meta_activation.provider_timeout_seconds,
                egress_enabled=True,
            )
            try:
                token = resolve_page_access_token(
                    lookup, page_id=row.external_id, fallback_token=token
                )
            finally:
                lookup.close()
        account = ProviderAccount(
            platform=row.platform,
            account_id=row.external_id,
            credential=ProviderCredential(access_token=token),
        )
        rate_guard = MetaRateGuard(sleeper=time.sleep)
        transport = MetaTransport(
            credential=account.credential,
            rate_guard=rate_guard,
            base_url=self.settings.meta.graph_base_url,
            api_version=self.settings.meta.graph_version,
            timeout_seconds=self.settings.meta_activation.provider_timeout_seconds,
            egress_enabled=True,
        )
        target = CollectionTarget(
            account=account,
            local_account_id=row.asset_id,
            brand_id=row.brand_id,
        )
        try:
            partial_errors: set[str] = set()
            profile_reader: ProfileReader
            daily_reader: DailyMetricsReader
            content_reader: ContentReader
            comments_reader: CommentsReader
            refreshing = _backfill_complete(row.backfill_status)
            content_page_size = REFRESH_PAGE_SIZE if refreshing else META_BACKFILL_PAGE_SIZE
            if row.platform is PlatformId.FACEBOOK:
                profile_reader = FacebookProfileReader(transport)
                daily_reader = FacebookDailyMetricsReader(transport)
                content_reader = FacebookContentReader(
                    transport, insights=True, page_size=content_page_size
                )
                comments_reader = FacebookCommentsReader(transport)
            else:
                profile_reader = InstagramProfileReader(transport)
                daily_reader = InstagramDailyMetricsReader(transport)
                content_reader = InstagramContentReader(
                    transport, insights=True, page_size=content_page_size
                )
                comments_reader = InstagramCommentsReader(transport)
            audience_reader = MetaAudienceReader(transport, platform=row.platform)
            with _phase(timings, "profile"):
                profile = collect_profile(
                    target=target,
                    reader=profile_reader,
                    metric_store=self.metrics,
                )
            today = date.today()
            daily_checkpoint_key = CheckpointKey(
                platform=row.platform,
                capability=CapabilityId.PROFILE,
                account_id=(f"{account.account_id}.{DAILY_METRIC_CHECKPOINT_SUFFIX}"),
            )
            daily_checkpoint = self.checkpoints.get(daily_checkpoint_key)
            inferred_daily_observed_on = (
                self.metrics.earliest_daily_gap(
                    platform=row.platform,
                    account_id=row.asset_id,
                    metric_ids=_meta_daily_metric_ids(row.platform),
                    start_on=today - timedelta(days=DAILY_METRIC_BACKFILL_DAYS),
                    end_on=today - timedelta(days=1),
                )
                if daily_checkpoint is None
                else None
            )
            since = _daily_metric_window_start(
                today=today,
                checkpoint=daily_checkpoint,
                inferred_observed_on=inferred_daily_observed_on,
            )
            daily = None
            try:
                with _phase(timings, "daily"):
                    daily = collect_daily_metrics(
                        target=target,
                        reader=daily_reader,
                        metric_store=self.metrics,
                        since=since,
                        until=today,
                    )
                if daily.status is not CollectionStatus.SUCCESS:
                    partial_errors.add("daily_partial")
                next_daily_checkpoint = ProviderCheckpoint(
                    key=daily_checkpoint_key,
                    version=1 if daily_checkpoint is None else daily_checkpoint.version + 1,
                    cursor=None,
                    watermark=today.isoformat(),
                    observed_through=datetime.combine(
                        today,
                        datetime.min.time(),
                        tzinfo=UTC,
                    ),
                )
                # A concurrent fast-lane/general timer pass may win this optimistic
                # update. Daily writes are idempotent and the winner observed at
                # least the same range, so losing the checkpoint race is harmless.
                self.checkpoints.put(
                    next_daily_checkpoint,
                    expected_version=(
                        daily_checkpoint.version if daily_checkpoint is not None else None
                    ),
                )
            except Exception as exc:
                # One malformed insight must not abandon audience, content and
                # stories. Do not advance the checkpoint: the daily phase will
                # be retried on the next run while the other capabilities make
                # independent progress now.
                logger.warning(
                    "daily_metrics_read_failed platform=%s asset_id=%s reason=%s",
                    row.platform.value,
                    row.asset_id,
                    _error_code(exc),
                )
                partial_errors.add("daily_unavailable")
            # This marker is written only after the phase returned normally;
            # `_phase` timings alone are also recorded for interrupted phases.
            timings["core_complete"] = 0.0
            try:
                with _phase(timings, "audience"):
                    audience = collect_audience(
                        target=target,
                        reader=audience_reader,
                        metric_store=self.metrics,
                    )
                if audience.status is not CollectionStatus.SUCCESS:
                    partial_errors.add("audience_partial_or_unavailable")
            except Exception:
                audience = None
                partial_errors.add("audience_unavailable")
            comment_count = 0
            commented_items = 0
            content_media_available = _lazy_phase_budget(MEDIA_PHASE_BUDGET_SECONDS)

            def persist_related(item: ProviderRecord) -> int:
                nonlocal comment_count, commented_items
                # Content arrives newest first, so this reads the comments on
                # recent posts and leaves the archive alone. Unbounded, an
                # account with hundreds of posts spent its entire turn re-reading
                # every comment on every one of them, every half hour, and the
                # accounts queued behind it were never reached. TikTok has been
                # bounded this way from the start.
                if commented_items < COMMENTED_CONTENT_PER_RUN:
                    commented_items += 1
                    try:
                        comments = collect_comments(
                            target=target,
                            content_id=item.external_id,
                            reader=comments_reader,
                            comment_store=self.comments,
                            max_pages=20,
                        )
                        comment_count += comments.comment_count
                        if comments.status is not CollectionStatus.SUCCESS:
                            partial_errors.add("comments_partial")
                    except Exception:
                        partial_errors.add("comments_unavailable")
                try:
                    return self._persist_media(target, item, can_fetch=content_media_available)
                except MediaBudgetDeferred:
                    partial_errors.add("media_deferred")
                    raise
                except Exception:
                    partial_errors.add("media_unavailable")
                    return 0

            # Guarded like comments, media and stories already are. Left bare,
            # a provider refusal here discarded the profile, daily metrics and
            # audience this account had already collected, and reported the run
            # as a total failure.
            content_count = 0
            content_media_count = 0
            content_backfill_complete = refreshing
            try:
                with _phase(timings, "content"):
                    content = collect_content(
                        target=target,
                        reader=content_reader,
                        content_store=self.content,
                        checkpoint_store=self.checkpoints,
                        record_sink=persist_related,
                        max_pages=(
                            CONTENT_PAGES_PER_RUN
                            if refreshing
                            else META_BACKFILL_CONTENT_PAGES_PER_RUN
                        ),
                        refresh_only=refreshing,
                    )
                content_count = content.content_count
                content_media_count = content.media_count
                content_backfill_complete = refreshing or content.status is CollectionStatus.SUCCESS
                if content.status is not CollectionStatus.SUCCESS:
                    partial_errors.add("content_partial")
            except Exception as exc:
                logger.warning(
                    "content_read_failed platform=%s asset_id=%s reason=%s",
                    row.platform.value,
                    row.asset_id,
                    _error_code(exc),
                )
                partial_errors.add("content_unavailable")
            story_content_count = 0
            story_media_count = 0
            if row.platform is PlatformId.INSTAGRAM and include_stories:
                story_reader = InstagramContentReader(
                    transport,
                    stories=True,
                    insights=True,
                    page_size=REFRESH_PAGE_SIZE,
                )
                story_media_available = _lazy_phase_budget(MEDIA_PHASE_BUDGET_SECONDS)

                def persist_story_media(item: ProviderRecord) -> int:
                    try:
                        return self._persist_media(target, item, can_fetch=story_media_available)
                    except MediaBudgetDeferred:
                        partial_errors.add("story_media_deferred")
                        raise
                    except Exception:
                        partial_errors.add("story_media_unavailable")
                        return 0

                try:
                    with _phase(timings, "stories"):
                        stories = collect_content(
                            target=target,
                            reader=story_reader,
                            content_store=self.content,
                            checkpoint_store=self.checkpoints,
                            record_sink=persist_story_media,
                            checkpoint_account_id=f"{account.account_id}.stories",
                            max_pages=20,
                            # Stories are what the account has live now; the
                            # provider drops them within a day. Resuming from where
                            # a previous run stopped walks a feed that no longer
                            # exists and misses the ones posted this morning.
                            refresh_only=True,
                        )
                    story_content_count = stories.content_count
                    story_media_count = stories.media_count
                    if stories.status is not CollectionStatus.SUCCESS:
                        partial_errors.add("stories_partial")
                except Exception:
                    partial_errors.add("stories_unavailable")
            return WorkerAccountResult(
                platform=row.platform.value,
                brand_id=row.brand_id,
                asset_id=row.asset_id,
                status="partial" if partial_errors else "success",
                metric_count=(
                    profile.metric_count
                    + (daily.metric_count if daily is not None else 0)
                    + (audience.metric_count if audience is not None else 0)
                ),
                content_count=content_count + story_content_count,
                comment_count=comment_count,
                media_count=content_media_count + story_media_count,
                error_code=_partial_error_code(partial_errors),
                backfill_complete=content_backfill_complete,
            )
        finally:
            # What the provider says is left of our quota, which is otherwise
            # measured and then thrown away. Meta reports pressure per app, per
            # Page and per user, and the only place it is visible to us is the
            # response headers of the calls we just made.
            usage = rate_guard.snapshot()
            if usage.pressure_pct > 0:
                timings["provider_pressure_pct"] = usage.pressure_pct
                logger.info(
                    "meta_rate_pressure link_id=%s scope=%s pressure_pct=%.1f%s",
                    row.link_id,
                    usage.scope or "unknown",
                    usage.pressure_pct,
                    " degraded" if usage.degraded_until else "",
                )
            transport.close()

    def _collect_tiktok(
        self,
        row: CollectionTargetRow,
        timings: dict[str, float] | None = None,
        *,
        provider_account: ProviderAccount | None = None,
        granted_scopes: frozenset[str] | None = None,
    ) -> WorkerAccountResult:
        if provider_account is None:
            context = self._tiktok_access_context(row.credential_reference, row.external_id)
            provider_account = ProviderAccount(
                platform=PlatformId.TIKTOK,
                account_id=row.external_id,
                credential=ProviderCredential(access_token=context.access_token),
            )
            granted_scopes = context.scopes
        if granted_scopes is None:
            raise PermissionError("provider_scope_context_unavailable")
        profile_reader, daily_reader, content_reader, audience_reader, comments_reader = (
            self._tiktok_readers(provider_account, scopes=granted_scopes)
        )
        target = CollectionTarget(
            account=provider_account,
            local_account_id=row.asset_id,
            brand_id=row.brand_id,
        )
        profile = collect_profile(
            target=target,
            reader=profile_reader,
            metric_store=self.metrics,
        )
        today = date.today()
        until = today - timedelta(days=1)
        daily_checkpoint_key = CheckpointKey(
            platform=PlatformId.TIKTOK,
            capability=CapabilityId.PROFILE,
            account_id=(f"{provider_account.account_id}.{TIKTOK_DAILY_METRIC_CHECKPOINT_SUFFIX}"),
        )
        daily_checkpoint = self.checkpoints.get(daily_checkpoint_key)
        # A missing versioned checkpoint means either a newly linked account or
        # a newly supported daily component. Prove all thirty completed days;
        # looking only for gaps among metrics that already exist cannot detect
        # a component that has never been persisted at all.
        inferred_daily_observed_on = None
        since = _daily_metric_window_start(
            today=today,
            checkpoint=daily_checkpoint,
            inferred_observed_on=inferred_daily_observed_on,
        )
        daily = collect_daily_metrics(
            target=target,
            reader=daily_reader,
            metric_store=self.metrics,
            since=since,
            until=until,
        )
        next_daily_checkpoint = ProviderCheckpoint(
            key=daily_checkpoint_key,
            version=1 if daily_checkpoint is None else daily_checkpoint.version + 1,
            cursor=None,
            watermark=until.isoformat(),
            observed_through=datetime.combine(
                until,
                datetime.min.time(),
                tzinfo=UTC,
            ),
        )
        self.checkpoints.put(
            next_daily_checkpoint,
            expected_version=(daily_checkpoint.version if daily_checkpoint is not None else None),
        )
        partial_errors: set[str] = set()
        try:
            audience = collect_audience(
                target=target,
                reader=audience_reader,
                metric_store=self.metrics,
            )
            if audience.status is not CollectionStatus.SUCCESS:
                partial_errors.add("audience_partial_or_unavailable")
                logger.warning(
                    "tiktok_audience_incomplete asset_id=%s status=%s reason=%s",
                    row.asset_id,
                    audience.status.value,
                    audience.error_code or "unreported",
                )
        except Exception as exc:
            audience = None
            partial_errors.add("audience_unavailable")
            # Swallowed silently, an account with no demographics looked the
            # same as one the provider withholds them for.
            logger.warning(
                "tiktok_audience_failed asset_id=%s reason=%s",
                row.asset_id,
                _error_code(exc),
            )
        totals: dict[MetricId, int] = {}
        comment_count = 0
        commented_videos = 0

        def persist_related(item: ProviderRecord) -> int:
            nonlocal comment_count, commented_videos
            raw_metrics = item.fields.get("metric_values")
            if isinstance(raw_metrics, dict):
                for metric_id, value in raw_metrics.items():
                    if isinstance(metric_id, MetricId) and isinstance(value, int):
                        totals[metric_id] = totals.get(metric_id, 0) + value
            if comments_reader is not None and commented_videos < 10:
                commented_videos += 1
                try:
                    comments = collect_comments(
                        target=target,
                        content_id=item.external_id,
                        reader=comments_reader,
                        comment_store=self.comments,
                        max_pages=5,
                    )
                    comment_count += comments.comment_count
                    if comments.status is not CollectionStatus.SUCCESS:
                        partial_errors.add("comments_partial")
                except Exception:
                    partial_errors.add("comments_unavailable")
            try:
                return self._persist_media(target, item)
            except Exception:
                partial_errors.add("media_unavailable")
                return 0

        content = collect_content(
            target=target,
            reader=content_reader,
            content_store=self.content,
            checkpoint_store=self.checkpoints,
            record_sink=persist_related,
            max_pages=(
                CONTENT_PAGES_PER_RUN
                if _backfill_complete(row.backfill_status)
                else FULL_CONTENT_PAGES
            ),
            refresh_only=_backfill_complete(row.backfill_status),
        )
        for metric_id, value in totals.items():
            from app.application.ports.persistence import MetricPoint

            self.metrics.upsert(
                MetricPoint(
                    platform=PlatformId.TIKTOK,
                    account_id=row.asset_id,
                    brand_id=row.brand_id,
                    # The same last complete day the daily metrics use. Dated
                    # today, these totals fell a day outside every reporting
                    # range -- which ends yesterday -- so the video cards were
                    # permanently blank while the rows sat in the table.
                    observed_on=until,
                    metric_id=metric_id,
                    value=value,
                )
            )
        return WorkerAccountResult(
            platform=row.platform.value,
            brand_id=row.brand_id,
            asset_id=row.asset_id,
            status="partial" if partial_errors else "success",
            metric_count=(
                profile.metric_count
                + daily.metric_count
                + len(totals)
                + (audience.metric_count if audience is not None else 0)
            ),
            content_count=content.content_count,
            comment_count=comment_count,
            media_count=content.media_count,
            error_code=_partial_error_code(partial_errors),
        )

    def _tiktok_readers(
        self,
        account: ProviderAccount,
        *,
        scopes: frozenset[str],
    ):
        config = self.settings.tiktok
        comment_enabled = "comment.list" in scopes
        get_urls = [config.profile_url, config.video_list_url]
        if comment_enabled:
            get_urls.append(config.comment_list_url)
        transport = TikTokHttpTransport(
            post_urls=(config.refresh_url,),
            get_urls=tuple(get_urls),
            timeout_seconds=self.settings.tiktok_activation.provider_timeout_seconds,
            max_retries=3,
            request_budget=500,
        )
        wire = TikTokAccountsWireMapper(config)
        headers = {"Access-Token": account.credential.access_token}
        profile = TikTokProfileReader(
            lambda business_id: transport.get(
                config.profile_url,
                headers=headers,
                params=wire.profile_fields(business_id=business_id),
            )
        )
        daily = TikTokDailyMetricsReader(
            lambda business_id, since, until: transport.get(
                config.profile_url,
                headers=headers,
                params=wire.daily_metric_fields(
                    business_id=business_id,
                    since=since,
                    until=until,
                ),
            )
        )
        content = TikTokContentReader(
            lambda business_id, cursor: transport.get(
                config.video_list_url,
                headers=headers,
                params=wire.video_fields(business_id=business_id, cursor=cursor),
            )
        )
        observed_on = date.today() - timedelta(days=1)
        audience = TikTokAudienceReader(
            lambda business_id, day: transport.get(
                config.profile_url,
                headers=headers,
                params=wire.audience_fields(
                    business_id=business_id,
                    observed_on=day,
                ),
            ),
            observed_on=observed_on,
        )
        comments = (
            TikTokCommentsReader(
                lambda business_id, video_id, cursor: transport.get(
                    config.comment_list_url,
                    headers=headers,
                    params=wire.comment_fields(
                        business_id=business_id,
                        video_id=video_id,
                        cursor=cursor,
                    ),
                )
            )
            if comment_enabled
            else None
        )
        return profile, daily, content, audience, comments

    def _access_token(self, platform: PlatformId, reference: str) -> str:
        token = self.credentials.get(
            CredentialRef(
                platform=platform,
                connection_id=reference,
                token_kind=TokenKind.ACCESS,
            )
        )
        if token is None:
            raise PermissionError("provider_access_token_unavailable")
        return token.value

    def _tiktok_access_context(self, reference: str, business_id: str) -> TikTokAccessContext:
        access_reference = CredentialRef(
            platform=PlatformId.TIKTOK,
            connection_id=reference,
            token_kind=TokenKind.ACCESS,
        )
        current = self.credentials.get(access_reference)
        grant = None
        refresh: SecretToken | None = None
        if current is not None and (
            current.expires_at is None
            or current.expires_at > datetime.now(UTC) + timedelta(minutes=5)
        ):
            access_token = current.value
        else:
            refresh_reference = CredentialRef(
                platform=PlatformId.TIKTOK,
                connection_id=reference,
                token_kind=TokenKind.REFRESH,
            )
            refresh = self.credentials.get(refresh_reference)
            if refresh is None:
                raise PermissionError("provider_refresh_token_unavailable")
            access_token = ""
        config = self.settings.tiktok
        transport = TikTokHttpTransport(
            post_urls=(config.refresh_url, config.token_info_url),
            get_urls=(),
            timeout_seconds=self.settings.tiktok_activation.provider_timeout_seconds,
        )
        wire = TikTokAccountsWireMapper(config)
        if not access_token:
            if refresh is None:
                raise PermissionError("provider_refresh_token_unavailable")
            grant = parse_token(
                transport.post(
                    config.refresh_url,
                    data=wire.refresh_fields(refresh_token=refresh.value),
                )
            )
            access_token = grant.access_token
        allowed = set(config.required_scopes) | set(config.optional_scopes)
        info = parse_token_info(
            transport.post(
                config.token_info_url,
                data=wire.token_info_fields(access_token=access_token),
            )
        )
        if (
            info.business_id != business_id
            or not set(config.required_scopes).issubset(info.scopes)
            or not set(info.scopes).issubset(allowed)
            or (grant is not None and set(info.scopes) != set(grant.scopes))
        ):
            raise PermissionError("provider_refresh_identity_rejected")
        if grant is not None:
            now = datetime.now(UTC)
            self.credentials.put_many(
                (
                    (
                        access_reference,
                        SecretToken(
                            value=grant.access_token,
                            expires_at=now + timedelta(seconds=grant.expires_in),
                        ),
                    ),
                    (
                        refresh_reference,
                        SecretToken(
                            value=grant.refresh_token,
                            expires_at=now + timedelta(seconds=grant.refresh_expires_in),
                        ),
                    ),
                )
            )
        return TikTokAccessContext(
            access_token=access_token,
            scopes=frozenset(info.scopes),
        )

    def _persist_media(
        self,
        target: CollectionTarget,
        item: ProviderRecord,
        *,
        can_fetch=lambda: True,
    ) -> int:
        if self.media_files is None or self.media_fetcher is None:
            return 0
        return ContentMediaWriter(
            target=target,
            files=self.media_files,
            media_store=self.media_store,
            fetch=self.media_fetcher.fetch,
            can_fetch=can_fetch,
        ).persist(item)


class _MediaFetcher:
    def fetch(self, url: str) -> FetchedMedia:
        _validate_media_url(url)
        with httpx.stream(
            "GET",
            url,
            timeout=httpx.Timeout(MEDIA_FETCH_TIMEOUT_SECONDS),
            follow_redirects=True,
            headers={"User-Agent": "social-media-v2-media/1"},
        ) as response:
            response.raise_for_status()
            _validate_media_url(str(response.url))
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type not in {"image/jpeg", "image/png", "image/webp", "video/mp4"}:
                raise ValueError("media_type_rejected")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_MEDIA_BYTES:
                    raise ValueError("media_too_large")
                chunks.append(chunk)
            return FetchedMedia(
                data=b"".join(chunks),
                mime_type=content_type,
                status_code=response.status_code,
            )

    def close(self) -> None:
        return None


def _validate_media_url(value: str) -> None:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname
        or hostname in {"localhost", "metadata.google.internal"}
    ):
        raise ValueError("media_url_rejected")
    if re.fullmatch(r"(?:127|10|0)\..*", hostname) or hostname in {"::1", "169.254.169.254"}:
        raise ValueError("media_url_rejected")


def collection_exit_code(
    results: Sequence[WorkerAccountResult], *, critical_failure: bool = False
) -> int:
    """Whether the run itself failed, not whether every account was perfect.

    Exiting non-zero on any imperfect account marked every run failed, because
    a partial account is ordinary: a provider withholds one metric and the rest
    is collected. systemd then showed `failed` on a healthy system, which is
    the state a real failure would have to stand out from.

    A run that reached nothing is worth waking someone for; one that collected
    what it could is not.
    """
    if critical_failure:
        return 1
    if not results:
        return 0
    return 0 if any(item.status != "failed" for item in results) else 1


def _error_code(exc: BaseException) -> str:
    """Record the class and the provider's sanitized reason.

    The class name alone said only `metatransporterror`, which is true of a
    refused metric, an expired token and a rate limit alike. The reason is an
    enum-like string from our own provider layer and carries no credential or
    response body, so keeping it turns an opaque failure into an actionable one.
    """
    name = re.sub(r"[^a-z0-9_]+", "_", type(exc).__name__.lower()).strip("_")
    reason = re.sub(r"[^a-z0-9_:.-]+", "_", str(exc).strip().lower()).strip("_")
    code = f"{name}:{reason}" if reason and reason != name else name
    return code[:120] or "collection_failed"


def _partial_error_code(errors: set[str]) -> str | None:
    if not errors:
        return None
    return ",".join(sorted(errors))[:256]


def _lock(engine: Engine, name: str):
    connection = engine.connect()
    acquired = bool(
        connection.execute(
            text("SELECT pg_try_advisory_lock(hashtext(:name))"), {"name": name}
        ).scalar_one()
    )
    if not acquired:
        connection.close()
        return None
    return connection


def _platforms(value: str) -> tuple[PlatformId, ...]:
    if value == "all":
        return tuple(PlatformId)
    return (PlatformId(value),)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Social Media V2 standalone collector")
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument(
        "--platform", choices=("all", *PlatformId.exact_set()), default="all"
    )
    collect_parser.add_argument("--brand-id", type=int)
    collect_parser.add_argument("--asset-id", type=int)
    run_mode = collect_parser.add_mutually_exclusive_group()
    run_mode.add_argument("--scheduled", action="store_true")
    run_mode.add_argument(
        "--complete",
        action="store_true",
        help="Process every selected account without the scheduled-run time budget.",
    )
    collect_parser.add_argument(
        "--only-new",
        action="store_true",
        help="Collect only accounts that have never been collected.",
    )
    collect_parser.set_defaults(explain=False)
    canary_parser = subparsers.add_parser("verify-tiktok")
    canary_parser.add_argument(
        "--explain",
        action="store_true",
        help="Print the provider's own message for a refusal, to this terminal only.",
    )
    canary_parser.add_argument("--connection-id", type=int, required=True)
    args = parser.parse_args(argv)

    settings = load_settings()
    # Nothing had ever configured the root logger, so the level the deployment
    # asks for was ignored and every INFO record was dropped. Only warnings
    # reached the journal, which is why a run that collected nothing looked the
    # same as one that collected everything.
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(message)s",
        force=True,
    )
    if args.command == "collect" and args.scheduled and not settings.worker_schedule_enabled:
        raise ConfigurationError("Scheduled collection is disabled")
    if not settings.db.url:
        raise ConfigurationError("Worker requires SOCIAL_DB_URL")
    engine = create_engine(settings.db.url, pool_pre_ping=True, pool_size=2, max_overflow=0)
    lock_name = (
        f"social_media_v2:tiktok_canary:{args.connection_id}"
        if args.command == "verify-tiktok"
        # Its own lock: the fast lane after a connection must not wait behind a
        # full pass, and a full pass must not wait behind it.
        else "social_media_v2:new_account_collection"
        if getattr(args, "only_new", False)
        else "social_media_v2:scheduled_collection"
    )
    lock_connection = _lock(engine, lock_name)
    if lock_connection is None:
        # Another run holds the collection lock. Skipping is right — two
        # collectors must not write the same accounts — but exiting silently
        # made a skipped run indistinguishable from a completed one, so a
        # scheduled tick that did nothing looked like a healthy collection.
        logger.warning("collection_skipped_lock_held lock=%s", lock_name)
        engine.dispose()
        return 0
    collector: StandaloneCollector | None = None
    try:
        collector = StandaloneCollector(
            settings,
            engine,
            run_budget_seconds=(
                None if getattr(args, "complete", False) else DEFAULT_RUN_BUDGET_SECONDS
            ),
        )
        results: tuple[WorkerAccountResult, ...]
        if args.command == "verify-tiktok":
            try:
                results = (collector.verify_pending_tiktok(args.connection_id),)
            except Exception as exc:
                # A refused verification left the connection at
                # `pending_verification` with nothing written anywhere, so an
                # account that TikTok would not confirm looked the same as one
                # still waiting its turn. The reason is our own provider layer's
                # enum, which carries no credential or response body.
                logger.warning(
                    "tiktok_verification_failed connection_id=%s reason=%s",
                    args.connection_id,
                    _error_code(exc),
                )
                # Only when an operator asks, and only to their terminal. The
                # provider's text is the sole way to read an undocumented code,
                # and it can echo request content, so it never reaches a log.
                message = getattr(exc, "provider_message", "")
                if args.explain and message:
                    print(f"provider_message: {message}")
                raise
        else:
            durable_round = bool(
                args.scheduled
                and args.platform == "all"
                and args.brand_id is None
                and args.asset_id is None
                and not args.only_new
            )
            results = collector.collect_connected(
                platforms=_platforms(args.platform),
                brand_id=args.brand_id,
                asset_id=args.asset_id,
                only_new=args.only_new,
                durable_round=durable_round,
            )
        print(json.dumps([asdict(item) for item in results], separators=(",", ":")))
        return collection_exit_code(
            results,
            critical_failure=(
                bool(getattr(args, "scheduled", False))
                and not collector.story_hot_lane_complete
            ),
        )
    finally:
        if collector is not None:
            collector.close()
        lock_connection.execute(
            text("SELECT pg_advisory_unlock(hashtext(:name))"), {"name": lock_name}
        )
        lock_connection.close()
        engine.dispose()


__all__ = ["StandaloneCollector", "WorkerAccountResult", "main"]

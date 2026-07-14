from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.persistence import ContentRecord, MetricPoint
from app.application.ports.platforms import ProviderAccount, ProviderCredential, ProviderRecord
from app.application.ports.platforms.content import ContentPage
from app.application.services.collection import (
    CollectionStatus,
    CollectionTarget,
    collect_content,
    collect_profile,
)
from app.application.services.collection.contracts import classify_failure
from app.domain.platforms import PlatformId
from app.domain.sync import (
    BackfillJobState,
    BackfillStage,
    JobStatus,
    SelectionSource,
    backfill_readiness,
    d1_coverage,
    defer_rate_limited_job,
    follower_series,
    initial_backfill_window,
    recover_stale_job,
    remaining_backfill_window,
    rolling_refresh_window,
    select_collection_accounts,
)
from app.infrastructure.persistence.media_files import AtomicMediaFiles
from app.infrastructure.providers.meta.facebook.profile import FacebookProfileReader
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard, MetaRateLimited
from app.infrastructure.providers.meta.transport import MetaTransport, MetaTransportError
from app.workers import WORKER_CONTRACTS

NOW = datetime(2026, 7, 14, 13, tzinfo=UTC)


class MemoryContentStore:
    def __init__(self) -> None:
        self.rows: dict[str, ContentRecord] = {}

    def upsert(self, record: ContentRecord) -> None:
        self.rows[record.external_content_id] = record

    def list_for_account(self, account_id: int) -> tuple[ContentRecord, ...]:
        return tuple(self.rows.values())


class MemoryMetricStore:
    def __init__(self) -> None:
        self.rows: list[MetricPoint] = []

    def upsert(self, point: MetricPoint) -> None:
        self.rows.append(point)

    def read(self, **kwargs: object) -> tuple[MetricPoint, ...]:
        return tuple(self.rows)


class MemoryCheckpointStore:
    def __init__(self) -> None:
        self.rows: dict[CheckpointKey, ProviderCheckpoint] = {}

    def get(self, key: CheckpointKey) -> ProviderCheckpoint | None:
        return self.rows.get(key)

    def put(
        self, checkpoint: ProviderCheckpoint, *, expected_version: int | None
    ) -> bool:
        current = self.rows.get(checkpoint.key)
        if (current.version if current else None) != expected_version:
            return False
        self.rows[checkpoint.key] = checkpoint
        return True

    def claim_once(
        self, key: CheckpointKey, operation_id: str, expires_at: datetime
    ) -> bool:
        return True


class FixedContentReader:
    def __init__(self, items: tuple[ProviderRecord, ...]) -> None:
        self.items = items
        self.cursors: list[str | None] = []

    def list_content(
        self, account: ProviderAccount, *, cursor: str | None = None
    ) -> ContentPage:
        self.cursors.append(cursor)
        return ContentPage(items=self.items, next_cursor=None, observed_at=NOW)


def _target() -> CollectionTarget:
    return CollectionTarget(
        account=ProviderAccount(
            platform=PlatformId.FACEBOOK,
            account_id="page-1",
            credential=ProviderCredential(access_token="fixture-access-value"),
        ),
        local_account_id=11,
        brand_id=7,
    )


def _content_item(external_id: str) -> ProviderRecord:
    return ProviderRecord(
        external_id=external_id,
        observed_at=NOW,
        fields={
            "content_type": "post",
            "permalink": "",
            "message": external_id,
            "media_url": "",
            "published_at": NOW,
            "likes_count": 1,
            "comments_count": 0,
            "shares_count": 0,
        },
    )


def test_crash_before_checkpoint_replays_page_without_duplicate_rows() -> None:
    target = _target()
    store = MemoryContentStore()
    checkpoints = MemoryCheckpointStore()
    reader = FixedContentReader((_content_item("post-1"), _content_item("post-2")))

    def crash_after_second(count: int) -> None:
        if count == 2:
            raise RuntimeError("simulated_worker_crash")

    with pytest.raises(RuntimeError, match="simulated_worker_crash"):
        collect_content(
            target=target,
            reader=reader,
            content_store=store,
            checkpoint_store=checkpoints,
            after_record=crash_after_second,
        )
    assert set(store.rows) == {"post-1", "post-2"}
    assert checkpoints.rows == {}

    outcome = collect_content(
        target=target,
        reader=reader,
        content_store=store,
        checkpoint_store=checkpoints,
    )
    assert outcome.status is CollectionStatus.SUCCESS
    assert set(store.rows) == {"post-1", "post-2"}
    assert reader.cursors == [None, None]
    assert next(iter(checkpoints.rows.values())).version == 1


def test_atomic_media_failure_leaves_no_destination_or_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = AtomicMediaFiles(tmp_path)

    def fail_replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        raise OSError("simulated_media_failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated_media_failure"):
        files.persist("facebook/11/post-1.jpg", b"fixture-media")
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


def test_dirty_backfill_windows_stale_recovery_and_rate_defer() -> None:
    today = date(2026, 7, 14)
    initial = initial_backfill_window(today)
    remaining = remaining_backfill_window(today)
    assert (initial.since, initial.until, initial.inclusive_days) == (
        date(2026, 6, 14),
        date(2026, 7, 13),
        30,
    )
    assert (remaining.since, remaining.until, remaining.inclusive_days) == (
        date(2026, 4, 15),
        date(2026, 6, 13),
        60,
    )
    running = BackfillJobState(
        status=JobStatus.RUNNING,
        scheduled_for=NOW - timedelta(hours=3),
        started_at=NOW - timedelta(hours=2),
        error_code=None,
    )
    recovered = recover_stale_job(
        running,
        now=NOW,
        stale_after=timedelta(hours=1),
    )
    assert recovered.status is JobStatus.PENDING
    assert recovered.started_at is None
    assert recovered.error_code == "worker_interrupted"
    deferred = defer_rate_limited_job(recovered, now=NOW)
    assert deferred.status is JobStatus.PENDING
    assert deferred.error_code == "rate_limited"
    assert deferred.scheduled_for == NOW + timedelta(minutes=20)
    assert backfill_readiness(completed_stages=(), current_stage=None) == "30d loading"
    assert (
        backfill_readiness(
            completed_stages=(BackfillStage.RECENT_30D,),
            current_stage=BackfillStage.REMAINING_90D,
        )
        == "90d loading"
    )
    assert (
        backfill_readiness(
            completed_stages=(
                BackfillStage.RECENT_30D,
                BackfillStage.REMAINING_90D,
            ),
            current_stage=None,
        )
        == "90d ready"
    )


def test_first_follower_snapshot_history_repair_and_rolling_window() -> None:
    since = date(2026, 7, 11)
    until = date(2026, 7, 14)
    first = follower_series(
        since=since,
        until=until,
        current_total=120,
        observed_values={},
        previous_total=None,
    )
    assert list(first.totals.values()) == [120, 120, 120, 120]
    assert list(first.changes.values()) == [0, 0, 0, 0]

    repaired = follower_series(
        since=since,
        until=until,
        current_total=120,
        observed_values={
            date(2026, 7, 11): 2,
            date(2026, 7, 12): 3,
            date(2026, 7, 13): 1,
            date(2026, 7, 14): 4,
        },
        previous_total=112,
    )
    assert list(repaired.totals.values()) == [112, 115, 116, 120]
    assert list(repaired.changes.values()) == [0, 3, 1, 4]
    assert rolling_refresh_window(date(2026, 7, 14), 14) == (
        date(2026, 6, 30),
        date(2026, 7, 13),
    )


def test_linked_account_transition_and_d1_coverage() -> None:
    fallback = select_collection_accounts(
        linked_account_ids=(),
        transition_account_ids=("page-1", "page-2"),
        transition_complete=False,
    )
    linked = select_collection_accounts(
        linked_account_ids=("page-3",),
        transition_account_ids=("page-1",),
        transition_complete=False,
    )
    complete_empty = select_collection_accounts(
        linked_account_ids=(),
        transition_account_ids=("page-1",),
        transition_complete=True,
    )
    assert fallback.source is SelectionSource.TRANSITION_FALLBACK
    assert linked.account_ids == ("page-3",)
    assert complete_empty.account_ids == ()
    assert d1_coverage(("page-1", "page-2"), ("page-1",)).missing_account_ids == (
        "page-2",
    )
    assert d1_coverage(("page-1",), ("page-1",)).exit_code == 0


def test_partial_profile_does_not_write_synthetic_zero() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id": "page-1", "name": "No Metric"},
            request=request,
        )

    target = _target()
    metric_store = MemoryMetricStore()
    transport = MetaTransport(
        credential=target.account.credential,
        rate_guard=MetaRateGuard(clock=lambda: NOW, sleeper=lambda _: None),
        wire=httpx.MockTransport(handler),
        egress_enabled=True,
    )
    outcome = collect_profile(
        target=target,
        reader=FacebookProfileReader(transport, clock=lambda: NOW),
        metric_store=metric_store,
    )
    assert outcome.status is CollectionStatus.PARTIAL
    assert outcome.error_code == "metric_unavailable"
    assert metric_store.rows == []


def test_timeout_malformed_page_story_expiry_and_status_classification() -> None:
    attempts = 0

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        raise httpx.ReadTimeout("fixture timeout", request=request)

    transport = MetaTransport(
        credential=ProviderCredential(access_token="fixture-access-value"),
        rate_guard=MetaRateGuard(clock=lambda: NOW, sleeper=lambda _: None),
        wire=httpx.MockTransport(timeout_handler),
        egress_enabled=True,
        max_retries=1,
        base_backoff_seconds=0,
        sleeper=lambda _: None,
    )
    with pytest.raises(MetaTransportError, match="meta_transport_failure"):
        transport.get("page-1")
    assert attempts == 2

    malformed = MetaTransport(
        credential=ProviderCredential(access_token="fixture-access-value"),
        rate_guard=MetaRateGuard(clock=lambda: NOW, sleeper=lambda _: None),
        wire=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": {}}, request=request)
        ),
        egress_enabled=True,
    )
    with pytest.raises(MetaTransportError, match="meta_page_data_invalid"):
        malformed.page("page-1/stories")

    expired = classify_failure(MetaTransportError("rejected", status_code=404))
    invalid = classify_failure(MetaTransportError("rejected", status_code=401))
    limited = classify_failure(
        MetaRateLimited(reason="cooldown_active", wait_seconds=10, pressure_pct=93)
    )
    assert expired.status is CollectionStatus.OBJECT_INACCESSIBLE
    assert invalid.status is CollectionStatus.TOKEN_INVALID
    assert limited.status is CollectionStatus.RATE_LIMITED
    assert limited.exit_code == 75


def test_worker_cli_lock_cadence_contracts_are_declared_but_not_scheduled() -> None:
    by_name = {contract.name: contract for contract in WORKER_CONTRACTS}
    assert by_name["facebook_followers_hourly"].cadence == "hourly-at-minute-10"
    assert by_name["instagram_followers_hourly"].cadence == "hourly-at-minute-05"
    assert by_name["instagram_stories"].cadence == "hourly-at-minute-15"
    assert by_name["social_backfill_jobs"].cadence == "minute-07-27-47"
    assert all(contract.lock_busy_exit_code == 0 for contract in WORKER_CONTRACTS)
    assert all("--brand-id" in contract.arguments for contract in WORKER_CONTRACTS)

"""One slow account must not consume the whole collection window.

A single account stalled inside a provider read and held the run until systemd
terminated it, taking every account queued behind it. Because targets came back
in a fixed order, the next run began at the same account and stalled again, so
the queue behind it was never reached at all.
"""

from __future__ import annotations

import time
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

import app.workers.collector as collector_module
from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.services.collection import CollectionOutcome, CollectionStatus
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.persistence.social_v2.collection_targets import (
    CollectionTargetRow,
    ScheduledCollectionRound,
)
from app.workers.collector import (
    DAILY_METRIC_BACKFILL_DAYS,
    DEFAULT_ACCOUNT_BUDGET_SECONDS,
    DEFAULT_RUN_BUDGET_SECONDS,
    MEDIA_FETCH_TIMEOUT_SECONDS,
    MEDIA_PHASE_BUDGET_SECONDS,
    META_BACKFILL_CONTENT_PAGES_PER_RUN,
    META_BACKFILL_PAGE_SIZE,
    AccountBudgetExceeded,
    StandaloneCollector,
    WorkerAccountResult,
    _daily_metric_window_start,
    _error_code,
    _lazy_phase_budget,
    _StorySnapshotContentStore,
)


def _daily_checkpoint(observed_on: date | None) -> ProviderCheckpoint:
    return ProviderCheckpoint(
        key=CheckpointKey(
            platform=PlatformId.INSTAGRAM,
            capability=CapabilityId.PROFILE,
            account_id="17841400000000.daily-metrics",
        ),
        version=1,
        cursor=None,
        watermark=observed_on.isoformat() if observed_on else None,
        observed_through=(
            datetime.combine(observed_on, datetime.min.time(), tzinfo=UTC) if observed_on else None
        ),
    )


def test_imported_account_without_daily_watermark_repairs_the_reporting_window() -> None:
    today = date(2026, 8, 25)

    assert _daily_metric_window_start(
        today=today,
        checkpoint=None,
    ) == today.replace(day=26, month=7)
    assert (
        today
        - _daily_metric_window_start(
            today=today,
            checkpoint=None,
        )
    ).days == DAILY_METRIC_BACKFILL_DAYS


def test_daily_watermark_closes_a_cutover_gap_then_returns_to_one_day_overlap() -> None:
    today = date(2026, 8, 25)

    assert _daily_metric_window_start(
        today=today,
        checkpoint=_daily_checkpoint(date(2026, 8, 18)),
    ) == date(2026, 8, 18)
    assert _daily_metric_window_start(
        today=today,
        checkpoint=_daily_checkpoint(today),
    ) == date(2026, 8, 24)


def test_imported_metric_gap_bounds_the_first_repair_without_hiding_the_gap() -> None:
    assert _daily_metric_window_start(
        today=date(2026, 8, 25),
        checkpoint=None,
        inferred_observed_on=date(2026, 8, 18),
    ) == date(2026, 8, 18)


def test_incomplete_daily_watermark_does_not_hide_history() -> None:
    today = date(2026, 8, 25)

    assert _daily_metric_window_start(
        today=today,
        checkpoint=_daily_checkpoint(None),
    ) == date(2026, 7, 26)


def test_the_account_budget_leaves_room_inside_the_run_budget() -> None:
    # Otherwise the first slow account would exhaust the run on its own. A
    # quarter of the run is already generous for one account.
    assert DEFAULT_ACCOUNT_BUDGET_SECONDS <= DEFAULT_RUN_BUDGET_SECONDS // 4


def test_the_account_budget_clears_the_heaviest_measured_account() -> None:
    # The busiest account measured needs 233s, nearly all of it reading the
    # insights of around sixty live Stories one at a time.
    assert DEFAULT_ACCOUNT_BUDGET_SECONDS >= 280


def test_meta_backfill_is_incremental_and_media_is_bounded() -> None:
    assert META_BACKFILL_CONTENT_PAGES_PER_RUN == 1
    assert META_BACKFILL_PAGE_SIZE <= 25
    assert MEDIA_FETCH_TIMEOUT_SECONDS <= MEDIA_PHASE_BUDGET_SECONDS
    assert MEDIA_PHASE_BUDGET_SECONDS < DEFAULT_ACCOUNT_BUDGET_SECONDS


def test_media_budget_starts_with_the_first_media_attempt() -> None:
    ticks = iter((100.0, 100.0, 131.0))
    available = _lazy_phase_budget(30, clock=lambda: next(ticks))

    # Time spent resolving content/Story insights occurs before this callback
    # and must not consume the media slice.
    assert available() is True
    assert available() is True
    assert available() is False


def test_the_run_budget_stops_before_the_service_timeout() -> None:
    # The unit allows 1500s; stopping at the budget lets the account in flight
    # finish and be committed instead of being killed mid-write.
    assert DEFAULT_RUN_BUDGET_SECONDS < 1500


def test_a_stalled_account_is_interrupted() -> None:
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = 1

    with pytest.raises(AccountBudgetExceeded):
        with collector._account_budget():
            time.sleep(5)


def test_the_alarm_is_cleared_after_a_healthy_account() -> None:
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = 1

    with collector._account_budget():
        pass
    # A leaked alarm would fire during whichever account came next and blame it
    # for the previous one's stall.
    time.sleep(2)


def test_the_budget_can_be_switched_off() -> None:
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = None

    with collector._account_budget():
        pass


def test_the_interruption_is_recorded_as_its_own_reason() -> None:
    code = _error_code(AccountBudgetExceeded("account_budget_exceeded"))
    assert code == "accountbudgetexceeded:account_budget_exceeded"


def test_the_interrupt_survives_the_phase_handlers() -> None:
    """The collection phases catch broadly so one provider fault does not lose
    the rest of an account. The budget interrupt must pass straight through
    them, or a stalled account keeps the run and is never recorded as stalled.
    """
    assert not issubclass(AccountBudgetExceeded, Exception)

    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = 1

    with pytest.raises(AccountBudgetExceeded):
        with collector._account_budget():
            try:
                time.sleep(5)
            except Exception:  # noqa: BLE001 - mirrors the phase handlers
                pytest.fail("a phase handler swallowed the budget interrupt")


def test_meta_daily_failure_does_not_abandon_later_capabilities(monkeypatch) -> None:
    class FakeTransport:
        def __init__(self, **_kwargs: object) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    class FakeMetrics:
        def earliest_daily_gap(self, **_kwargs: object) -> None:
            return None

    class FakeCheckpoints:
        put_called = False

        def get(self, _key: CheckpointKey) -> None:
            return None

        def put(self, *_args: object, **_kwargs: object) -> bool:
            self.put_called = True
            return True

    content_calls: list[str] = []
    fake_transport = FakeTransport()
    monkeypatch.setattr(
        collector_module,
        "MetaTransport",
        lambda **_kwargs: fake_transport,
    )
    for name in (
        "InstagramProfileReader",
        "InstagramDailyMetricsReader",
        "InstagramCommentsReader",
        "MetaAudienceReader",
    ):
        monkeypatch.setattr(collector_module, name, lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        collector_module,
        "InstagramContentReader",
        lambda *_args, **kwargs: SimpleNamespace(stories=kwargs.get("stories", False)),
    )
    monkeypatch.setattr(
        collector_module,
        "collect_profile",
        lambda **_kwargs: CollectionOutcome(
            status=CollectionStatus.SUCCESS,
            metric_count=1,
        ),
    )

    def fail_daily(**_kwargs: object) -> CollectionOutcome:
        raise ValueError("provider_daily_metric_shape_invalid")

    monkeypatch.setattr(collector_module, "collect_daily_metrics", fail_daily)
    monkeypatch.setattr(
        collector_module,
        "collect_audience",
        lambda **_kwargs: CollectionOutcome(
            status=CollectionStatus.SUCCESS,
            metric_count=2,
        ),
    )

    def collect_content(**kwargs: object) -> CollectionOutcome:
        reader = kwargs["reader"]
        content_calls.append("stories" if reader.stories else "content")
        return CollectionOutcome(status=CollectionStatus.SUCCESS)

    monkeypatch.setattr(collector_module, "collect_content", collect_content)

    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector.settings = SimpleNamespace(
        meta=SimpleNamespace(
            graph_base_url="https://graph.facebook.com",
            graph_version="v26.0",
        ),
        meta_activation=SimpleNamespace(provider_timeout_seconds=1),
    )
    collector.metrics = FakeMetrics()
    collector.checkpoints = FakeCheckpoints()
    collector.content = object()
    collector.comments = object()
    collector._access_token = lambda _platform, _reference: "fixture-token"

    result = collector._collect_meta(
        CollectionTargetRow(
            link_id=114,
            connection_id=84,
            asset_id=910008,
            brand_id=286298,
            platform=PlatformId.INSTAGRAM,
            external_id="17841406168669898",
            display_name="ersan_et",
            credential_reference="84",
            backfill_status="pending",
        ),
        {},
    )

    assert result.status == "partial"
    assert result.error_code == "daily_unavailable"
    assert result.metric_count == 3
    assert content_calls == ["content", "stories"]
    assert collector.checkpoints.put_called is False
    assert fake_transport.closed is True


def test_scheduled_orchestrator_runs_story_lane_before_durable_round(monkeypatch) -> None:
    instagram = CollectionTargetRow(
        link_id=11,
        connection_id=21,
        asset_id=31,
        brand_id=41,
        platform=PlatformId.INSTAGRAM,
        external_id="ig-1",
        display_name="IG One",
        credential_reference="vault:ig",
        backfill_status="complete",
    )
    facebook = CollectionTargetRow(
        link_id=12,
        connection_id=22,
        asset_id=32,
        brand_id=42,
        platform=PlatformId.FACEBOOK,
        external_id="page-1",
        display_name="Page One",
        credential_reference="vault:fb",
        backfill_status="complete",
    )
    events: list[str] = []

    class FakeTargets:
        def list_connected(self, **_kwargs: object):
            return (instagram, facebook)

        def scheduled_round(self, rows):
            events.append("round")
            return ScheduledCollectionRound(3, rows, 0, 2)

        def mark_success(self, row, *_args, **_kwargs):
            events.append(f"success:{row.link_id}")

        def advance_scheduled_round(self, *, round_id: int, link_id: int):
            events.append(f"advance:{round_id}:{link_id}")
            return (1 if link_id == 11 else 2, 2)

    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector.settings = SimpleNamespace(
        meta=SimpleNamespace(collection_enabled=True),
        tiktok=SimpleNamespace(collection_enabled=False),
    )
    collector.targets = FakeTargets()
    collector._run_budget_seconds = None
    collector._account_budget_seconds = None
    collector._collect_story_hot_lane = lambda _rows, deadline: events.append("stories")

    def collect(row, _timings, *, include_stories: bool):
        events.append(f"collect:{row.link_id}:stories={include_stories}")
        return WorkerAccountResult(
            platform=row.platform.value,
            brand_id=row.brand_id,
            asset_id=row.asset_id,
            status="success",
        )

    collector._collect = collect

    collector.collect_connected(
        platforms=(PlatformId.FACEBOOK, PlatformId.INSTAGRAM),
        brand_id=None,
        asset_id=None,
        durable_round=True,
    )

    assert events[:2] == ["stories", "round"]
    assert "collect:11:stories=False" in events
    assert "collect:12:stories=False" in events
    assert events[-1] == "advance:3:12"


def test_story_discovery_covers_all_accounts_before_any_enrichment(monkeypatch) -> None:
    rows = tuple(
        CollectionTargetRow(
            link_id=link_id,
            connection_id=link_id + 10,
            asset_id=link_id + 20,
            brand_id=link_id + 30,
            platform=PlatformId.INSTAGRAM,
            external_id=f"ig-{link_id}",
            display_name=f"IG {link_id}",
            credential_reference=f"vault:{link_id}",
            backfill_status="complete",
        )
        for link_id in (1, 2, 3)
    )
    calls: list[tuple[int, bool]] = []

    class FakeCheckpoints:
        def get(self, _key):
            return None

    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = None
    collector.checkpoints = FakeCheckpoints()

    def collect_story(row, *, insights, **_kwargs):
        calls.append((row.link_id, insights))
        return WorkerAccountResult(
            platform="instagram",
            brand_id=row.brand_id,
            asset_id=row.asset_id,
            status="success",
            content_count=1 if row.link_id != 2 else 0,
        )

    collector._collect_instagram_stories = collect_story
    collector._collect_story_hot_lane(rows, deadline=None)

    assert calls == [
        (1, False),
        (2, False),
        (3, False),
        (1, True),
        (3, True),
    ]
    assert collector.story_hot_lane_complete is True


def test_story_discovery_respects_the_total_scheduled_run_deadline(monkeypatch) -> None:
    rows = tuple(
        CollectionTargetRow(
            link_id=link_id,
            connection_id=link_id + 10,
            asset_id=link_id + 20,
            brand_id=link_id + 30,
            platform=PlatformId.INSTAGRAM,
            external_id=f"ig-{link_id}",
            display_name=f"IG {link_id}",
            credential_reference=f"vault:{link_id}",
            backfill_status="complete",
        )
        for link_id in (1, 2)
    )
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = None
    collector._collect_instagram_stories = lambda *_args, **_kwargs: pytest.fail(
        "expired discovery lane must not call the provider"
    )
    monkeypatch.setattr(collector_module.time, "monotonic", lambda: 11.0)

    collector._collect_story_hot_lane(rows, deadline=10.0)

    assert collector.story_hot_lane_complete is False
    assert collector.story_hot_lane_failures == 2


def test_story_snapshot_requests_insight_preserving_upsert() -> None:
    calls: list[tuple[object, bool]] = []

    class FakeContentStore:
        def upsert(self, record: object, *, preserve_insights: bool = False) -> None:
            calls.append((record, preserve_insights))

    record = object()
    _StorySnapshotContentStore(FakeContentStore()).upsert(record)

    assert calls == [(record, True)]

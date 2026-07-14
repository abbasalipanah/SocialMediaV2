"""Pure sync, backfill, coverage, and migration-transition contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum


class BackfillStage(StrEnum):
    RECENT_30D = "30d_historical"
    REMAINING_90D = "90d_historical"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SelectionSource(StrEnum):
    LINKED_ACCOUNTS = "linked_accounts"
    TRANSITION_FALLBACK = "transition_fallback"


@dataclass(frozen=True)
class BackfillWindow:
    stage: BackfillStage
    since: date
    until: date

    @property
    def inclusive_days(self) -> int:
        return (self.until - self.since).days + 1


@dataclass(frozen=True)
class BackfillJobState:
    status: JobStatus
    scheduled_for: datetime
    started_at: datetime | None
    error_code: str | None


@dataclass(frozen=True)
class FollowerSeries:
    totals: Mapping[date, int]
    changes: Mapping[date, int]


@dataclass(frozen=True)
class AccountSelection:
    account_ids: tuple[str, ...]
    source: SelectionSource


@dataclass(frozen=True)
class CoverageOutcome:
    missing_account_ids: tuple[str, ...]
    exit_code: int


def initial_backfill_window(today: date) -> BackfillWindow:
    return BackfillWindow(
        stage=BackfillStage.RECENT_30D,
        since=today - timedelta(days=30),
        until=today - timedelta(days=1),
    )


def remaining_backfill_window(today: date) -> BackfillWindow:
    return BackfillWindow(
        stage=BackfillStage.REMAINING_90D,
        since=today - timedelta(days=90),
        until=today - timedelta(days=31),
    )


def recover_stale_job(
    job: BackfillJobState,
    *,
    now: datetime,
    stale_after: timedelta,
) -> BackfillJobState:
    if stale_after <= timedelta(0):
        raise ValueError("stale_window_invalid")
    if (
        job.status is JobStatus.RUNNING
        and job.started_at is not None
        and job.started_at <= now - stale_after
    ):
        return BackfillJobState(
            status=JobStatus.PENDING,
            scheduled_for=now,
            started_at=None,
            error_code="worker_interrupted",
        )
    return job


def defer_rate_limited_job(
    job: BackfillJobState,
    *,
    now: datetime,
    backoff: timedelta = timedelta(minutes=20),
) -> BackfillJobState:
    if backoff <= timedelta(0):
        raise ValueError("rate_backoff_invalid")
    return BackfillJobState(
        status=JobStatus.PENDING,
        scheduled_for=now + backoff,
        started_at=None,
        error_code="rate_limited",
    )


def follower_series(
    *,
    since: date,
    until: date,
    current_total: int,
    observed_values: Mapping[date, int],
    previous_total: int | None,
) -> FollowerSeries:
    if until < since or current_total < 0 or previous_total is not None and previous_total < 0:
        raise ValueError("follower_series_input_invalid")
    if any(day < since or day > until or value < 0 for day, value in observed_values.items()):
        raise ValueError("follower_series_input_invalid")
    days = tuple(_days(since, until))
    if not observed_values:
        totals = {day: current_total for day in days}
    elif current_total > 0 and max(observed_values.values()) < current_total // 2:
        deltas = {day: observed_values.get(day, 0) for day in days}
        deltas[min(observed_values)] = 0
        if previous_total is not None:
            running = previous_total
            totals = {}
            for day in days:
                running = max(0, running + deltas[day])
                totals[day] = running
        else:
            running = current_total
            totals = {}
            for day in reversed(days):
                totals[day] = running
                running = max(0, running - deltas[day])
    else:
        totals = {}
        running = previous_total if previous_total is not None else current_total
        for day in days:
            if day in observed_values:
                running = observed_values[day]
            totals[day] = running
    changes: dict[date, int] = {}
    previous = previous_total
    for day in days:
        changes[day] = 0 if previous is None else totals[day] - previous
        previous = totals[day]
    return FollowerSeries(totals=totals, changes=changes)


def select_collection_accounts(
    *,
    linked_account_ids: tuple[str, ...],
    transition_account_ids: tuple[str, ...],
    transition_complete: bool,
) -> AccountSelection:
    linked = _unique_nonempty(linked_account_ids)
    if linked:
        return AccountSelection(linked, SelectionSource.LINKED_ACCOUNTS)
    if transition_complete:
        return AccountSelection((), SelectionSource.LINKED_ACCOUNTS)
    return AccountSelection(
        _unique_nonempty(transition_account_ids),
        SelectionSource.TRANSITION_FALLBACK,
    )


def d1_coverage(
    expected_account_ids: tuple[str, ...], observed_account_ids: tuple[str, ...]
) -> CoverageOutcome:
    expected = _unique_nonempty(expected_account_ids)
    observed = set(_unique_nonempty(observed_account_ids))
    missing = tuple(account_id for account_id in expected if account_id not in observed)
    return CoverageOutcome(missing_account_ids=missing, exit_code=1 if missing else 0)


def rolling_refresh_window(today: date, mutable_days: int) -> tuple[date, date]:
    if mutable_days < 1 or mutable_days > 365:
        raise ValueError("rolling_window_invalid")
    return today - timedelta(days=mutable_days), today - timedelta(days=1)


def backfill_readiness(
    *,
    completed_stages: tuple[BackfillStage, ...],
    current_stage: BackfillStage | None,
) -> str:
    if BackfillStage.REMAINING_90D in completed_stages:
        return "90d ready"
    if current_stage is BackfillStage.REMAINING_90D:
        return "90d loading"
    if BackfillStage.RECENT_30D in completed_stages:
        return "30d ready"
    return "30d loading"


def _days(since: date, until: date):
    cursor = since
    while cursor <= until:
        yield cursor
        cursor += timedelta(days=1)


def _unique_nonempty(values: tuple[str, ...]) -> tuple[str, ...]:
    if any(not value.strip() for value in values):
        raise ValueError("account_selection_invalid")
    return tuple(dict.fromkeys(values))


__all__ = [
    "AccountSelection",
    "BackfillJobState",
    "BackfillStage",
    "BackfillWindow",
    "CoverageOutcome",
    "FollowerSeries",
    "JobStatus",
    "SelectionSource",
    "d1_coverage",
    "backfill_readiness",
    "defer_rate_limited_job",
    "follower_series",
    "initial_backfill_window",
    "recover_stale_job",
    "remaining_backfill_window",
    "rolling_refresh_window",
    "select_collection_accounts",
]

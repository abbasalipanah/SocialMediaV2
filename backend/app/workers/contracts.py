"""Dormant worker CLI, lock, and cadence declarations."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerContract:
    name: str
    arguments: tuple[str, ...]
    lock_name: str
    cadence: str
    persistent: bool
    lock_busy_exit_code: int = 0


WORKER_CONTRACTS = (
    WorkerContract(
        name="facebook_followers_hourly",
        arguments=(
            "--day",
            "--brand-id",
            "--limit",
            "--missing-today-only",
            "--force-refresh-today",
        ),
        lock_name="facebook-followers-hourly.lock",
        cadence="hourly-at-minute-10",
        persistent=False,
    ),
    WorkerContract(
        name="instagram_followers_hourly",
        arguments=(
            "--day",
            "--brand-id",
            "--limit",
            "--missing-today-only",
            "--force-refresh-today",
        ),
        lock_name="instagram-followers-hourly.lock",
        cadence="hourly-at-minute-05",
        persistent=False,
    ),
    WorkerContract(
        name="instagram_stories",
        arguments=("--mode", "--since-days", "--until-days", "--brand-id"),
        lock_name="instagram-stories.lock",
        cadence="hourly-at-minute-15",
        persistent=False,
    ),
    WorkerContract(
        name="social_backfill_jobs",
        arguments=("--platform", "--brand-id", "--limit"),
        lock_name="social-backfill-jobs.lock",
        cadence="minute-07-27-47",
        persistent=True,
    ),
)


__all__ = ["WORKER_CONTRACTS", "WorkerContract"]

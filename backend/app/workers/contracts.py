"""Standalone worker CLI, lock, and cadence declarations."""

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
        name="standalone_social_collection",
        arguments=(
            "--platform",
            "--brand-id",
            "--asset-id",
            "--scheduled",
        ),
        lock_name="social_media_v2:scheduled_collection",
        cadence="every-30-minutes",
        persistent=True,
    ),
    WorkerContract(
        name="tiktok_connection_verification",
        arguments=("--connection-id",),
        lock_name="social_media_v2:tiktok_canary:{connection_id}",
        cadence="manual-only",
        persistent=False,
    ),
)


__all__ = ["WORKER_CONTRACTS", "WorkerContract"]

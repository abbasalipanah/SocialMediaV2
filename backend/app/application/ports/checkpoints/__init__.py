"""Typed provider checkpoint and idempotency contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.domain.platforms import CapabilityId, PlatformId


@dataclass(frozen=True)
class CheckpointKey:
    platform: PlatformId
    capability: CapabilityId
    account_id: str

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", self.account_id):
            raise ValueError("checkpoint_account_invalid")


MAX_CURSOR_BYTES = 8192


@dataclass(frozen=True)
class ProviderCheckpoint:
    key: CheckpointKey
    version: int
    cursor: str | None
    watermark: str | None
    observed_through: datetime | None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("checkpoint_version_invalid")
        # Facebook pagination cursors on an established Page run past 2 kB, so the
        # old bound rejected legitimate paging and abandoned the rest of the feed
        # partway through. The bound stays, to keep a runaway cursor out of the
        # projection, but at a size the provider actually produces.
        if self.cursor is not None and len(self.cursor.encode("utf-8")) > MAX_CURSOR_BYTES:
            raise ValueError("checkpoint_cursor_too_large")
        if self.watermark is not None and len(self.watermark.encode("utf-8")) > 512:
            raise ValueError("checkpoint_watermark_too_large")
        if self.observed_through is not None and self.observed_through.tzinfo is None:
            raise ValueError("checkpoint_observed_time_invalid")


class CheckpointStore(Protocol):
    def get(self, key: CheckpointKey) -> ProviderCheckpoint | None: ...

    def put(self, checkpoint: ProviderCheckpoint, *, expected_version: int | None) -> bool: ...

    def claim_once(
        self, key: CheckpointKey, operation_id: str, expires_at: datetime
    ) -> bool: ...


__all__ = ["CheckpointKey", "CheckpointStore", "ProviderCheckpoint"]

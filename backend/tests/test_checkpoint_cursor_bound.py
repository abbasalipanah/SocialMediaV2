"""Pagination cursors must survive the checkpoint bound.

Facebook cursors on an established Page run past two kilobytes. Rejecting them
abandoned the rest of the feed partway through a run, which read as a content
failure rather than as a bound that was simply set too low.
"""

from __future__ import annotations

import pytest

from app.application.ports.checkpoints import (
    MAX_CURSOR_BYTES,
    CheckpointKey,
    ProviderCheckpoint,
)
from app.domain.platforms import CapabilityId, PlatformId


def _checkpoint(cursor: str) -> ProviderCheckpoint:
    return ProviderCheckpoint(
        key=CheckpointKey(
            platform=PlatformId.FACEBOOK,
            capability=CapabilityId.CONTENT,
            account_id="page-1",
        ),
        version=1,
        cursor=cursor,
        watermark=None,
        observed_through=None,
    )


def test_a_realistic_provider_cursor_is_accepted() -> None:
    assert MAX_CURSOR_BYTES >= 8192
    assert _checkpoint("a" * 4096).cursor is not None


def test_the_bound_still_holds() -> None:
    # It exists to keep a runaway cursor out of the projection.
    with pytest.raises(ValueError, match="checkpoint_cursor_too_large"):
        _checkpoint("a" * (MAX_CURSOR_BYTES + 1))

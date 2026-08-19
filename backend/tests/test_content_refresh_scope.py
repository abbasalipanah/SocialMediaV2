"""A routine refresh reads the newest posts, not the whole archive.

Content is collected with a per-item insights call, so re-walking an account's
entire history every half hour spent the account's whole turn on posts whose
numbers had long settled. Five of the first six accounts in a run were
interrupted inside `fetch_content_insights` for exactly this reason, and the
accounts queued behind them were never reached.
"""

from __future__ import annotations

import pytest

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.application.services.collection.content import collect_content
from app.application.services.collection.contracts import CollectionTarget
from app.domain.platforms import CapabilityId, PlatformId


@pytest.fixture
def collection_target() -> CollectionTarget:
    return CollectionTarget(
        account=ProviderAccount(
            platform=PlatformId.INSTAGRAM,
            account_id="ig-1",
            credential=ProviderCredential(access_token="opaque"),
        ),
        local_account_id=1,
        brand_id=1,
    )


class _Page:
    def __init__(self, items, next_cursor):
        self.items = items
        self.next_cursor = next_cursor
        self.observed_at = None


class _Reader:
    def __init__(self) -> None:
        self.cursors: list[str | None] = []

    def list_content(self, account, cursor=None):
        self.cursors.append(cursor)
        return _Page((), f"page-{len(self.cursors)}")


class _Store:
    def upsert(self, record) -> None:
        return None


class _Checkpoints:
    def __init__(self, existing: ProviderCheckpoint | None = None) -> None:
        self.existing = existing
        self.written: list[ProviderCheckpoint] = []

    def get(self, key):
        return self.existing

    def put(self, checkpoint, expected_version=None):
        self.written.append(checkpoint)
        self.existing = checkpoint
        return True


def _key(target) -> CheckpointKey:
    return CheckpointKey(
        platform=PlatformId.INSTAGRAM,
        capability=CapabilityId.CONTENT,
        account_id=target.account.account_id,
    )


def _collect(target, *, checkpoints, refresh_only, max_pages=2):
    reader = _Reader()
    outcome = collect_content(
        target=target,
        reader=reader,
        content_store=_Store(),
        checkpoint_store=checkpoints,
        max_pages=max_pages,
        refresh_only=refresh_only,
    )
    return reader, outcome


def test_a_refresh_starts_at_the_newest_page(collection_target) -> None:
    stored = ProviderCheckpoint(
        key=_key(collection_target),
        version=4,
        cursor="deep-in-the-archive",
        watermark=None,
        observed_through=None,
    )
    reader, _ = _collect(
        collection_target, checkpoints=_Checkpoints(stored), refresh_only=True
    )

    # Resuming would refresh posts from months ago and miss this morning's.
    assert reader.cursors[0] is None


def test_a_refresh_does_not_record_how_far_it_reached(collection_target) -> None:
    checkpoints = _Checkpoints()
    _collect(collection_target, checkpoints=checkpoints, refresh_only=True)

    assert [written.cursor for written in checkpoints.written] == [None, None]


def test_a_backfill_still_resumes_where_it_stopped(collection_target) -> None:
    stored = ProviderCheckpoint(
        key=_key(collection_target),
        version=4,
        cursor="deep-in-the-archive",
        watermark=None,
        observed_through=None,
    )
    checkpoints = _Checkpoints(stored)
    reader, _ = _collect(collection_target, checkpoints=checkpoints, refresh_only=False)

    assert reader.cursors[0] == "deep-in-the-archive"
    assert checkpoints.written[-1].cursor is not None

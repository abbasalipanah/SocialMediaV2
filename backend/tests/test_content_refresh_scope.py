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


class _ConflictOnceCheckpoints(_Checkpoints):
    def __init__(self) -> None:
        super().__init__()
        self.conflicted = False

    def put(self, checkpoint, expected_version=None):
        if not self.conflicted:
            self.conflicted = True
            self.existing = ProviderCheckpoint(
                key=checkpoint.key,
                version=checkpoint.version,
                cursor=checkpoint.cursor,
                watermark=checkpoint.watermark,
                observed_through=checkpoint.observed_through,
            )
            return False
        return super().put(checkpoint, expected_version=expected_version)


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


def test_a_concurrent_checkpoint_is_adopted_without_failing_the_account(
    collection_target,
) -> None:
    outcome = collect_content(
        target=collection_target,
        reader=_Reader(),
        content_store=_Store(),
        checkpoint_store=_ConflictOnceCheckpoints(),
        max_pages=1,
        refresh_only=True,
    )

    # The concurrent write is adopted cleanly. The refresh is still partial
    # because this fixture advertises another page while the caller allows
    # only one; that page-limit result must not be confused with a checkpoint
    # conflict failure.
    assert outcome.status.value == "partial"
    assert outcome.error_code == "page_limit_reached"


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


def test_a_refresh_asks_for_fewer_items_than_a_backfill() -> None:
    """The provider is asked for insights on every item a page yields, and that
    call takes seconds. A hundred of them outlast an account's whole share of a
    run, which is what kept every account being interrupted in the same place.
    """
    from app.workers.collector import (
        FULL_PAGE_SIZE,
        REFRESH_PAGE_SIZE,
    )

    assert REFRESH_PAGE_SIZE < FULL_PAGE_SIZE
    assert REFRESH_PAGE_SIZE <= 25


def test_the_readers_refuse_a_page_size_the_provider_would_reject() -> None:
    import pytest

    from app.infrastructure.providers.meta.facebook.content import FacebookContentReader
    from app.infrastructure.providers.meta.instagram.content import (
        InstagramContentReader,
    )

    for reader in (FacebookContentReader, InstagramContentReader):
        with pytest.raises(ValueError):
            reader(object(), page_size=0)
        with pytest.raises(ValueError):
            reader(object(), page_size=101)


def test_feed_insights_do_not_fall_back_for_a_story_only_metric() -> None:
    from app.infrastructure.providers.meta.instagram.content_insights import (
        MEDIA_INSIGHT_METRICS,
        STORY_INSIGHT_METRICS,
    )

    # Meta rejects the whole comma-separated request when `replies` is sent
    # for an ordinary feed post. That made the reader retry every metric one at
    # a time and turned a complete account refresh into a 100-second operation.
    assert "replies" not in MEDIA_INSIGHT_METRICS
    assert "replies" in STORY_INSIGHT_METRICS
    # These legacy/per-media metrics are rejected for current Stories. One
    # rejected name invalidates the whole comma-separated request and used to
    # trigger sixteen individual retries for every Story.
    assert set(STORY_INSIGHT_METRICS) == {
        "views",
        "reach",
        "total_interactions",
        "shares",
        "replies",
        "navigation",
        "profile_visits",
        "follows",
    }

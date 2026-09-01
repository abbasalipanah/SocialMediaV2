"""Media already on disk must not be downloaded again.

A published post's image does not change, and the provider's URLs are signed
and rotate, so there is nothing to compare them against. Every run re-fetched
every image it already held: an account that had not finished spent its whole
turn downloading bytes that were already stored, was interrupted by its budget,
and so was never marked finished -- which meant it started over next run.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.application.ports.persistence import MediaRecord
from app.application.ports.platforms import ProviderAccount, ProviderCredential, ProviderRecord
from app.application.services.collection.contracts import CollectionTarget
from app.application.services.collection.media import (
    ContentMediaWriter,
    FetchedMedia,
    MediaBudgetDeferred,
)
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.media_files import AtomicMediaFiles


class _Store:
    def __init__(self, record: MediaRecord | None, kind: str = "cover") -> None:
        self.record = record
        self.kind = kind
        self.written: list[MediaRecord] = []

    def get(self, account_id: int, external_content_id: str, media_kind: str):
        return self.record if media_kind == self.kind else None

    def upsert(self, record: MediaRecord) -> None:
        self.written.append(record)


def _target() -> CollectionTarget:
    return CollectionTarget(
        account=ProviderAccount(
            platform=PlatformId.INSTAGRAM,
            account_id="ig-1",
            credential=ProviderCredential(access_token="opaque"),
        ),
        local_account_id=2790,
        brand_id=57,
    )


def _item() -> ProviderRecord:
    return ProviderRecord(
        external_id="18005672441954835",
        observed_at=datetime(2026, 8, 19, tzinfo=UTC),
        fields={"media_url": "https://scontent.cdninstagram.com/a.jpg"},
    )


def _record(path: str, kind: str = "cover") -> MediaRecord:
    return MediaRecord(
        platform=PlatformId.INSTAGRAM,
        account_id=2790,
        brand_id=57,
        external_content_id="18005672441954835",
        media_kind=kind,
        storage_path=path,
        source_url="https://scontent.cdninstagram.com/old.jpg",
        source_status=200,
        mime_type="image/jpeg",
        size_bytes=3,
        checksum="abc",
        verified_at=datetime(2026, 8, 19, tzinfo=UTC),
    )


def _writer(tmp_path: Path, store: _Store, fetches: list[str]) -> ContentMediaWriter:
    def fetch(url: str) -> FetchedMedia:
        fetches.append(url)
        return FetchedMedia(data=b"img", mime_type="image/jpeg", status_code=200)

    return ContentMediaWriter(
        target=_target(),
        files=AtomicMediaFiles(tmp_path),
        media_store=store,
        fetch=fetch,
    )


def test_a_stored_image_is_not_fetched_again(tmp_path: Path) -> None:
    stored = tmp_path / "instagram" / "2790" / "18005672441954835.jpg"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"img")
    fetches: list[str] = []

    written = _writer(
        tmp_path, _Store(_record("instagram/2790/18005672441954835.jpg")), fetches
    ).persist(_item())

    assert fetches == []
    assert written == 0


def test_a_record_whose_file_is_gone_is_fetched(tmp_path: Path) -> None:
    fetches: list[str] = []

    _writer(
        tmp_path, _Store(_record("instagram/2790/18005672441954835.jpg")), fetches
    ).persist(_item())

    # The row promised a file that is not there; re-fetching is the repair.
    assert fetches == ["https://scontent.cdninstagram.com/a.jpg"]


def test_an_empty_leftover_does_not_count_as_stored(tmp_path: Path) -> None:
    stored = tmp_path / "instagram" / "2790" / "18005672441954835.jpg"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"")
    fetches: list[str] = []

    _writer(
        tmp_path, _Store(_record("instagram/2790/18005672441954835.jpg")), fetches
    ).persist(_item())

    assert fetches == ["https://scontent.cdninstagram.com/a.jpg"]


def test_an_unseen_item_is_fetched(tmp_path: Path) -> None:
    fetches: list[str] = []

    _writer(tmp_path, _Store(None), fetches).persist(_item())

    assert fetches == ["https://scontent.cdninstagram.com/a.jpg"]


def test_media_budget_defers_the_page_without_starting_a_fetch(tmp_path: Path) -> None:
    fetches: list[str] = []
    writer = ContentMediaWriter(
        target=_target(),
        files=AtomicMediaFiles(tmp_path),
        media_store=_Store(None),
        fetch=lambda url: fetches.append(url),
        can_fetch=lambda: False,
    )

    with pytest.raises(MediaBudgetDeferred, match="media_phase_budget_exhausted"):
        writer.persist(_item())

    assert fetches == []


def test_an_imported_story_cover_counts_as_held(tmp_path: Path) -> None:
    """The V1 import filed a Story's image under its own kind.

    V2 writes every cover under one name, so looking only there meant an
    imported Story image was never recognised as held. Those were re-downloaded
    on every run, which is where the last stalling account spent its budget.
    """
    stored = tmp_path / "content-assets" / "instagram" / "2790" / "s.jpg"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"img")
    fetches: list[str] = []
    store = _Store(
        _record("content-assets/instagram/2790/s.jpg", kind="story_cover"),
        kind="story_cover",
    )

    written = _writer(tmp_path, store, fetches).persist(_item())

    assert fetches == []
    assert written == 0

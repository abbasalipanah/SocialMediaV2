"""Content cover persistence across the file and metadata stores."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from app.application.ports.persistence import MediaRecord, MediaStore
from app.application.ports.platforms import ProviderRecord
from app.core.time import utc_now
from app.infrastructure.persistence.media_files import AtomicMediaFiles

from .contracts import CollectionTarget


@dataclass(frozen=True)
class FetchedMedia:
    data: bytes
    mime_type: str
    status_code: int

    def __post_init__(self) -> None:
        if not self.data or not self.mime_type or not 200 <= self.status_code < 300:
            raise ValueError("fetched_media_invalid")


# V2 writes every cover under one kind; the V1 import distinguished a Story's
# cover from a post's. Looking under only V2's name meant an imported Story
# image was never recognised as held, so those were re-downloaded on every run
# -- which is exactly where the last stalling account spent its budget.
STORED_MEDIA_KINDS = ("cover", "story_cover")


class ContentMediaWriter:
    def __init__(
        self,
        *,
        target: CollectionTarget,
        files: AtomicMediaFiles,
        media_store: MediaStore,
        fetch: Callable[[str], FetchedMedia],
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._target = target
        self._files = files
        self._media_store = media_store
        self._fetch = fetch
        self._clock = clock

    def _already_held(self, item: ProviderRecord) -> bool:
        for media_kind in STORED_MEDIA_KINDS:
            stored = self._media_store.get(
                self._target.local_account_id, item.external_id, media_kind
            )
            if stored is not None and self._files.holds(stored.storage_path):
                return True
        return False

    def persist(self, item: ProviderRecord) -> int:
        # A published post's image does not change, and the provider's URLs are
        # signed and rotate, so there is nothing to compare them against. Every
        # run therefore re-downloaded every image it already held: an account
        # that had not finished spent its whole turn fetching bytes that were
        # already on disk, and never got far enough to be marked done.
        if self._already_held(item):
            return 0
        selected: tuple[str, FetchedMedia] | None = None
        for source_url in _media_candidates(item):
            try:
                selected = (source_url, self._fetch(source_url))
            except Exception:
                continue
            break
        if selected is None:
            return 0
        source_url, fetched = selected
        suffix = _suffix(fetched.mime_type)
        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", item.external_id)
        relative_path = (
            f"{self._target.account.platform.value}/"
            f"{self._target.local_account_id}/{safe_id}.{suffix}"
        )
        persisted = self._files.persist(relative_path, fetched.data)
        self._media_store.upsert(
            MediaRecord(
                platform=self._target.account.platform,
                account_id=self._target.local_account_id,
                brand_id=self._target.brand_id,
                external_content_id=item.external_id,
                media_kind="cover",
                storage_path=persisted.relative_path,
                source_url=source_url,
                source_status=fetched.status_code,
                mime_type=fetched.mime_type,
                size_bytes=persisted.size_bytes,
                checksum=persisted.checksum,
                verified_at=self._clock(),
            )
        )
        return 1


def _media_candidates(item: ProviderRecord) -> tuple[str, ...]:
    fields = item.fields
    candidates: list[str] = []
    for key in (
        "cover_candidates",
        "thumbnail_candidates",
        "media_url_candidates",
    ):
        values = fields.get(key, ())
        if isinstance(values, tuple | list):
            candidates.extend(value for value in values if isinstance(value, str) and value)
    for key in ("cover_url", "thumbnail_url", "media_url"):
        value = fields.get(key)
        if isinstance(value, str) and value:
            candidates.append(value)
    return tuple(dict.fromkeys(candidates))


def _suffix(mime_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "video/mp4": "mp4",
    }.get(mime_type.lower(), "bin")


__all__ = ["ContentMediaWriter", "FetchedMedia"]

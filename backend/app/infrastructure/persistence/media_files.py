"""Atomic, root-confined media byte persistence."""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PersistedMedia:
    relative_path: str
    size_bytes: int
    checksum: str


class AtomicMediaFiles:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def holds(self, relative_path: str) -> bool:
        """Whether this path is already on disk, and not an empty leftover."""
        if not relative_path:
            return False
        destination = (self._root / relative_path).resolve()
        if self._root not in destination.parents:
            return False
        return destination.is_file() and destination.stat().st_size > 0

    def persist(self, relative_path: str, data: bytes) -> PersistedMedia:
        if not relative_path or not data:
            raise ValueError("media_write_input_invalid")
        destination = (self._root / relative_path).resolve()
        if self._root not in destination.parents:
            raise ValueError("media_path_outside_root")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=destination.parent,
                prefix=".partial-",
                delete=False,
            ) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
                temporary = Path(handle.name)
            os.replace(temporary, destination)
        except Exception:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            raise
        return PersistedMedia(
            relative_path=str(destination.relative_to(self._root)),
            size_bytes=len(data),
            checksum=hashlib.sha256(data).hexdigest(),
        )


__all__ = ["AtomicMediaFiles", "PersistedMedia"]

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from scripts.import_legacy_brand import (
    _content_type,
    _copy_media,
    _safe_media_url,
    _validate_urls,
)


def test_database_guard_requires_a_separate_v2_owned_target() -> None:
    source = make_url("postgresql+psycopg://source@127.0.0.1/socialmedia_adv")

    _validate_urls(
        source,
        make_url("postgresql+psycopg://v2@127.0.0.1:55432/social_media_v2_local"),
    )

    with pytest.raises(RuntimeError, match="v2_owned"):
        _validate_urls(
            source,
            make_url("postgresql+psycopg://v2@127.0.0.1/another_database"),
        )
    with pytest.raises(RuntimeError, match="must_differ"):
        _validate_urls(
            make_url("postgresql+psycopg://source@127.0.0.1:55432/social_media_v2_local"),
            make_url("postgresql+psycopg://v2@127.0.0.1:55432/social_media_v2_local"),
        )


def test_media_url_guard_rejects_oauth_material() -> None:
    assert _safe_media_url("https://cdn.example.test/image.jpg?size=large")
    assert _safe_media_url("https://cdn.example.test/image.jpg?access_token=secret") == ""
    assert _safe_media_url("/source-project/media/image.jpg") == ""
    assert _content_type("CAROUSEL_ALBUM") == "carousel"


def test_media_copy_checks_the_source_checksum(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    target_root = tmp_path / "target"
    source = source_root / "content-assets" / "facebook" / "cover.jpg"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"pine-beach-cover")
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    snapshot = {
        "media": [
            {
                "storage_path": "content-assets/facebook/cover.jpg",
                "size_bytes": source.stat().st_size,
                "checksum": checksum,
            }
        ]
    }

    _copy_media(snapshot, source_root, target_root)

    assert (target_root / "content-assets/facebook/cover.jpg").read_bytes() == source.read_bytes()

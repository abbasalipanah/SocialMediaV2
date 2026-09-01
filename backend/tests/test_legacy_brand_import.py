from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from scripts.import_legacy_brand import (
    AUDIENCE_METRIC_MAP,
    _content_type,
    _copy_media,
    _safe_media_url,
    _validate_urls,
    _verify_existing_media,
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


def test_demo_audience_city_rows_are_projected() -> None:
    assert AUDIENCE_METRIC_MAP["audience_cities"] == ("followers", "audience_cities")


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


def test_existing_media_verification_is_read_only_and_checksum_strict(tmp_path: Path) -> None:
    root = tmp_path / "target"
    media = root / "demo-assets" / "cover.webp"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"demo-cover")
    snapshot = {
        "media": [
            {
                "storage_path": "demo-assets/cover.webp",
                "size_bytes": media.stat().st_size,
                "checksum": hashlib.sha256(media.read_bytes()).hexdigest(),
            },
            {
                "storage_path": "demo-assets/cover.webp",
                "size_bytes": media.stat().st_size,
                "checksum": hashlib.sha256(media.read_bytes()).hexdigest(),
            },
        ]
    }

    assert _verify_existing_media(snapshot, root, label="target") == 1
    media.write_bytes(b"wrong-cover")
    with pytest.raises(RuntimeError, match="target_media_size_mismatch"):
        _verify_existing_media(snapshot, root, label="target")

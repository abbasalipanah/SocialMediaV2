"""Comment collection must not re-read an account's whole archive every run.

Meta comment reads were unbounded: every content item an account had, up to
twenty pages each, on every scheduled run. An account with hundreds of posts
spent its entire turn re-reading comments that had not changed, and the
accounts queued behind it were never reached at all. TikTok has always been
bounded this way; the Meta path was not.
"""

from __future__ import annotations

from app.workers.collector import COMMENTED_CONTENT_PER_RUN


def test_a_bound_exists_and_is_modest() -> None:
    assert 1 <= COMMENTED_CONTENT_PER_RUN <= 50


def test_the_meta_path_applies_the_bound() -> None:
    from pathlib import Path

    source = Path("app/workers/collector.py").read_text(encoding="utf-8")
    # The bound has to sit on the Meta record sink, which is the caller that was
    # unbounded; asserting on the constant alone would not notice it going unused.
    assert "if commented_items < COMMENTED_CONTENT_PER_RUN:" in source


def test_tiktok_keeps_its_own_bound() -> None:
    from pathlib import Path

    source = Path("app/workers/collector.py").read_text(encoding="utf-8")
    assert "commented_videos < 10" in source

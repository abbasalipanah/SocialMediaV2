"""A newly connected account should not wait for the main queue.

TikTok collects the moment its connection is verified, so an admin sees data as
soon as setup finishes. A Meta account waited for the scheduled pass to reach
it. The staleness ordering already puts a never-collected account at the head of
the next run, and a small pass of its own closes the rest of the gap without
running provider work inside the web process, where the per-account budget's
SIGALRM cannot safely live.
"""

from __future__ import annotations

from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
COLLECTOR = (BACKEND / "app" / "workers" / "collector.py").read_text(encoding="utf-8")
TARGETS = (
    BACKEND / "app" / "infrastructure" / "persistence" / "social_v2" / "collection_targets.py"
).read_text(encoding="utf-8")


def test_the_fast_lane_selects_only_never_collected_accounts() -> None:
    assert "la.last_synced_at IS NULL" in TARGETS


def test_the_fast_lane_holds_its_own_lock() -> None:
    # Sharing the scheduled lock would make the fast lane wait behind a full
    # pass, which is the delay it exists to remove.
    assert "social_media_v2:new_account_collection" in COLLECTOR
    assert "social_media_v2:scheduled_collection" in COLLECTOR


def test_the_main_queue_still_puts_new_accounts_first() -> None:
    # Even without the fast lane, a never-collected account leads the next run.
    assert "la.last_synced_at ASC NULLS FIRST" in TARGETS

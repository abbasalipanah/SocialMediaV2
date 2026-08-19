"""An imported account must not be re-read from scratch on every run.

V2 marks a finished account `complete`; the V1 import wrote `completed`. While
the collector compared against a single spelling, all 79 imported accounts
looked mid-backfill forever and each scheduled run asked the provider for a
thirty-day window per account instead of one day. A pass then outlasted the
service timeout and was killed before it could mark anything finished, so the
state that caused the slowness could never be corrected by finishing.
"""

from __future__ import annotations

from app.workers.collector import BACKFILL_COMPLETE_STATUSES, _backfill_complete


def test_both_spellings_count_as_finished() -> None:
    assert _backfill_complete("complete")
    assert _backfill_complete("completed")


def test_unfinished_states_still_ask_for_the_backfill_window() -> None:
    assert not _backfill_complete("pending")
    assert not _backfill_complete("disabled")
    assert not _backfill_complete("")


def test_comparison_survives_casing_and_padding() -> None:
    assert _backfill_complete(" Completed ")
    assert _backfill_complete("COMPLETE")


def test_vocabulary_is_explicit() -> None:
    # Kept as a named set so a third spelling is added deliberately rather than
    # discovered from a collection run that no longer finishes.
    assert BACKFILL_COMPLETE_STATUSES == {"complete", "completed"}

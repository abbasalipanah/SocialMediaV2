"""Video totals must land on a day the dashboard actually reads.

They were written with today's date while every reporting range ends yesterday,
so the rows sat in the table and six cards -- video views, likes, comments,
shares, engagements and engagement rate -- stayed permanently blank.
"""

from __future__ import annotations

from pathlib import Path

COLLECTOR = (Path(__file__).resolve().parents[1] / "app" / "workers" / "collector.py").read_text(
    encoding="utf-8"
)


def test_totals_use_the_same_day_as_the_daily_metrics() -> None:
    tiktok = COLLECTOR.split("def _collect_tiktok", 1)[1]
    write = tiktok.split("for metric_id, value in totals.items():", 1)[1].split(")", 1)[0]
    assert "observed_on=until" in write
    assert "observed_on=date.today()" not in write


def test_the_daily_window_still_ends_on_the_last_complete_day() -> None:
    assert "until = today - timedelta(days=1)" in COLLECTOR


def test_completed_tiktok_accounts_reprove_the_window_for_new_daily_components() -> None:
    tiktok = COLLECTOR.split("def _collect_tiktok", 1)[1]

    assert "TIKTOK_DAILY_METRIC_CHECKPOINT_SUFFIX" in tiktok
    assert "inferred_daily_observed_on = None" in tiktok
    assert "daily_checkpoint_key" in tiktok
    assert "observed_through=datetime.combine" in tiktok
    assert "since = until if _backfill_complete" not in tiktok

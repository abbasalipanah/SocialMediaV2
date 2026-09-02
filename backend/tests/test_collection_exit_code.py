"""A healthy collection run must not report itself as failed.

Exiting non-zero on any imperfect account marked every run failed: a partial
account is ordinary -- a provider withholds one metric and the rest is
collected. systemd showed `failed` on a healthy system, which is precisely the
state a real failure would have to stand out from.
"""

from __future__ import annotations

from app.workers.collector import WorkerAccountResult, collection_exit_code


def _result(status: str) -> WorkerAccountResult:
    return WorkerAccountResult(
        platform="instagram",
        brand_id=219392,
        asset_id=1,
        status=status,
        error_code=None if status == "success" else "metric_unavailable",
    )


def test_a_run_with_partial_accounts_succeeded() -> None:
    assert collection_exit_code((_result("success"), _result("partial"))) == 0


def test_a_run_where_some_accounts_failed_still_succeeded() -> None:
    # The failures are recorded per account and logged; the run did its job.
    assert collection_exit_code((_result("partial"), _result("failed"))) == 0


def test_a_run_that_reached_nothing_is_a_failure() -> None:
    assert collection_exit_code((_result("failed"), _result("failed"))) == 1


def test_a_run_with_no_accounts_to_collect_is_not_a_failure() -> None:
    assert collection_exit_code(()) == 0


def test_incomplete_story_hot_lane_is_a_critical_run_failure() -> None:
    assert collection_exit_code((_result("success"),), critical_failure=True) == 1

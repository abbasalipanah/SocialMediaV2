"""One slow account must not consume the whole collection window.

A single account stalled inside a provider read and held the run until systemd
terminated it, taking every account queued behind it. Because targets came back
in a fixed order, the next run began at the same account and stalled again, so
the queue behind it was never reached at all.
"""

from __future__ import annotations

import time

import pytest

from app.workers.collector import (
    DEFAULT_ACCOUNT_BUDGET_SECONDS,
    DEFAULT_RUN_BUDGET_SECONDS,
    AccountBudgetExceeded,
    StandaloneCollector,
    _error_code,
)


def test_the_account_budget_leaves_room_inside_the_run_budget() -> None:
    # Otherwise the first slow account would exhaust the run on its own. A
    # quarter of the run is already generous for one account.
    assert DEFAULT_ACCOUNT_BUDGET_SECONDS <= DEFAULT_RUN_BUDGET_SECONDS // 4


def test_the_account_budget_clears_the_heaviest_measured_account() -> None:
    # The busiest account measured needs 233s, nearly all of it reading the
    # insights of around sixty live Stories one at a time.
    assert DEFAULT_ACCOUNT_BUDGET_SECONDS >= 280


def test_the_run_budget_stops_before_the_service_timeout() -> None:
    # The unit allows 1500s; stopping at the budget lets the account in flight
    # finish and be committed instead of being killed mid-write.
    assert DEFAULT_RUN_BUDGET_SECONDS < 1500


def test_a_stalled_account_is_interrupted() -> None:
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = 1

    with pytest.raises(AccountBudgetExceeded):
        with collector._account_budget():
            time.sleep(5)


def test_the_alarm_is_cleared_after_a_healthy_account() -> None:
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = 1

    with collector._account_budget():
        pass
    # A leaked alarm would fire during whichever account came next and blame it
    # for the previous one's stall.
    time.sleep(2)


def test_the_budget_can_be_switched_off() -> None:
    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = None

    with collector._account_budget():
        pass


def test_the_interruption_is_recorded_as_its_own_reason() -> None:
    code = _error_code(AccountBudgetExceeded("account_budget_exceeded"))
    assert code == "accountbudgetexceeded:account_budget_exceeded"


def test_the_interrupt_survives_the_phase_handlers() -> None:
    """The collection phases catch broadly so one provider fault does not lose
    the rest of an account. The budget interrupt must pass straight through
    them, or a stalled account keeps the run and is never recorded as stalled.
    """
    assert not issubclass(AccountBudgetExceeded, Exception)

    collector = StandaloneCollector.__new__(StandaloneCollector)
    collector._account_budget_seconds = 1

    with pytest.raises(AccountBudgetExceeded):
        with collector._account_budget():
            try:
                time.sleep(5)
            except Exception:  # noqa: BLE001 - mirrors the phase handlers
                pytest.fail("a phase handler swallowed the budget interrupt")

"""Coverage is measured against the accounts a run is expected to write.

The same Facebook Page and Instagram profile are linked twice: once under a
rollup parent and once under one of its children. The parent's pair is disabled
so the accounts are collected once rather than twice. They still counted
towards coverage, so the Limak rollup reported "Partial reporting coverage"
permanently -- with no account anyone could fix to clear it.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.application.ports.reporting import ReportingAccount
from app.application.queries.dashboards import collected_accounts
from app.domain.platforms import PlatformId


def _account(account_id: int, status: str) -> ReportingAccount:
    return ReportingAccount(
        account_id=account_id,
        brand_id="218998",
        platform=PlatformId.FACEBOOK,
        external_id="138663676259165",
        display_name="Limak International Hotels & Resorts",
        status="active",
        connection_state="connected",
        health_status="healthy",
        backfill_status="complete",
        nightly_enabled=True,
        last_synced_at=datetime(2026, 8, 18, tzinfo=UTC),
        # The asset stays active and the platform connection stays healthy; it
        # is the link that is disabled, which is why neither of the other two
        # fields could be used to spot it.
        link_status=status,
    )


def test_a_disabled_duplicate_is_not_expected_to_report() -> None:
    accounts = (_account(2834, "disabled"), _account(2844, "active"))

    assert [account.account_id for account in collected_accounts(accounts)] == [2844]


def test_active_accounts_are_all_kept() -> None:
    accounts = (_account(1, "active"), _account(2, "active"))

    assert len(collected_accounts(accounts)) == 2


def test_the_comparison_survives_casing_and_padding() -> None:
    assert collected_accounts((_account(1, " Disabled "),)) == ()


def test_an_unfamiliar_status_still_counts() -> None:
    # Coverage should err towards reporting a gap, not towards hiding one.
    assert len(collected_accounts((_account(1, "needs_reauth"),))) == 1

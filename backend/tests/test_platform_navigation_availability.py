"""A platform is navigable for a Brand when that Brand has an account on it.

Navigation folded in the capability records, which describe what the product
supports rather than what a Brand has. Every platform was therefore navigable
for every Brand: TikTok opened on a Brand with no TikTok account and rendered
an empty dashboard headed "No Accounts", and the sidebar could not lock it
because the API had told it the platform was available.
"""

from __future__ import annotations

from pathlib import Path

SOURCE = (
    Path(__file__).resolve().parents[1] / "app" / "api" / "workspace" / "__init__.py"
).read_text(encoding="utf-8")


def test_navigation_is_decided_by_linked_accounts() -> None:
    assert (
        "navigation_available=any(\n"
        "                        account.platform is platform for account in accounts\n"
        "                    )," in SOURCE
    )


def test_capability_records_no_longer_open_navigation() -> None:
    # The records still populate `capabilities` on the response; they just do
    # not decide whether the Brand may open the platform.
    navigation = SOURCE.split("navigation_available=", 1)[1].split("),", 1)[0]
    assert "capabilities.records()" not in navigation

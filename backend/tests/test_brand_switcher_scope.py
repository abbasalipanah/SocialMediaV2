"""The switcher offers the Brands this product actually covers.

The signed scope lists every Brand the user may open in Accumulate, which is far
wider than the set Social Media serves. Offering all of them turns the switcher
into a list of dead ends.
"""

from __future__ import annotations

from app.application.queries.brand_visibility import brands_with_social_media
from app.domain.authority import (
    BrandFamilyProjection,
    BrandScope,
    BrandWorkspace,
    WorkspaceBrand,
)


class FakeReportingStore:
    def __init__(self, connected: set[str]) -> None:
        self._connected = connected
        self.asked: tuple[str, ...] = ()

    def list_accounts(self, *, brand_ids, platform=None):
        self.asked = brand_ids
        return tuple(
            type("Account", (), {"brand_id": brand_id})()
            for brand_id in brand_ids
            if brand_id in self._connected
        )


def _brand(brand_id: str, parent: str | None = None, visibility: str = "active"):
    return WorkspaceBrand(
        brand_id=brand_id,
        name=f"Brand {brand_id}",
        parent_brand_id=parent,
        visibility=visibility,  # type: ignore[arg-type]
        access_mode="write",
        role="super_admin",
    )


def _workspace(brands, families=()):
    return BrandWorkspace(
        default_brand_id="1",
        brands=tuple(brands),
        families=tuple(families),
        scope=BrandScope(requested_brand_id="1", rollup=False, resolved_brand_ids=("1",)),
    )


def test_brands_without_an_account_are_not_offered() -> None:
    workspace = _workspace([_brand("1"), _brand("2"), _brand("3")])

    result = brands_with_social_media(
        workspace, reporting_store=FakeReportingStore({"1"}), keep_brand_id="1"
    )

    assert [brand.brand_id for brand in result.brands] == ["1"]


def test_the_launch_brand_is_always_offered() -> None:
    # Dropping the Brand the session resolved to would fail the workspace.
    workspace = _workspace([_brand("1"), _brand("2")])

    result = brands_with_social_media(
        workspace, reporting_store=FakeReportingStore(set()), keep_brand_id="2"
    )

    assert [brand.brand_id for brand in result.brands] == ["2"]


def test_a_parent_is_kept_so_its_child_keeps_its_place() -> None:
    workspace = _workspace(
        [_brand("10", visibility="hidden_parent"), _brand("11", parent="10")],
        [BrandFamilyProjection(root_brand_id="10", brand_ids=("10", "11"))],
    )

    result = brands_with_social_media(
        workspace, reporting_store=FakeReportingStore({"11"}), keep_brand_id="11"
    )

    assert {brand.brand_id for brand in result.brands} == {"10", "11"}
    assert result.families[0].brand_ids == ("10", "11")


def test_an_unavailable_store_changes_nothing() -> None:
    workspace = _workspace([_brand("1"), _brand("2")])

    result = brands_with_social_media(
        workspace, reporting_store=None, keep_brand_id="1"
    )

    assert result is workspace

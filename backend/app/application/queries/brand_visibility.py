"""Which Brands this product actually covers, for anything that lists them."""

from __future__ import annotations

from app.application.ports.reporting import ReportingStore
from app.domain.authority import BrandFamilyProjection, BrandWorkspace


def brands_with_social_media(
    workspace: BrandWorkspace,
    *,
    reporting_store: ReportingStore | None,
    keep_brand_id: str,
) -> BrandWorkspace:
    """Narrow the switcher to the Brands this product actually covers.

    The signed scope lists every Brand the user may open in Accumulate, which is
    far wider than the set Social Media serves: a switcher offering a hundred and
    thirty-five Brands when fifty-three have an account is a list of dead ends.

    A Brand that only carries the hierarchy keeps its place, otherwise a child
    with accounts would lose its parent. The launch Brand is always kept, since
    dropping the one the session resolved to would fail the whole workspace.
    """
    if reporting_store is None:
        return workspace

    scope_ids = tuple(brand.brand_id for brand in workspace.brands)
    if not scope_ids:
        return workspace

    connected = {
        str(account.brand_id)
        for account in reporting_store.list_accounts(brand_ids=scope_ids)
    }
    connected.add(keep_brand_id)
    parents_of_connected = {
        brand.parent_brand_id
        for brand in workspace.brands
        if brand.brand_id in connected and brand.parent_brand_id
    }
    kept = connected | {parent for parent in parents_of_connected if parent}

    brands = tuple(brand for brand in workspace.brands if brand.brand_id in kept)
    if not brands:
        return workspace
    families = tuple(
        BrandFamilyProjection(
            root_brand_id=family.root_brand_id,
            brand_ids=tuple(
                brand_id for brand_id in family.brand_ids if brand_id in kept
            ),
        )
        for family in workspace.families
        if family.root_brand_id in kept
    )
    return BrandWorkspace(
        default_brand_id=workspace.default_brand_id,
        brands=brands,
        families=tuple(family for family in families if family.brand_ids),
        scope=workspace.scope,
    )


__all__ = ["brands_with_social_media"]

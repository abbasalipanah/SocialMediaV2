"""Authorization-safe Brand family and rollup resolution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.application.ports import ProvisioningStore
from app.domain.authority import (
    BrandAccess,
    BrandFamilyProjection,
    BrandScope,
    BrandShell,
    BrandWorkspace,
    WorkspaceBrand,
)


class AuthorityError(ValueError):
    pass


def _shell(payload: Mapping[str, Any]) -> BrandShell:
    return BrandShell(
        brand_id=str(payload.get("brand_id") or ""),
        name=str(payload["name"]).strip() if payload.get("name") else None,
        parent_brand_id=(
            str(payload["parent_brand_id"]) if payload.get("parent_brand_id") else None
        ),
        active=payload.get("active") is True,
        placeholder=payload.get("placeholder") is True,
    )


def _access(payload: Mapping[str, Any]) -> BrandAccess:
    access_mode = payload.get("access_mode")
    if access_mode not in {"read", "write"}:
        raise AuthorityError("invalid_access_projection")
    authority_source = payload.get("authority_source")
    if authority_source not in {"full_snapshot", "membership"}:
        raise AuthorityError("invalid_access_projection")
    return BrandAccess(
        user_id=str(payload.get("user_id") or ""),
        brand_id=str(payload.get("brand_id") or ""),
        role=str(payload.get("role") or ""),
        access_mode=access_mode,
        active=payload.get("active") is True,
        authority_source=authority_source,
    )


def _explicit_projection_allows(store: ProvisioningStore, projection_key: str) -> bool:
    projection = store.get_projection(projection_key)
    return projection is None or projection.get("active") is True


def _load_authority(
    store: ProvisioningStore, user_id: str
) -> tuple[dict[str, BrandShell], dict[str, BrandAccess]]:
    shells = {
        shell.brand_id: shell
        for payload in store.list_projections("v2:brand-shell:")
        if (shell := _shell(payload)).brand_id
    }
    accesses: dict[str, BrandAccess] = {}
    for payload in store.list_projections(f"v2:brand-access:{user_id}:"):
        access = _access(payload)
        shell = shells.get(access.brand_id)
        entitlement = store.get_projection(f"v2:brand-entitlement:{access.brand_id}")
        app_access = store.get_projection(f"v2:brand-app-access:{access.brand_id}")
        if (
            access.user_id != user_id
            or not access.active
            or shell is None
            or not shell.active
            or not _explicit_projection_allows(
                store, f"v2:brand-entitlement:{access.brand_id}"
            )
            or not _explicit_projection_allows(
                store, f"v2:brand-app-access:{access.brand_id}"
            )
            or (
                access.authority_source == "membership"
                and (
                    entitlement is None
                    or entitlement.get("active") is not True
                    or app_access is None
                    or app_access.get("active") is not True
                )
            )
        ):
            continue
        accesses[access.brand_id] = access
    return shells, accesses


def _ancestor_ids(brand_id: str, shells: Mapping[str, BrandShell]) -> tuple[str, ...]:
    ancestors: list[str] = []
    seen = {brand_id}
    current = shells.get(brand_id)
    while current and current.parent_brand_id:
        parent_id = current.parent_brand_id
        if parent_id in seen:
            raise AuthorityError("brand_hierarchy_cycle")
        seen.add(parent_id)
        parent = shells.get(parent_id)
        if parent is None or not parent.active:
            break
        ancestors.append(parent_id)
        current = parent
    return tuple(ancestors)


def _is_descendant(
    candidate_id: str, parent_id: str, shells: Mapping[str, BrandShell]
) -> bool:
    return parent_id in _ancestor_ids(candidate_id, shells)


def build_brand_workspace(
    *,
    store: ProvisioningStore,
    user_id: str,
    selected_brand_id: str,
    rollup: bool,
    require_write: bool = False,
) -> BrandWorkspace:
    shells, accesses = _load_authority(store, user_id)
    visible_ids = set(accesses)
    for brand_id in tuple(accesses):
        visible_ids.update(_ancestor_ids(brand_id, shells))
    if selected_brand_id not in visible_ids:
        raise AuthorityError("brand_access_denied")
    if require_write and rollup:
        raise AuthorityError("rollup_mutation_denied")

    selected_access = accesses.get(selected_brand_id)
    if not rollup:
        if selected_access is None:
            raise AuthorityError("hidden_parent_requires_rollup")
        if require_write and selected_access.access_mode != "write":
            raise AuthorityError("brand_write_denied")
        resolved_ids = (selected_brand_id,)
    else:
        resolved = [
            brand_id
            for brand_id in accesses
            if brand_id == selected_brand_id
            or _is_descendant(brand_id, selected_brand_id, shells)
        ]
        if not resolved:
            raise AuthorityError("brand_access_denied")
        resolved_ids = tuple(sorted(resolved))

    workspace_brands = tuple(
        WorkspaceBrand(
            brand_id=brand_id,
            name=shells[brand_id].name,
            parent_brand_id=shells[brand_id].parent_brand_id,
            visibility="active" if brand_id in accesses else "hidden_parent",
            access_mode=accesses[brand_id].access_mode if brand_id in accesses else None,
            role=accesses[brand_id].role if brand_id in accesses else None,
        )
        for brand_id in sorted(visible_ids)
    )

    families: dict[str, list[str]] = {}
    for brand_id in visible_ids:
        ancestors = _ancestor_ids(brand_id, shells)
        root_id = ancestors[-1] if ancestors else brand_id
        families.setdefault(root_id, []).append(brand_id)
    family_projections = tuple(
        BrandFamilyProjection(root_brand_id=root_id, brand_ids=tuple(sorted(brand_ids)))
        for root_id, brand_ids in sorted(families.items())
    )
    return BrandWorkspace(
        default_brand_id=selected_brand_id,
        brands=workspace_brands,
        families=family_projections,
        scope=BrandScope(
            requested_brand_id=selected_brand_id,
            rollup=rollup,
            resolved_brand_ids=resolved_ids,
        ),
    )


def session_has_current_brand_access(
    *, store: ProvisioningStore, user_id: str, brand_id: str
) -> bool:
    try:
        build_brand_workspace(
            store=store,
            user_id=user_id,
            selected_brand_id=brand_id,
            rollup=False,
        )
    except AuthorityError:
        return False
    return True

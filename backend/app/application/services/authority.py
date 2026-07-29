"""Authorization-safe Brand scope resolution from the signed SSO session."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.domain.authority import (
    BrandFamilyProjection,
    BrandScope,
    BrandWorkspace,
    WorkspaceBrand,
)


class AuthorityError(ValueError):
    pass


def _session_brands(session: Mapping[str, Any]) -> dict[str, WorkspaceBrand]:
    scope = session.get("brand_scope")
    if not isinstance(scope, Mapping) or scope.get("version") != "v1":
        raise AuthorityError("session_brand_scope_invalid")
    raw_brands = scope.get("brands")
    if not isinstance(raw_brands, Sequence) or isinstance(raw_brands, (str, bytes)):
        raise AuthorityError("session_brand_scope_invalid")

    brands: dict[str, WorkspaceBrand] = {}
    for raw in raw_brands:
        if not isinstance(raw, Mapping):
            raise AuthorityError("session_brand_scope_invalid")
        brand_id = str(raw.get("brand_id") or "").strip()
        if not brand_id or brand_id in brands:
            raise AuthorityError("session_brand_scope_invalid")
        parent_value = raw.get("parent_brand_id")
        parent_brand_id = str(parent_value).strip() if parent_value is not None else None
        if parent_brand_id == "":
            parent_brand_id = None
        visibility = raw.get("visibility")
        access_mode = raw.get("access_mode")
        role = raw.get("role")
        if visibility == "active":
            if access_mode not in {"read", "write"} or not isinstance(role, str) or not role:
                raise AuthorityError("session_brand_scope_invalid")
        elif visibility == "hidden_parent":
            if access_mode is not None or role is not None:
                raise AuthorityError("session_brand_scope_invalid")
        else:
            raise AuthorityError("session_brand_scope_invalid")
        name_value = raw.get("name")
        if name_value is not None and not isinstance(name_value, str):
            raise AuthorityError("session_brand_scope_invalid")
        brands[brand_id] = WorkspaceBrand(
            brand_id=brand_id,
            name=name_value.strip() or None if isinstance(name_value, str) else None,
            parent_brand_id=parent_brand_id,
            visibility=visibility,
            access_mode=access_mode,
            role=role,
        )

    if not brands or len(brands) > 500:
        raise AuthorityError("session_brand_scope_invalid")
    for brand in brands.values():
        if brand.parent_brand_id is not None and brand.parent_brand_id not in brands:
            raise AuthorityError("session_brand_scope_invalid")
        _ancestor_ids(brand.brand_id, brands)
    return brands


def _ancestor_ids(
    brand_id: str, brands: Mapping[str, WorkspaceBrand]
) -> tuple[str, ...]:
    ancestors: list[str] = []
    seen = {brand_id}
    current = brands.get(brand_id)
    while current and current.parent_brand_id:
        parent_id = current.parent_brand_id
        if parent_id in seen:
            raise AuthorityError("brand_hierarchy_cycle")
        seen.add(parent_id)
        parent = brands.get(parent_id)
        if parent is None:
            raise AuthorityError("session_brand_scope_invalid")
        ancestors.append(parent_id)
        current = parent
    return tuple(ancestors)


def _is_descendant(
    candidate_id: str, parent_id: str, brands: Mapping[str, WorkspaceBrand]
) -> bool:
    return parent_id in _ancestor_ids(candidate_id, brands)


def build_brand_workspace(
    *,
    session: Mapping[str, Any],
    selected_brand_id: str,
    rollup: bool,
    require_write: bool = False,
) -> BrandWorkspace:
    """Resolve a workspace using only the immutable scope captured at SSO consume."""

    brands = _session_brands(session)
    selected = brands.get(selected_brand_id)
    if selected is None:
        raise AuthorityError("brand_access_denied")
    if require_write and rollup:
        raise AuthorityError("rollup_mutation_denied")

    if not rollup:
        if selected.visibility == "hidden_parent":
            raise AuthorityError("hidden_parent_requires_rollup")
        if require_write and selected.access_mode != "write":
            raise AuthorityError("brand_write_denied")
        resolved_ids = (selected_brand_id,)
    else:
        resolved = [
            brand_id
            for brand_id, brand in brands.items()
            if brand.visibility == "active"
            and (
                brand_id == selected_brand_id
                or _is_descendant(brand_id, selected_brand_id, brands)
            )
        ]
        if not resolved:
            raise AuthorityError("brand_access_denied")
        resolved_ids = tuple(sorted(resolved))

    families: dict[str, list[str]] = {}
    for brand_id in brands:
        ancestors = _ancestor_ids(brand_id, brands)
        root_id = ancestors[-1] if ancestors else brand_id
        families.setdefault(root_id, []).append(brand_id)
    family_projections = tuple(
        BrandFamilyProjection(root_brand_id=root_id, brand_ids=tuple(sorted(brand_ids)))
        for root_id, brand_ids in sorted(families.items())
    )
    return BrandWorkspace(
        default_brand_id=str(session.get("brand_id") or ""),
        brands=tuple(brands[brand_id] for brand_id in sorted(brands)),
        families=family_projections,
        scope=BrandScope(
            requested_brand_id=selected_brand_id,
            rollup=rollup,
            resolved_brand_ids=resolved_ids,
        ),
    )


def session_has_current_brand_access(
    *, session: Mapping[str, Any], brand_id: str
) -> bool:
    try:
        build_brand_workspace(
            session=session,
            selected_brand_id=brand_id,
            rollup=False,
        )
    except AuthorityError:
        return False
    return True


__all__ = [
    "AuthorityError",
    "build_brand_workspace",
    "session_has_current_brand_access",
]

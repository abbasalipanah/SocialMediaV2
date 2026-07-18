from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from app.application.services.authority import (
    AuthorityError,
    build_brand_workspace,
    session_has_current_brand_access,
)


class MemoryProjectionStore:
    def __init__(self, projections: Mapping[str, Mapping[str, Any]]) -> None:
        self.projections = {key: dict(value) for key, value in projections.items()}

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None:
        return self.projections.get(entity_key)

    def list_projections(self, projection_key_prefix: str) -> list[Mapping[str, Any]]:
        return [
            projection
            for key, projection in sorted(self.projections.items())
            if key.startswith(projection_key_prefix)
        ]


def projection_fixture() -> dict[str, dict[str, Any]]:
    return {
        "v2:brand-shell:parent": {
            "active": True,
            "brand_id": "parent",
            "name": "Parent Brand",
            "parent_brand_id": None,
            "placeholder": False,
        },
        "v2:brand-shell:child-a": {
            "active": True,
            "brand_id": "child-a",
            "name": "Child A",
            "parent_brand_id": "parent",
            "placeholder": False,
        },
        "v2:brand-shell:child-b": {
            "active": True,
            "brand_id": "child-b",
            "name": "Child B",
            "parent_brand_id": "parent",
            "placeholder": False,
        },
        "v2:brand-shell:other": {
            "active": True,
            "brand_id": "other",
            "name": "Other Brand",
            "parent_brand_id": None,
            "placeholder": False,
        },
        "v2:brand-access:user-1:child-a": {
            "access_mode": "write",
            "active": True,
            "authority_source": "full_snapshot",
            "brand_id": "child-a",
            "role": "agency_operator",
            "user_id": "user-1",
        },
        "v2:brand-access:user-1:child-b": {
            "access_mode": "read",
            "active": True,
            "authority_source": "full_snapshot",
            "brand_id": "child-b",
            "role": "viewer",
            "user_id": "user-1",
        },
        "v2:brand-access:user-2:other": {
            "access_mode": "write",
            "active": True,
            "authority_source": "full_snapshot",
            "brand_id": "other",
            "role": "agency_admin",
            "user_id": "user-2",
        },
    }


def test_hidden_parent_rollup_contains_only_authorized_active_children() -> None:
    store = MemoryProjectionStore(projection_fixture())
    workspace = build_brand_workspace(
        store=store,
        user_id="user-1",
        selected_brand_id="parent",
        rollup=True,
    )

    assert workspace.scope.resolved_brand_ids == ("child-a", "child-b")
    assert {brand.brand_id for brand in workspace.brands} == {
        "parent",
        "child-a",
        "child-b",
    }
    parent = next(brand for brand in workspace.brands if brand.brand_id == "parent")
    assert parent.visibility == "hidden_parent"
    assert parent.access_mode is None
    assert workspace.families[0].root_brand_id == "parent"


def test_cross_brand_and_hidden_parent_direct_access_are_denied() -> None:
    store = MemoryProjectionStore(projection_fixture())
    with pytest.raises(AuthorityError, match="brand_access_denied"):
        build_brand_workspace(
            store=store,
            user_id="user-1",
            selected_brand_id="other",
            rollup=False,
        )
    with pytest.raises(AuthorityError, match="hidden_parent_requires_rollup"):
        build_brand_workspace(
            store=store,
            user_id="user-1",
            selected_brand_id="parent",
            rollup=False,
        )


def test_mutation_scope_requires_concrete_write_access() -> None:
    store = MemoryProjectionStore(projection_fixture())
    assert build_brand_workspace(
        store=store,
        user_id="user-1",
        selected_brand_id="child-a",
        rollup=False,
        require_write=True,
    ).scope.resolved_brand_ids == ("child-a",)
    with pytest.raises(AuthorityError, match="brand_write_denied"):
        build_brand_workspace(
            store=store,
            user_id="user-1",
            selected_brand_id="child-b",
            rollup=False,
            require_write=True,
        )
    with pytest.raises(AuthorityError, match="rollup_mutation_denied"):
        build_brand_workspace(
            store=store,
            user_id="user-1",
            selected_brand_id="parent",
            rollup=True,
            require_write=True,
        )


def test_explicit_app_access_revoke_invalidates_current_session_scope() -> None:
    projections = projection_fixture()
    projections["v2:brand-app-access:child-a"] = {
        "active": False,
        "brand_id": "child-a",
    }
    store = MemoryProjectionStore(projections)

    assert not session_has_current_brand_access(
        store=store, user_id="user-1", brand_id="child-a"
    )
    workspace = build_brand_workspace(
        store=store,
        user_id="user-1",
        selected_brand_id="parent",
        rollup=True,
    )
    assert workspace.scope.resolved_brand_ids == ("child-b",)


def test_membership_event_cannot_grant_access_without_app_authority() -> None:
    projections = projection_fixture()
    projections["v2:brand-access:user-1:child-a"]["authority_source"] = "membership"
    store = MemoryProjectionStore(projections)
    assert not session_has_current_brand_access(
        store=store, user_id="user-1", brand_id="child-a"
    )

    projections["v2:brand-entitlement:child-a"] = {
        "active": True,
        "brand_id": "child-a",
    }
    projections["v2:brand-app-access:child-a"] = {
        "active": True,
        "brand_id": "child-a",
    }
    store = MemoryProjectionStore(projections)
    assert session_has_current_brand_access(
        store=store, user_id="user-1", brand_id="child-a"
    )


def test_hierarchy_cycle_fails_closed() -> None:
    projections = projection_fixture()
    projections["v2:brand-shell:parent"]["parent_brand_id"] = "child-a"
    store = MemoryProjectionStore(projections)

    with pytest.raises(AuthorityError, match="brand_hierarchy_cycle"):
        build_brand_workspace(
            store=store,
            user_id="user-1",
            selected_brand_id="parent",
            rollup=True,
        )

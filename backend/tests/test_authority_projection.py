from __future__ import annotations

from typing import Any

import pytest

from app.application.services.authority import (
    AuthorityError,
    build_brand_workspace,
    session_has_current_brand_access,
)


def session_fixture() -> dict[str, Any]:
    return {
        "user_id": "user-1",
        "brand_id": "child-a",
        "brand_scope": {
            "version": "v1",
            "default_brand_id": "child-a",
            "brands": [
                {
                    "brand_id": "parent",
                    "name": "Parent Brand",
                    "parent_brand_id": None,
                    "visibility": "hidden_parent",
                    "access_mode": None,
                    "role": None,
                },
                {
                    "brand_id": "child-a",
                    "name": "Child A",
                    "parent_brand_id": "parent",
                    "visibility": "active",
                    "access_mode": "write",
                    "role": "agency_operator",
                },
                {
                    "brand_id": "child-b",
                    "name": "Child B",
                    "parent_brand_id": "parent",
                    "visibility": "active",
                    "access_mode": "read",
                    "role": "viewer",
                },
            ],
        },
    }


def test_hidden_parent_rollup_contains_only_signed_active_children() -> None:
    session = session_fixture()
    workspace = build_brand_workspace(
        session=session,
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
    session = session_fixture()
    with pytest.raises(AuthorityError, match="brand_access_denied"):
        build_brand_workspace(
            session=session,
            selected_brand_id="other",
            rollup=False,
        )
    with pytest.raises(AuthorityError, match="hidden_parent_requires_rollup"):
        build_brand_workspace(
            session=session,
            selected_brand_id="parent",
            rollup=False,
        )


def test_mutation_scope_requires_concrete_write_access() -> None:
    session = session_fixture()
    assert build_brand_workspace(
        session=session,
        selected_brand_id="child-a",
        rollup=False,
        require_write=True,
    ).scope.resolved_brand_ids == ("child-a",)
    with pytest.raises(AuthorityError, match="brand_write_denied"):
        build_brand_workspace(
            session=session,
            selected_brand_id="child-b",
            rollup=False,
            require_write=True,
        )
    with pytest.raises(AuthorityError, match="rollup_mutation_denied"):
        build_brand_workspace(
            session=session,
            selected_brand_id="parent",
            rollup=True,
            require_write=True,
        )


def test_session_scope_is_fail_closed_when_tampered() -> None:
    session = session_fixture()
    session["brand_scope"]["brands"][1]["access_mode"] = "owner"
    assert not session_has_current_brand_access(session=session, brand_id="child-a")


def test_session_scope_rejects_missing_parent_and_cycle() -> None:
    missing_parent = session_fixture()
    missing_parent["brand_scope"]["brands"][1]["parent_brand_id"] = "unknown"
    with pytest.raises(AuthorityError, match="session_brand_scope_invalid"):
        build_brand_workspace(
            session=missing_parent,
            selected_brand_id="child-a",
            rollup=False,
        )

    cycle = session_fixture()
    cycle["brand_scope"]["brands"][0]["parent_brand_id"] = "child-a"
    with pytest.raises(AuthorityError, match="brand_hierarchy_cycle"):
        build_brand_workspace(
            session=cycle,
            selected_brand_id="parent",
            rollup=True,
        )

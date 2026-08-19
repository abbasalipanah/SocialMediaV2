"""Who may set up which Brand's provider connection.

Brand Setup is opened from a row in the Settings table, so an admin sets up
whichever Brand they clicked. Connections used to be allowed only for the Brand
the session was launched with, so every row could only ever configure that one.

Widening this must not widen the other case it protected: Accumulate can
delegate a connection to a viewer for a single Brand, and that delegation is
worth nothing if the viewer can point it at a different Brand.
"""

from __future__ import annotations

from app.application.services.sso import SETTINGS_ROLES, session_can_access_settings


def _session(role: str, app_role: str = "admin") -> dict[str, object]:
    return {
        "role": role,
        "app_role": app_role,
        "brand_id": "101",
        "source_system": "accumulate",
    }


def test_the_two_roles_that_own_settings_are_the_ones_that_widen() -> None:
    assert SETTINGS_ROLES == {"super_admin", "agency_admin"}


def test_an_admin_carries_settings_authority() -> None:
    for role in ("super_admin", "agency_admin"):
        assert session_can_access_settings(_session(role))


def test_a_delegated_viewer_does_not() -> None:
    # This session may connect a provider, but only for the Brand Accumulate
    # delegated it for.
    assert not session_can_access_settings(_session("viewer", app_role="operator"))
    assert not session_can_access_settings(_session("agency_operator"))


def test_the_check_ignores_casing_and_padding() -> None:
    assert session_can_access_settings({"role": " Super_Admin "})


def test_a_session_without_a_role_is_not_an_admin() -> None:
    assert not session_can_access_settings({})
    assert not session_can_access_settings({"role": None})

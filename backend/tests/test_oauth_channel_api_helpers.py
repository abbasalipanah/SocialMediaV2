from __future__ import annotations

from fastapi import HTTPException

from app.api.integrations.callback import oauth_channel_callback_page
from app.api.integrations.context import resolve_oauth_channel_context
from app.core.security import sha256_text
from app.domain.platforms import PlatformId
from tests.test_phase6_dashboard_api import MemoryAuthority


def test_oauth_channel_context_is_bound_to_signed_brand_and_session() -> None:
    authority = MemoryAuthority()

    scope, context = resolve_oauth_channel_context(
        authority_store=authority,
        raw_session=authority.raw_session,
        requested_brand_id="101",
        platform=PlatformId.YOUTUBE,
    )

    assert scope.workspace.scope.resolved_brand_ids == ("101",)
    assert context.brand_id == 101
    assert context.session_binding == sha256_text(authority.raw_session)


def test_oauth_channel_context_keeps_delegated_viewer_on_launch_brand() -> None:
    authority = MemoryAuthority()
    session = authority.sessions[sha256_text(authority.raw_session)]
    session.update(
        {
            "role": "viewer",
            "app_role": "operator",
            "source_system": "accumulate",
        }
    )

    try:
        resolve_oauth_channel_context(
            authority_store=authority,
            raw_session=authority.raw_session,
            requested_brand_id="102",
            platform=PlatformId.YOUTUBE,
        )
    except HTTPException as exc:
        assert exc.status_code == 403
        assert exc.detail == "oauth_channel_brand_forbidden"
    else:
        raise AssertionError("delegated viewer escaped launch Brand")


def test_oauth_callback_page_uses_origin_bound_message_and_no_store() -> None:
    response = oauth_channel_callback_page(
        platform=PlatformId.YOUTUBE,
        brand_id="101",
        connection_id=71,
        discovered_count=2,
    )

    body = response.body.decode()
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert '"type":"social-media:youtube-oauth"' in body
    assert '"discoveredCount":2' in body
    assert "window.location.origin" in body

from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core import load_settings
from app.infrastructure.providers.youtube import (
    YouTubeOAuthError,
    YouTubeOAuthProvider,
    YouTubeOAuthTransport,
    YouTubeOAuthTransportError,
)

SCOPES = (
    "openid",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
)


class Sender:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def __call__(self, method: str, url: str, **kwargs) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def _response(status: int, payload: object | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://provider.example.test")
    if payload is None:
        return httpx.Response(status, request=request)
    return httpx.Response(status, json=payload, request=request)


def _provider(
    responses: list[httpx.Response],
) -> tuple[YouTubeOAuthProvider, Sender]:
    config = replace(
        load_settings().youtube,
        oauth_app_id="oauth-app.apps.googleusercontent.com",
        oauth_app_secret="oauth-app-secret",
        account_enabled=True,
        oauth_mode="manual_intent_only",
    )
    sender = Sender(responses)
    transport = YouTubeOAuthTransport(
        token_url=config.token_url,
        revoke_url=config.revoke_url,
        get_urls=(config.userinfo_url, config.channels_url),
        timeout_seconds=5,
        sender=sender,
    )
    return YouTubeOAuthProvider(config=config, transport=transport), sender


def test_youtube_authorization_requests_exact_offline_read_scopes() -> None:
    provider, _ = _provider([])

    query = parse_qs(
        urlparse(provider.authorization_url(state="signed-state", scopes=SCOPES)).query
    )

    assert query == {
        "access_type": ["offline"],
        "client_id": ["oauth-app.apps.googleusercontent.com"],
        "include_granted_scopes": ["false"],
        "prompt": ["consent"],
        "redirect_uri": [provider.redirect_uri],
        "response_type": ["code"],
        "scope": [" ".join(SCOPES)],
        "state": ["signed-state"],
    }


def test_youtube_exchange_binds_google_subject_and_owned_channels() -> None:
    provider, sender = _provider(
        [
            _response(
                200,
                {
                    "access_token": "access-value",
                    "expires_in": 3600,
                    "refresh_token": "refresh-value",
                    "scope": " ".join(SCOPES),
                    "token_type": "Bearer",
                },
            ),
            _response(200, {"sub": "google-user-1"}),
            _response(
                200,
                {
                    "items": [
                        {
                            "id": "UC-other",
                            "snippet": {"title": "Other Channel"},
                        },
                        {
                            "id": "UC-channel",
                            "snippet": {"title": "Example Channel"},
                        },
                    ]
                },
            ),
        ]
    )

    grant = provider.exchange_and_discover(authorization_code="authorization-code")

    assert grant.provider_subject_id == "google-user-1"
    assert grant.access_token == "access-value"
    assert grant.refresh_token == "refresh-value"
    assert grant.granted_scopes == SCOPES
    assert [(item.external_id, item.display_name) for item in grant.accounts] == [
        ("UC-channel", "Example Channel"),
        ("UC-other", "Other Channel"),
    ]
    assert [call[1] for call in sender.calls] == [
        "https://oauth2.googleapis.com/token",
        "https://openidconnect.googleapis.com/v1/userinfo",
        "https://www.googleapis.com/youtube/v3/channels",
    ]
    assert sender.calls[2][2]["params"] == {
        "part": "id,snippet",
        "mine": "true",
        "maxResults": "50",
    }


def test_youtube_refresh_and_revoke_keep_tokens_out_of_results() -> None:
    provider, sender = _provider(
        [
            _response(
                200,
                {
                    "access_token": "new-access",
                    "expires_in": 3600,
                    "scope": " ".join(SCOPES),
                    "token_type": "Bearer",
                },
            ),
            _response(200),
        ]
    )

    refreshed = provider.refresh(refresh_token="refresh-value")
    provider.revoke(access_token="new-access")

    assert refreshed.access_token == "new-access"
    assert refreshed.refresh_token is None
    assert "new-access" not in repr(refreshed)
    assert sender.calls[0][2]["data"] == {
        "client_id": "oauth-app.apps.googleusercontent.com",
        "client_secret": "oauth-app-secret",
        "grant_type": "refresh_token",
        "refresh_token": "refresh-value",
    }
    assert sender.calls[1][2]["data"] == {"token": "new-access"}


def test_youtube_oauth_rejects_missing_refresh_and_unallowlisted_urls() -> None:
    provider, _ = _provider(
        [
            _response(
                200,
                {
                    "access_token": "access-value",
                    "expires_in": 3600,
                    "scope": " ".join(SCOPES),
                    "token_type": "Bearer",
                },
            )
        ]
    )

    with pytest.raises(YouTubeOAuthError, match="^youtube_token_response_invalid$"):
        provider.exchange_and_discover(authorization_code="authorization-code")

    transport = YouTubeOAuthTransport(
        token_url="https://oauth2.googleapis.com/token",
        revoke_url="https://oauth2.googleapis.com/revoke",
        get_urls=("https://openidconnect.googleapis.com/v1/userinfo",),
        timeout_seconds=5,
        sender=Sender([]),
    )
    with pytest.raises(YouTubeOAuthTransportError, match="^oauth_url_rejected$"):
        transport.get(
            "https://attacker.example.test/token",
            access_token="access-value",
            params={},
        )

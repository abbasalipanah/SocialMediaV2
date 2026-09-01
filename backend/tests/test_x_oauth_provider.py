from __future__ import annotations

import base64
import hashlib
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core import load_settings
from app.infrastructure.providers.x import (
    XOAuthError,
    XOAuthProvider,
    XOAuthTransport,
    XOAuthTransportError,
)

SCOPES = ("tweet.read", "users.read", "offline.access")


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
) -> tuple[XOAuthProvider, Sender]:
    config = replace(
        load_settings().x,
        oauth_client_id="x-client-id",
        oauth_client_secret="x-client-secret",
        account_enabled=True,
        oauth_mode="manual_intent_only",
    )
    sender = Sender(responses)
    transport = XOAuthTransport(
        client_id=config.oauth_client_id,
        client_secret=config.oauth_client_secret,
        token_url=config.token_url,
        revoke_url=config.revoke_url,
        get_urls=(config.users_me_url,),
        timeout_seconds=5,
        sender=sender,
    )
    return (
        XOAuthProvider(config=config, transport=transport, pkce_secret=b"p" * 32),
        sender,
    )


def test_x_authorization_and_exchange_use_the_same_s256_pkce_binding() -> None:
    provider, sender = _provider(
        [
            _response(
                200,
                {
                    "access_token": "access-value",
                    "expires_in": 7200,
                    "refresh_token": "refresh-value",
                    "scope": " ".join(SCOPES),
                    "token_type": "bearer",
                },
            ),
            _response(
                200,
                {"data": {"id": "123456789", "name": "Example", "username": "example"}},
            ),
        ]
    )

    query = parse_qs(
        urlparse(provider.authorization_url(state="signed-state", scopes=SCOPES)).query
    )
    grant = provider.exchange_and_discover(
        authorization_code="authorization-code",
        authorization_state="signed-state",
    )

    verifier = sender.calls[0][2]["data"]["code_verifier"]
    expected_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode("ascii").rstrip("=")
    assert query == {
        "client_id": ["x-client-id"],
        "code_challenge": [expected_challenge],
        "code_challenge_method": ["S256"],
        "redirect_uri": [provider.redirect_uri],
        "response_type": ["code"],
        "scope": [" ".join(SCOPES)],
        "state": ["signed-state"],
    }
    assert sender.calls[0][2]["auth"] == ("x-client-id", "x-client-secret")
    assert grant.provider_subject_id == "123456789"
    assert grant.refresh_token == "refresh-value"
    assert [(account.external_id, account.display_name) for account in grant.accounts] == [
        ("123456789", "Example (@example)")
    ]


def test_x_refresh_supports_rotating_refresh_tokens_and_revoke() -> None:
    provider, sender = _provider(
        [
            _response(
                200,
                {
                    "access_token": "new-access",
                    "expires_in": 7200,
                    "refresh_token": "new-refresh",
                    "scope": " ".join(SCOPES),
                    "token_type": "Bearer",
                },
            ),
            _response(200),
        ]
    )

    refreshed = provider.refresh(refresh_token="old-refresh")
    provider.revoke(access_token="new-access")

    assert refreshed.refresh_token == "new-refresh"
    assert "new-access" not in repr(refreshed)
    assert sender.calls[0][2]["data"] == {
        "grant_type": "refresh_token",
        "refresh_token": "old-refresh",
    }
    assert sender.calls[1][2]["data"] == {"token": "new-access"}


def test_x_oauth_rejects_missing_refresh_and_unallowlisted_urls() -> None:
    provider, _ = _provider(
        [
            _response(
                200,
                {
                    "access_token": "access-value",
                    "expires_in": 7200,
                    "scope": " ".join(SCOPES),
                    "token_type": "bearer",
                },
            )
        ]
    )
    with pytest.raises(XOAuthError, match="^x_token_response_invalid$"):
        provider.exchange_and_discover(
            authorization_code="authorization-code",
            authorization_state="signed-state",
        )

    config = replace(
        load_settings().x,
        oauth_client_id="x-client-id",
        oauth_client_secret="x-client-secret",
    )
    transport = XOAuthTransport(
        client_id=config.oauth_client_id,
        client_secret=config.oauth_client_secret,
        token_url=config.token_url,
        revoke_url=config.revoke_url,
        get_urls=(config.users_me_url,),
        timeout_seconds=5,
        sender=Sender([]),
    )
    with pytest.raises(XOAuthTransportError, match="^x_oauth_url_rejected$"):
        transport.get(
            "https://attacker.example.test/token",
            access_token="access-value",
            params={},
        )

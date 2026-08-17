from __future__ import annotations

import json

import httpx
import pytest

from app.infrastructure.providers.tiktok.accounts import (
    TikTokHttpTransport,
    TikTokTransportError,
)

TOKEN_URL = "https://business-api.tiktok.com/token"
INFO_URL = "https://business-api.tiktok.com/info"


def test_tiktok_transport_posts_json_and_parses_allowlisted_json() -> None:
    """Business API v1.3 rejects form-encoded bodies on every tt_user endpoint.

    A form POST is answered with `40002 header Content-Type has unexpected
    value`, so the body must be JSON for token, refresh, revoke and token_info
    alike.
    """
    observed: list[tuple[str, str, str]] = []
    bodies: list[bytes] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(
            (
                request.method,
                str(request.url),
                request.headers.get("content-type", ""),
            )
        )
        bodies.append(request.content)
        return httpx.Response(
            200,
            json={"code": 0, "message": "OK", "request_id": "request", "data": {}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = TikTokHttpTransport(
        post_urls=(TOKEN_URL,),
        get_urls=(INFO_URL,),
        timeout_seconds=5,
        sender=client.request,
        sleeper=lambda _: None,
    )

    payload = transport.post(TOKEN_URL, data={"auth_code": "opaque"})

    assert payload["code"] == 0
    assert observed == [
        ("POST", TOKEN_URL, "application/json"),
    ]
    assert json.loads(bodies[0]) == {"auth_code": "opaque"}


def test_tiktok_transport_rejects_unknown_urls_and_sanitizes_provider_failures() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500, text="secret-body"))
    )
    transport = TikTokHttpTransport(
        post_urls=(TOKEN_URL,),
        get_urls=(INFO_URL,),
        timeout_seconds=5,
        sender=client.request,
        sleeper=lambda _: None,
    )

    with pytest.raises(TikTokTransportError, match="^provider_url_rejected$"):
        transport.get("https://example.test/redirect", headers={})
    with pytest.raises(TikTokTransportError, match="^provider_http_rejected$") as raised:
        transport.post(TOKEN_URL, data={"client_secret": "must-not-escape"})
    assert "secret-body" not in str(raised.value)
    assert "must-not-escape" not in str(raised.value)


def test_tiktok_transport_retries_with_retry_after_and_enforces_budget() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0.25"})
        return httpx.Response(
            200,
            json={"code": 0, "message": "OK", "request_id": "request", "data": {}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = TikTokHttpTransport(
        post_urls=(TOKEN_URL,),
        get_urls=(INFO_URL,),
        timeout_seconds=5,
        sender=client.request,
        max_retries=1,
        request_budget=2,
        sleeper=delays.append,
    )

    assert transport.get(INFO_URL, headers={})["code"] == 0
    assert attempts == 2
    assert delays == [0.25]
    assert transport.remaining_requests == 0
    with pytest.raises(TikTokTransportError, match="^provider_request_budget_exhausted$"):
        transport.get(INFO_URL, headers={})


def test_transport_allows_a_post_only_allowlist_but_still_needs_one_url() -> None:
    """The token-inspection path declares no GET URL.

    `tt_user/token_info/get/` answers POST only, so requiring a non-empty GET
    allowlist would force callers to declare a URL they must never call.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={"code": 0, "message": "OK", "request_id": "request", "data": {}},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = TikTokHttpTransport(
        post_urls=(INFO_URL,),
        get_urls=(),
        timeout_seconds=5,
        sender=client.request,
        sleeper=lambda _: None,
    )

    assert transport.post(INFO_URL, data={"access_token": "opaque"})["code"] == 0
    with pytest.raises(TikTokTransportError, match="^provider_url_rejected$"):
        transport.get(INFO_URL, headers={})

    with pytest.raises(TikTokTransportError, match="^provider_transport_config_invalid$"):
        TikTokHttpTransport(post_urls=(), get_urls=(), timeout_seconds=5)

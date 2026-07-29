from __future__ import annotations

import httpx
import pytest

from app.infrastructure.providers.tiktok.accounts import (
    TikTokHttpTransport,
    TikTokTransportError,
)

TOKEN_URL = "https://business-api.tiktok.com/token"
INFO_URL = "https://business-api.tiktok.com/info"


def test_tiktok_transport_posts_form_and_parses_allowlisted_json() -> None:
    observed: list[tuple[str, str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(
            (
                request.method,
                str(request.url),
                request.headers.get("content-type", ""),
            )
        )
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
    )

    payload = transport.post(TOKEN_URL, data={"auth_code": "opaque"})

    assert payload["code"] == 0
    assert observed == [
        ("POST", TOKEN_URL, "application/x-www-form-urlencoded"),
    ]


def test_tiktok_transport_rejects_unknown_urls_and_sanitizes_provider_failures() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(500, text="secret-body"))
    )
    transport = TikTokHttpTransport(
        post_urls=(TOKEN_URL,),
        get_urls=(INFO_URL,),
        timeout_seconds=5,
        sender=client.request,
    )

    with pytest.raises(TikTokTransportError, match="^provider_url_rejected$"):
        transport.get("https://example.test/redirect", headers={})
    with pytest.raises(TikTokTransportError, match="^provider_http_rejected$") as raised:
        transport.post(TOKEN_URL, data={"client_secret": "must-not-escape"})
    assert "secret-body" not in str(raised.value)
    assert "must-not-escape" not in str(raised.value)

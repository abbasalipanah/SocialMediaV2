from __future__ import annotations

import httpx
import pytest

from app.infrastructure.providers.youtube import (
    YouTubeHttpTransport,
    YouTubeTransportError,
)

CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
REPORTS_URL = "https://youtubeanalytics.googleapis.com/v2/reports"


def test_youtube_transport_sends_bearer_token_and_query_to_allowlisted_url() -> None:
    observed: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request)
        return httpx.Response(200, json={"items": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = YouTubeHttpTransport(
        get_urls=(CHANNELS_URL,),
        timeout_seconds=5,
        sender=client.request,
        sleeper=lambda _: None,
    )

    assert transport.get(
        CHANNELS_URL,
        access_token="opaque-token",
        params={"part": "snippet,statistics", "mine": "true"},
    ) == {"items": []}
    assert len(observed) == 1
    assert observed[0].method == "GET"
    assert observed[0].headers["authorization"] == "Bearer opaque-token"
    assert observed[0].url.params["part"] == "snippet,statistics"
    assert observed[0].url.params["mine"] == "true"


def test_youtube_transport_rejects_unknown_url_and_sanitizes_failures() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(403, text="provider-secret-body")
        )
    )
    transport = YouTubeHttpTransport(
        get_urls=(CHANNELS_URL,),
        timeout_seconds=5,
        sender=client.request,
        sleeper=lambda _: None,
    )

    with pytest.raises(YouTubeTransportError, match="^provider_url_rejected$"):
        transport.get(
            "https://example.test/redirect",
            access_token="must-not-escape",
            params={},
        )
    with pytest.raises(YouTubeTransportError, match="^provider_http_rejected$") as raised:
        transport.get(
            CHANNELS_URL,
            access_token="must-not-escape",
            params={},
        )
    assert "provider-secret-body" not in str(raised.value)
    assert "must-not-escape" not in str(raised.value)


def test_youtube_transport_retries_retryable_status_and_enforces_budget() -> None:
    attempts = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "0.25"})
        return httpx.Response(200, json={"rows": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    transport = YouTubeHttpTransport(
        get_urls=(REPORTS_URL,),
        timeout_seconds=5,
        sender=client.request,
        max_retries=1,
        request_budget=2,
        sleeper=delays.append,
    )

    assert transport.get(REPORTS_URL, access_token="opaque", params={}) == {"rows": []}
    assert attempts == 2
    assert delays == [0.25]
    assert transport.remaining_requests == 0
    with pytest.raises(YouTubeTransportError, match="^provider_request_budget_exhausted$"):
        transport.get(REPORTS_URL, access_token="opaque", params={})


@pytest.mark.parametrize(
    "kwargs",
    (
        {"get_urls": (), "timeout_seconds": 5},
        {"get_urls": (CHANNELS_URL,), "timeout_seconds": 0},
        {"get_urls": (CHANNELS_URL,), "timeout_seconds": 5, "request_budget": 0},
    ),
)
def test_youtube_transport_rejects_invalid_configuration(kwargs: dict[str, object]) -> None:
    with pytest.raises(YouTubeTransportError, match="^provider_transport_config_invalid$"):
        YouTubeHttpTransport(**kwargs)  # type: ignore[arg-type]


def test_youtube_transport_rejects_blank_access_token() -> None:
    transport = YouTubeHttpTransport(get_urls=(CHANNELS_URL,), timeout_seconds=5)

    with pytest.raises(YouTubeTransportError, match="^provider_access_token_invalid$"):
        transport.get(CHANNELS_URL, access_token="   ", params={})

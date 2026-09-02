from __future__ import annotations

import httpx
import pytest

from app.infrastructure.providers.linkedin import (
    LinkedInHttpTransport,
    LinkedInTransportError,
)


def test_linkedin_transport_sends_versioned_read_only_finder() -> None:
    calls = []

    def sender(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return httpx.Response(200, json={"elements": []})

    transport = LinkedInHttpTransport(
        get_urls=("https://api.linkedin.com/rest/posts",),
        api_version="202608",
        timeout_seconds=3,
        sender=sender,
        max_retries=0,
    )

    assert transport.get(
        "https://api.linkedin.com/rest/posts",
        access_token="access-secret",
        params={"q": "author"},
        finder=True,
    ) == {"elements": []}
    method, _url, kwargs = calls[0]
    assert method == "GET"
    assert kwargs["headers"] == {
        "Authorization": "Bearer access-secret",
        "Linkedin-Version": "202608",
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
        "X-RestLi-Method": "FINDER",
    }
    assert kwargs["follow_redirects"] is False


def test_linkedin_transport_rejects_urls_outside_the_allowlist() -> None:
    transport = LinkedInHttpTransport(
        get_urls=("https://api.linkedin.com/rest/posts",),
        api_version="202608",
        timeout_seconds=3,
        sender=lambda *_args, **_kwargs: pytest.fail("request must not be sent"),
    )

    with pytest.raises(LinkedInTransportError, match="linkedin_provider_url_rejected"):
        transport.get(
            "https://attacker.invalid/posts",
            access_token="access-secret",
            params={},
        )

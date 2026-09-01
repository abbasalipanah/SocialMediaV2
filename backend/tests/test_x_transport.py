from __future__ import annotations

import httpx
import pytest

from app.infrastructure.providers.x import XHttpTransport, XTransportError


class Sender:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def __call__(self, method: str, url: str, **kwargs) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def _response(status: int, payload: object) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", "https://api.x.com/2/users/me"),
    )


def test_x_transport_retries_rate_limit_and_keeps_bearer_out_of_url() -> None:
    sender = Sender([_response(429, {}), _response(200, {"data": {"id": "1"}})])
    delays: list[float] = []
    transport = XHttpTransport(
        get_urls=("https://api.x.com/2/users/me",),
        timeout_seconds=5,
        sender=sender,
        max_retries=1,
        sleeper=delays.append,
    )

    payload = transport.get(
        "https://api.x.com/2/users/me",
        access_token="access-value",
        params={"user.fields": "name"},
    )

    assert payload == {"data": {"id": "1"}}
    assert delays == [1.0]
    assert all("access-value" not in url for _method, url, _kwargs in sender.calls)
    assert sender.calls[0][2]["headers"] == {"Authorization": "Bearer access-value"}


def test_x_transport_rejects_unallowlisted_url_without_sending() -> None:
    sender = Sender([])
    transport = XHttpTransport(
        get_urls=("https://api.x.com/2/users/me",),
        timeout_seconds=5,
        sender=sender,
    )
    with pytest.raises(XTransportError, match="^x_provider_url_rejected$"):
        transport.get(
            "https://attacker.example.test",
            access_token="access-value",
            params={},
        )
    assert sender.calls == []

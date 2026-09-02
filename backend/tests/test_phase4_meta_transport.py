from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest

from app.application.ports.platforms import ProviderCredential
from app.infrastructure.providers.meta import (
    MetaRateGuard,
    MetaRateLimited,
    MetaTransport,
    MetaTransportError,
)

NOW = datetime(2026, 7, 14, 12, tzinfo=UTC)


def guard(sleeps: list[float] | None = None) -> MetaRateGuard:
    return MetaRateGuard(clock=lambda: NOW, sleeper=(sleeps if sleeps is not None else []).append)


def test_meta_egress_is_default_off_and_secret_parameters_are_rejected() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"id": "page-1"}, request=request)

    blocked = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=guard(),
        wire=httpx.MockTransport(handler),
    )
    with pytest.raises(MetaTransportError, match="meta_egress_disabled"):
        blocked.get("me")
    assert calls == []

    enabled = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=guard(),
        wire=httpx.MockTransport(handler),
        egress_enabled=True,
    )
    with pytest.raises(MetaTransportError, match="meta_secret_parameter_forbidden"):
        enabled.get("me", {"access_token": "must-not-pass"})
    with pytest.raises(MetaTransportError, match="meta_path_invalid"):
        enabled.get("https://example.test/escape")
    assert calls == []


def test_meta_request_uses_canonical_host_version_and_authorization_header() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "page-1"}, request=request)

    transport = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=guard(),
        wire=httpx.MockTransport(handler),
        egress_enabled=True,
    )
    assert transport.get("me", {"fields": "id,name"}) == {"id": "page-1"}
    request = requests[0]
    assert str(request.url) == "https://graph.facebook.com/v26.0/me?fields=id%2Cname"
    assert request.headers["authorization"] == "Bearer disposable-access-value"
    assert "disposable-access-value" not in str(request.url)


def test_meta_retries_transient_responses_with_bounded_backoff() -> None:
    attempts = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"error": {"message": "temporary"}}, request=request)
        if attempts == 2:
            return httpx.Response(
                429,
                headers={"retry-after": "2"},
                json={"error": {"message": "slow"}},
                request=request,
            )
        return httpx.Response(200, json={"data": []}, request=request)

    transport = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=guard(),
        wire=httpx.MockTransport(handler),
        egress_enabled=True,
        max_retries=2,
        base_backoff_seconds=0.5,
        sleeper=sleeps.append,
        jitter=lambda _start, _end: 0.0,
    )
    assert transport.get("page-1/posts") == {"data": []}
    assert attempts == 3
    assert sleeps == [0.5, 2.0]


def test_meta_usage_pressure_throttles_degrades_and_opens_cooldown() -> None:
    rate_sleeps: list[float] = []
    rate_guard = guard(rate_sleeps)

    def response_with_pressure(pressure: int) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={
                    "x-app-usage": json.dumps(
                        {"call_count": pressure, "total_cputime": 1, "total_time": 1}
                    )
                },
                json={"id": "page-1"},
                request=request,
            )

        return httpx.MockTransport(handler)

    throttled = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=rate_guard,
        wire=response_with_pressure(75),
        egress_enabled=True,
    )
    assert throttled.get("me") == {"id": "page-1"}
    assert rate_sleeps == [pytest.approx(0.4)]

    degraded = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=rate_guard,
        wire=response_with_pressure(86),
        egress_enabled=True,
    )
    assert degraded.get("me") == {"id": "page-1"}
    assert rate_guard.background_available() is False

    cooldown = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=rate_guard,
        wire=response_with_pressure(93),
        egress_enabled=True,
    )
    with pytest.raises(MetaRateLimited, match="pressure_cooldown") as raised:
        cooldown.get("me")
    assert raised.value.wait_seconds == 120
    with pytest.raises(MetaRateLimited, match="cooldown_active"):
        cooldown.get("me")


def test_meta_limit_error_opens_fail_closed_preflight_without_echoing_payload() -> None:
    calls = 0
    rate_guard = guard()

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": 4,
                    "message": "disposable-provider-message",
                    "retry_after_seconds": 300,
                }
            },
            request=request,
        )

    transport = MetaTransport(
        credential=ProviderCredential("disposable-access-value"),
        rate_guard=rate_guard,
        wire=httpx.MockTransport(handler),
        egress_enabled=True,
    )
    with pytest.raises(MetaTransportError, match="meta_provider_rejected") as raised:
        transport.get("me")
    assert "disposable-provider-message" not in str(raised.value)
    with pytest.raises(MetaRateLimited, match="cooldown_active"):
        transport.get("me")
    assert calls == 1

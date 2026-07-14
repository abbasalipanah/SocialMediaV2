"""Fail-closed Meta Graph HTTP transport with bounded retries."""

from __future__ import annotations

import random
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

import httpx

from app.application.ports.platforms import ProviderCredential

from .rate_guard import MetaRateGuard

META_GRAPH_BASE_URL = "https://graph.facebook.com"


class MetaTransportError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class MetaTransport:
    def __init__(
        self,
        *,
        credential: ProviderCredential,
        rate_guard: MetaRateGuard,
        wire: httpx.BaseTransport | None = None,
        base_url: str = META_GRAPH_BASE_URL,
        api_version: str = "v23.0",
        timeout_seconds: float = 30.0,
        max_retries: int = 5,
        base_backoff_seconds: float = 0.6,
        egress_enabled: bool = False,
        sleeper: Callable[[float], None] = time.sleep,
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        parsed = urlparse(base_url)
        valid_origin = (
            parsed.scheme == "https"
            and parsed.hostname == "graph.facebook.com"
            and parsed.path in {"", "/"}
        )
        if not valid_origin:
            raise MetaTransportError("meta_base_url_invalid")
        if not api_version.startswith("v") or not api_version[1:].replace(".", "").isdigit():
            raise MetaTransportError("meta_api_version_invalid")
        if not 0 <= max_retries <= 8 or timeout_seconds <= 0 or base_backoff_seconds < 0:
            raise MetaTransportError("meta_retry_contract_invalid")
        self._credential = credential
        self._rate_guard = rate_guard
        self._wire = wire or httpx.HTTPTransport(retries=0)
        self._base_url = base_url.rstrip("/")
        self._api_version = api_version
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._base_backoff_seconds = base_backoff_seconds
        self._egress_enabled = egress_enabled
        self._sleeper = sleeper
        self._jitter = jitter

    def get(
        self,
        path: str,
        params: Mapping[str, str | int | float] | None = None,
    ) -> Mapping[str, Any]:
        if not self._egress_enabled:
            raise MetaTransportError("meta_egress_disabled")
        url = self._url(path)
        request_params = dict(params or {})
        if any(key.lower() in {"access_token", "appsecret_proof"} for key in request_params):
            raise MetaTransportError("meta_secret_parameter_forbidden")
        last_error: MetaTransportError | None = None
        for attempt in range(self._max_retries + 1):
            self._rate_guard.preflight()
            request = httpx.Request(
                "GET",
                url,
                params=request_params,
                headers={
                    "Authorization": f"Bearer {self._credential.access_token}",
                    "Accept": "application/json",
                },
                extensions={
                    "timeout": {
                        "connect": self._timeout_seconds,
                        "read": self._timeout_seconds,
                        "write": self._timeout_seconds,
                        "pool": self._timeout_seconds,
                    }
                },
            )
            try:
                response = self._wire.handle_request(request)
                response.read()
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = MetaTransportError("meta_transport_failure", retryable=True)
                if attempt >= self._max_retries:
                    raise last_error from exc
                self._sleep(attempt, None)
                continue
            self._rate_guard.observe_headers(response.headers)
            payload = _json_object(response)
            if response.status_code == 429 or response.status_code >= 500:
                self._rate_guard.observe_limit_error(payload)
                last_error = MetaTransportError(
                    "meta_transient_response",
                    status_code=response.status_code,
                    retryable=True,
                )
                if attempt >= self._max_retries:
                    raise last_error
                self._sleep(attempt, _retry_after(response, payload))
                continue
            if response.status_code >= 400:
                self._rate_guard.observe_limit_error(payload)
                raise MetaTransportError(
                    "meta_provider_rejected",
                    status_code=response.status_code,
                )
            if "error" in payload:
                limited = self._rate_guard.observe_limit_error(payload)
                raise MetaTransportError(
                    "meta_limit_response" if limited else "meta_error_payload",
                    status_code=response.status_code,
                    retryable=limited,
                )
            return payload
        raise last_error or MetaTransportError("meta_transport_failure")

    def close(self) -> None:
        self._wire.close()

    def _url(self, path: str) -> str:
        if not path or path.startswith(("http://", "https://", "//")) or ".." in path.split("/"):
            raise MetaTransportError("meta_path_invalid")
        return f"{self._base_url}/{self._api_version}/{path.lstrip('/')}"

    def _sleep(self, attempt: int, retry_after: float | None) -> None:
        base = self._base_backoff_seconds * (2**attempt)
        delay = base + self._jitter(0.0, base * 0.2)
        self._sleeper(max(delay, retry_after or 0.0))


def _json_object(response: httpx.Response) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise MetaTransportError(
            "meta_response_not_json",
            status_code=response.status_code,
        ) from exc
    if not isinstance(payload, Mapping):
        raise MetaTransportError(
            "meta_response_shape_invalid",
            status_code=response.status_code,
        )
    return payload


def _retry_after(response: httpx.Response, payload: Mapping[str, Any]) -> float | None:
    values: list[object] = [response.headers.get("retry-after")]
    error = payload.get("error")
    if isinstance(error, Mapping):
        values.extend((error.get("retry_after"), error.get("retry_after_seconds")))
    parsed: list[float] = []
    for value in values:
        try:
            if value is not None:
                parsed.append(max(0.0, float(value)))
        except (TypeError, ValueError):
            continue
    return max(parsed) if parsed else None


__all__ = ["META_GRAPH_BASE_URL", "MetaTransport", "MetaTransportError"]

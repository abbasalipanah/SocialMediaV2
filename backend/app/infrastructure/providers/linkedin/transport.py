"""Allowlisted, bounded, read-only LinkedIn Community Management transport."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

MAX_LINKEDIN_RESPONSE_BYTES = 4_000_000
MAX_RETRY_DELAY_SECONDS = 60.0
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class LinkedInTransportError(RuntimeError):
    """Sanitized provider failure without credentials or response bodies."""


class LinkedInHttpTransport:
    def __init__(
        self,
        *,
        get_urls: tuple[str, ...],
        api_version: str,
        timeout_seconds: float,
        sender: Callable[..., httpx.Response] | None = None,
        max_retries: int = 3,
        request_budget: int = 100,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if (
            not get_urls
            or len(api_version) != 6
            or not api_version.isdigit()
            or timeout_seconds <= 0
            or max_retries < 0
            or max_retries > 10
            or request_budget < 1
            or request_budget > 500
        ):
            raise LinkedInTransportError("linkedin_transport_config_invalid")
        self._get_urls = frozenset(get_urls)
        self._api_version = api_version
        self._timeout = httpx.Timeout(timeout_seconds)
        self._sender = sender or httpx.request
        self._max_retries = max_retries
        self._remaining_requests = request_budget
        self._sleeper = sleeper

    @property
    def remaining_requests(self) -> int:
        return self._remaining_requests

    def get(
        self,
        url: str,
        *,
        access_token: str,
        params: Mapping[str, str],
        finder: bool = False,
    ) -> Mapping[str, object]:
        if url not in self._get_urls:
            raise LinkedInTransportError("linkedin_provider_url_rejected")
        if not access_token.strip():
            raise LinkedInTransportError("linkedin_provider_access_token_invalid")
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Linkedin-Version": self._api_version,
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json",
        }
        if finder:
            headers["X-RestLi-Method"] = "FINDER"
        return self._request(url, headers=headers, params=dict(params))

    def _request(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, str],
    ) -> Mapping[str, object]:
        attempt = 0
        while True:
            if self._remaining_requests < 1:
                raise LinkedInTransportError("linkedin_provider_request_budget_exhausted")
            self._remaining_requests -= 1
            try:
                response = self._sender(
                    "GET",
                    url,
                    headers=headers,
                    params=params,
                    timeout=self._timeout,
                    follow_redirects=False,
                )
            except httpx.HTTPError as exc:
                if attempt >= self._max_retries:
                    raise LinkedInTransportError("linkedin_provider_transport_failed") from exc
                self._sleeper(_retry_delay(None, attempt))
                attempt += 1
                continue
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                self._sleeper(_retry_delay(response, attempt))
                attempt += 1
                continue
            return self._payload(response)

    @staticmethod
    def _payload(response: httpx.Response) -> Mapping[str, object]:
        if response.status_code < 200 or response.status_code >= 300:
            raise LinkedInTransportError("linkedin_provider_http_rejected")
        if len(response.content) > MAX_LINKEDIN_RESPONSE_BYTES:
            raise LinkedInTransportError("linkedin_provider_response_too_large")
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise LinkedInTransportError("linkedin_provider_response_invalid") from exc
        if not isinstance(payload, Mapping):
            raise LinkedInTransportError("linkedin_provider_response_invalid")
        return payload


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    retry_after = response.headers.get("retry-after") if response is not None else None
    if retry_after:
        try:
            return min(MAX_RETRY_DELAY_SECONDS, max(0.0, float(retry_after)))
        except ValueError:
            pass
    return min(MAX_RETRY_DELAY_SECONDS, float(2**attempt))


__all__ = ["LinkedInHttpTransport", "LinkedInTransportError"]

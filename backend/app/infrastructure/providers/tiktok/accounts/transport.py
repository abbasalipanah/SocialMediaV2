"""Allowlisted TikTok provider transport with sanitized failures."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx

MAX_RESPONSE_BYTES = 1_000_000


class TikTokTransportError(RuntimeError):
    """Provider transport failure that never includes response bodies or credentials."""


class TikTokHttpTransport:
    def __init__(
        self,
        *,
        post_urls: tuple[str, ...],
        get_urls: tuple[str, ...],
        timeout_seconds: float,
        sender: Callable[..., httpx.Response] | None = None,
    ) -> None:
        if not post_urls or not get_urls or timeout_seconds <= 0:
            raise TikTokTransportError("provider_transport_config_invalid")
        self._post_urls = frozenset(post_urls)
        self._get_urls = frozenset(get_urls)
        self._timeout = httpx.Timeout(timeout_seconds)
        self._sender = sender or httpx.request

    def post(self, url: str, *, data: Mapping[str, str]) -> Mapping[str, object]:
        if url not in self._post_urls:
            raise TikTokTransportError("provider_url_rejected")
        try:
            response = self._sender(
                "POST",
                url,
                data=data,
                timeout=self._timeout,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise TikTokTransportError("provider_transport_failed") from exc
        return self._payload(response)

    def get(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        params: Mapping[str, str] | None = None,
    ) -> Mapping[str, object]:
        if url not in self._get_urls:
            raise TikTokTransportError("provider_url_rejected")
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
            raise TikTokTransportError("provider_transport_failed") from exc
        return self._payload(response)

    @staticmethod
    def _payload(response: httpx.Response) -> Mapping[str, object]:
        if response.status_code < 200 or response.status_code >= 300:
            raise TikTokTransportError("provider_http_rejected")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise TikTokTransportError("provider_response_too_large")
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise TikTokTransportError("provider_response_invalid") from exc
        if not isinstance(payload, Mapping):
            raise TikTokTransportError("provider_response_invalid")
        return payload


__all__ = ["TikTokHttpTransport", "TikTokTransportError"]

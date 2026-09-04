"""Allowlisted transport for X OAuth and authenticated-user discovery."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import httpx

MAX_OAUTH_RESPONSE_BYTES = 1_000_000


class XOAuthTransportError(RuntimeError):
    """Sanitized provider failure without tokens or response bodies."""


class XOAuthTransport:
    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        token_url: str,
        revoke_url: str,
        get_urls: tuple[str, ...],
        timeout_seconds: float,
        sender: Callable[..., httpx.Response] | None = None,
        request_budget: int = 20,
    ) -> None:
        if (
            not app_id
            or not app_secret
            or not token_url
            or not revoke_url
            or not get_urls
            or timeout_seconds <= 0
            or request_budget < 1
            or request_budget > 100
        ):
            raise XOAuthTransportError("x_oauth_transport_config_invalid")
        self._app_auth = (app_id, app_secret)
        self._token_url = token_url
        self._revoke_url = revoke_url
        self._get_urls = frozenset(get_urls)
        self._timeout = httpx.Timeout(timeout_seconds)
        self._sender = sender or httpx.request
        self._remaining_requests = request_budget

    def exchange(self, data: Mapping[str, str]) -> Mapping[str, object]:
        return self._json_request(
            "POST", self._token_url, auth=self._app_auth, data=_form(data)
        )

    def refresh(self, data: Mapping[str, str]) -> Mapping[str, object]:
        return self._json_request(
            "POST", self._token_url, auth=self._app_auth, data=_form(data)
        )

    def revoke(self, *, token: str) -> None:
        if not token:
            raise XOAuthTransportError("x_oauth_token_invalid")
        response = self._request(
            "POST",
            self._revoke_url,
            auth=self._app_auth,
            data={"token": token},
        )
        self._accept(response)

    def get(
        self,
        url: str,
        *,
        access_token: str,
        params: Mapping[str, str],
    ) -> Mapping[str, object]:
        if url not in self._get_urls:
            raise XOAuthTransportError("x_oauth_url_rejected")
        if not access_token:
            raise XOAuthTransportError("x_oauth_token_invalid")
        return self._json_request(
            "GET",
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            params=dict(params),
        )

    def _json_request(self, method: str, url: str, **kwargs) -> Mapping[str, object]:
        response = self._request(method, url, **kwargs)
        self._accept(response)
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise XOAuthTransportError("x_oauth_response_invalid") from exc
        if not isinstance(payload, Mapping):
            raise XOAuthTransportError("x_oauth_response_invalid")
        return payload

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self._remaining_requests < 1:
            raise XOAuthTransportError("x_oauth_request_budget_exhausted")
        self._remaining_requests -= 1
        try:
            return self._sender(
                method,
                url,
                timeout=self._timeout,
                follow_redirects=False,
                **kwargs,
            )
        except httpx.HTTPError as exc:
            raise XOAuthTransportError("x_oauth_transport_failed") from exc

    @staticmethod
    def _accept(response: httpx.Response) -> None:
        if response.status_code < 200 or response.status_code >= 300:
            raise XOAuthTransportError("x_oauth_http_rejected")
        if len(response.content) > MAX_OAUTH_RESPONSE_BYTES:
            raise XOAuthTransportError("x_oauth_response_too_large")


def _form(data: Mapping[str, str]) -> dict[str, str]:
    if not data or any(
        not key or not isinstance(value, str) or not value
        for key, value in data.items()
    ):
        raise XOAuthTransportError("x_oauth_form_invalid")
    return dict(data)


__all__ = ["XOAuthTransport", "XOAuthTransportError"]

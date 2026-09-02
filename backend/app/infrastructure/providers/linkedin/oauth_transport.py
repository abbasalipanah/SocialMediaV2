"""Bounded transport for LinkedIn OAuth and organization discovery."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

import httpx

MAX_OAUTH_RESPONSE_BYTES = 1_000_000


class LinkedInOAuthTransportError(RuntimeError):
    """Sanitized provider failure without tokens or response bodies."""


class LinkedInOAuthTransport:
    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        token_url: str,
        organization_acls_url: str,
        organizations_url: str,
        api_version: str,
        timeout_seconds: float,
        sender: Callable[..., httpx.Response] | None = None,
        request_budget: int = 200,
    ) -> None:
        if (
            not app_id
            or not app_secret
            or not token_url
            or not organization_acls_url
            or not organizations_url
            or not re.fullmatch(r"20[0-9]{4}", api_version)
            or timeout_seconds <= 0
            or request_budget < 1
            or request_budget > 500
        ):
            raise LinkedInOAuthTransportError("linkedin_oauth_transport_config_invalid")
        self._app_id = app_id
        self._app_secret = app_secret
        self._token_url = token_url
        self._organization_acls_url = organization_acls_url
        self._organizations_url = organizations_url.rstrip("/")
        self._api_version = api_version
        self._timeout = httpx.Timeout(timeout_seconds)
        self._sender = sender or httpx.request
        self._remaining_requests = request_budget

    def exchange(self, data: Mapping[str, str]) -> Mapping[str, object]:
        return self._json_request("POST", self._token_url, data=self._token_form(data))

    def refresh(self, data: Mapping[str, str]) -> Mapping[str, object]:
        return self._json_request("POST", self._token_url, data=self._token_form(data))

    def organization_acls(
        self,
        *,
        access_token: str,
    ) -> Mapping[str, object]:
        return self._authorized_get(
            self._organization_acls_url,
            access_token=access_token,
            params={"q": "roleAssignee", "state": "APPROVED", "count": "100"},
        )

    def organization(
        self,
        organization_id: str,
        *,
        access_token: str,
    ) -> Mapping[str, object]:
        if not organization_id.isdigit() or len(organization_id) > 32:
            raise LinkedInOAuthTransportError("linkedin_organization_id_invalid")
        return self._authorized_get(
            f"{self._organizations_url}/{organization_id}",
            access_token=access_token,
            params={},
        )

    def _token_form(self, data: Mapping[str, str]) -> dict[str, str]:
        payload = {
            **_form(data),
            "client_id": self._app_id,
            "client_secret": self._app_secret,
        }
        return payload

    def _authorized_get(
        self,
        url: str,
        *,
        access_token: str,
        params: Mapping[str, str],
    ) -> Mapping[str, object]:
        if not access_token:
            raise LinkedInOAuthTransportError("linkedin_oauth_token_invalid")
        return self._json_request(
            "GET",
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Linkedin-Version": self._api_version,
                "X-Restli-Protocol-Version": "2.0.0",
            },
            params=dict(params),
        )

    def _json_request(self, method: str, url: str, **kwargs) -> Mapping[str, object]:
        response = self._request(method, url, **kwargs)
        if response.status_code < 200 or response.status_code >= 300:
            raise LinkedInOAuthTransportError("linkedin_oauth_http_rejected")
        if len(response.content) > MAX_OAUTH_RESPONSE_BYTES:
            raise LinkedInOAuthTransportError("linkedin_oauth_response_too_large")
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise LinkedInOAuthTransportError("linkedin_oauth_response_invalid") from exc
        if not isinstance(payload, Mapping):
            raise LinkedInOAuthTransportError("linkedin_oauth_response_invalid")
        return payload

    def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if self._remaining_requests < 1:
            raise LinkedInOAuthTransportError("linkedin_oauth_request_budget_exhausted")
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
            raise LinkedInOAuthTransportError("linkedin_oauth_transport_failed") from exc


def _form(data: Mapping[str, str]) -> dict[str, str]:
    if not data or any(
        not key or not isinstance(value, str) or not value
        for key, value in data.items()
    ):
        raise LinkedInOAuthTransportError("linkedin_oauth_form_invalid")
    return dict(data)


__all__ = ["LinkedInOAuthTransport", "LinkedInOAuthTransportError"]

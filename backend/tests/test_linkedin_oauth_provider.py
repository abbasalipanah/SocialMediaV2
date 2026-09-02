from __future__ import annotations

from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core import load_settings
from app.infrastructure.providers.linkedin import (
    LinkedInOAuthError,
    LinkedInOAuthProvider,
    LinkedInOAuthTransport,
)

SCOPES = ("r_organization_admin", "r_organization_social")


class Sender:
    def __init__(self, responses: list[httpx.Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def __call__(self, method: str, url: str, **kwargs) -> httpx.Response:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def _response(status: int, payload: object) -> httpx.Response:
    request = httpx.Request("GET", "https://provider.example.test")
    return httpx.Response(status, json=payload, request=request)


def _provider(
    responses: list[httpx.Response],
) -> tuple[LinkedInOAuthProvider, Sender]:
    config = replace(
        load_settings().linkedin,
        oauth_app_id="linkedin-client-id",
        oauth_app_secret="linkedin-client-secret",
        account_enabled=True,
        oauth_mode="manual_intent_only",
    )
    sender = Sender(responses)
    transport = LinkedInOAuthTransport(
        app_id=config.oauth_app_id,
        app_secret=config.oauth_app_secret,
        token_url=config.token_url,
        organization_acls_url=config.organization_acls_url,
        organizations_url=config.organizations_url,
        api_version=config.api_version,
        timeout_seconds=5,
        sender=sender,
    )
    return LinkedInOAuthProvider(config=config, transport=transport), sender


def test_linkedin_authorization_requests_only_company_page_read_scopes() -> None:
    provider, _ = _provider([])

    query = parse_qs(
        urlparse(provider.authorization_url(state="signed-state", scopes=SCOPES)).query
    )

    assert query == {
        "client_id": ["linkedin-client-id"],
        "redirect_uri": [provider.redirect_uri],
        "response_type": ["code"],
        "scope": [" ".join(SCOPES)],
        "state": ["signed-state"],
    }


def test_linkedin_exchange_discovers_administered_organizations_without_batch_get() -> None:
    provider, sender = _provider(
        [
            _response(
                200,
                {
                    "access_token": "access-value",
                    "expires_in": 5_184_000,
                    "refresh_token": "refresh-value",
                    "refresh_token_expires_in": 31_536_000,
                    "scope": " ".join(SCOPES),
                },
            ),
            _response(
                200,
                {
                    "elements": [
                        {
                            "organization": "urn:li:organization:200",
                            "roleAssignee": "urn:li:person:member-a",
                            "role": "ANALYST",
                            "state": "APPROVED",
                        },
                        {
                            "organization": "urn:li:organization:100",
                            "roleAssignee": "urn:li:person:member-a",
                            "role": "ADMINISTRATOR",
                            "state": "APPROVED",
                        },
                    ]
                },
            ),
            _response(200, {"id": 100, "localizedName": "Acme"}),
            _response(200, {"id": 200, "localizedName": "Zeta"}),
        ]
    )

    grant = provider.exchange_and_discover(
        authorization_code="authorization-code",
        authorization_state="signed-state",
    )

    assert grant.provider_subject_id == "member-a"
    assert grant.refresh_token == "refresh-value"
    assert grant.granted_scopes == SCOPES
    assert [(item.external_id, item.display_name) for item in grant.accounts] == [
        ("100", "Acme"),
        ("200", "Zeta"),
    ]
    assert [call[1] for call in sender.calls] == [
        "https://www.linkedin.com/oauth/v2/accessToken",
        "https://api.linkedin.com/rest/organizationAcls",
        "https://api.linkedin.com/rest/organizations/100",
        "https://api.linkedin.com/rest/organizations/200",
    ]
    assert sender.calls[0][2]["data"] == {
        "client_id": "linkedin-client-id",
        "client_secret": "linkedin-client-secret",
        "code": "authorization-code",
        "grant_type": "authorization_code",
        "redirect_uri": provider.redirect_uri,
    }
    headers = sender.calls[1][2]["headers"]
    assert headers["Linkedin-Version"] == "202608"
    assert headers["X-Restli-Protocol-Version"] == "2.0.0"


def test_linkedin_identity_recheck_uses_acl_only_and_refresh_can_rotate() -> None:
    provider, sender = _provider(
        [
            _response(
                200,
                {
                    "elements": [
                        {
                            "organization": "urn:li:organization:100",
                            "roleAssignee": "urn:li:person:member-a",
                            "role": "ADMINISTRATOR",
                            "state": "APPROVED",
                        }
                    ]
                },
            ),
            _response(
                200,
                {
                    "access_token": "new-access",
                    "expires_in": 5_184_000,
                    "refresh_token": "new-refresh",
                    "refresh_token_expires_in": 30_000_000,
                    "scope": " ".join(SCOPES),
                },
            ),
        ]
    )

    accounts = provider.inspect_accounts(access_token="access-value")
    refreshed = provider.refresh(refresh_token="old-refresh")
    provider.revoke(access_token="new-access")

    assert [(item.external_id, item.display_name) for item in accounts] == [
        ("100", "LinkedIn Page 100")
    ]
    assert refreshed.refresh_token == "new-refresh"
    assert [call[1] for call in sender.calls] == [
        "https://api.linkedin.com/rest/organizationAcls",
        "https://www.linkedin.com/oauth/v2/accessToken",
    ]


def test_linkedin_rejects_cross_member_acl_payload_and_mismatched_organization() -> None:
    provider, _ = _provider(
        [
            _response(
                200,
                {
                    "elements": [
                        {
                            "organization": "urn:li:organization:100",
                            "roleAssignee": "urn:li:person:member-a",
                            "state": "APPROVED",
                        },
                        {
                            "organization": "urn:li:organization:200",
                            "roleAssignee": "urn:li:person:member-b",
                            "state": "APPROVED",
                        },
                    ]
                },
            )
        ]
    )
    with pytest.raises(LinkedInOAuthError, match="^linkedin_account_discovery_invalid$"):
        provider.inspect_accounts(access_token="access-value")

    provider, _ = _provider(
        [
            _response(
                200,
                {
                    "access_token": "access-value",
                    "expires_in": 5_184_000,
                    "scope": " ".join(SCOPES),
                },
            ),
            _response(
                200,
                {
                    "elements": [
                        {
                            "organization": "urn:li:organization:100",
                            "roleAssignee": "urn:li:person:member-a",
                            "state": "APPROVED",
                        }
                    ]
                },
            ),
            _response(200, {"id": 999, "localizedName": "Wrong Page"}),
        ]
    )
    with pytest.raises(LinkedInOAuthError, match="^linkedin_organization_response_invalid$"):
        provider.exchange_and_discover(
            authorization_code="authorization-code",
            authorization_state="signed-state",
        )

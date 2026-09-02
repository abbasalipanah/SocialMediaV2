"""LinkedIn 3-legged OAuth adapter for administered Company Pages."""

from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlencode

from app.application.ports import (
    OAuthAccountGrant,
    OAuthChannelError,
    OAuthProviderGrant,
    OAuthTokenRefresh,
)
from app.core import LinkedInConfig
from app.domain.platforms import PlatformId

from .oauth_transport import LinkedInOAuthTransport
from .responses import LinkedInResponseError, required_text

_ORGANIZATION_URN = re.compile(r"urn:li:organization:([0-9]{1,32})")
_PERSON_URN = re.compile(r"urn:li:person:([A-Za-z0-9_-]{1,255})")


class LinkedInOAuthError(OAuthChannelError):
    """Stable LinkedIn OAuth failure without provider payloads or credentials."""


class LinkedInOAuthProvider:
    platform = PlatformId.LINKEDIN

    def __init__(
        self,
        *,
        config: LinkedInConfig,
        transport: LinkedInOAuthTransport,
    ) -> None:
        self._config = config
        self._transport = transport

    @property
    def activation_enabled(self) -> bool:
        return self._config.account_enabled

    @property
    def redirect_uri(self) -> str:
        return self._config.redirect_uri

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str:
        if not state or scopes != self._config.required_scopes:
            raise LinkedInOAuthError("linkedin_authorization_request_invalid")
        query = urlencode(
            {
                "client_id": self._config.oauth_app_id,
                "redirect_uri": self._config.redirect_uri,
                "response_type": "code",
                "scope": " ".join(scopes),
                "state": state,
            }
        )
        return f"{self._config.authorization_url}?{query}"

    def exchange_and_discover(
        self,
        *,
        authorization_code: str,
        authorization_state: str,
    ) -> OAuthProviderGrant:
        if not authorization_code or not authorization_state:
            raise LinkedInOAuthError("linkedin_authorization_code_invalid")
        payload = self._transport.exchange(
            {
                "code": authorization_code,
                "grant_type": "authorization_code",
                "redirect_uri": self._config.redirect_uri,
            }
        )
        token = _token(payload)
        subject, organization_ids = self._authorized_organizations(token[0])
        accounts = tuple(
            OAuthAccountGrant(
                platform=PlatformId.LINKEDIN,
                external_id=organization_id,
                display_name=_organization_name(
                    self._transport.organization(
                        organization_id,
                        access_token=token[0],
                    ),
                    expected_id=organization_id,
                ),
            )
            for organization_id in organization_ids
        )
        return OAuthProviderGrant(
            provider_subject_id=subject,
            access_token=token[0],
            refresh_token=token[3],
            access_expires_in=token[1],
            refresh_expires_in=token[4],
            granted_scopes=token[2],
            accounts=tuple(
                sorted(accounts, key=lambda item: (item.display_name.casefold(), item.external_id))
            ),
        )

    def refresh(self, *, refresh_token: str) -> OAuthTokenRefresh:
        if not refresh_token:
            raise LinkedInOAuthError("linkedin_refresh_token_invalid")
        token = _token(
            self._transport.refresh(
                {"grant_type": "refresh_token", "refresh_token": refresh_token}
            )
        )
        return OAuthTokenRefresh(
            access_token=token[0],
            access_expires_in=token[1],
            granted_scopes=token[2],
            refresh_token=token[3],
            refresh_expires_in=token[4],
        )

    def inspect_accounts(self, *, access_token: str) -> tuple[OAuthAccountGrant, ...]:
        if not access_token:
            raise LinkedInOAuthError("linkedin_access_token_invalid")
        _, organization_ids = self._authorized_organizations(access_token)
        return tuple(
            OAuthAccountGrant(
                platform=PlatformId.LINKEDIN,
                external_id=organization_id,
                display_name=f"LinkedIn Page {organization_id}",
            )
            for organization_id in organization_ids
        )

    def revoke(self, *, access_token: str) -> None:
        if not access_token:
            raise LinkedInOAuthError("linkedin_access_token_invalid")
        # LinkedIn does not publish a provider-side token revocation endpoint for
        # this flow. Disconnect still revokes the encrypted local credential.

    def _authorized_organizations(self, access_token: str) -> tuple[str, tuple[str, ...]]:
        try:
            payload = self._transport.organization_acls(access_token=access_token)
            elements = payload.get("elements")
            if not isinstance(elements, list) or not elements or len(elements) > 100:
                raise ValueError
            organization_ids: set[str] = set()
            subjects: set[str] = set()
            for item in elements:
                if not isinstance(item, Mapping) or item.get("state") != "APPROVED":
                    raise ValueError
                organization = required_text(item, "organization")
                assignee = required_text(item, "roleAssignee")
                organization_match = _ORGANIZATION_URN.fullmatch(organization)
                subject_match = _PERSON_URN.fullmatch(assignee)
                if organization_match is None or subject_match is None:
                    raise ValueError
                organization_ids.add(organization_match.group(1))
                subjects.add(subject_match.group(1))
            if len(subjects) != 1 or not organization_ids:
                raise ValueError
            return next(iter(subjects)), tuple(sorted(organization_ids, key=int))
        except (LinkedInResponseError, TypeError, ValueError) as exc:
            raise LinkedInOAuthError("linkedin_account_discovery_invalid") from exc


def _organization_name(
    payload: Mapping[str, object],
    *,
    expected_id: str,
) -> str:
    try:
        organization_id = payload.get("id")
        if (
            isinstance(organization_id, bool)
            or not isinstance(organization_id, int)
            or str(organization_id) != expected_id
        ):
            raise ValueError
        return required_text(payload, "localizedName")
    except (LinkedInResponseError, TypeError, ValueError) as exc:
        raise LinkedInOAuthError("linkedin_organization_response_invalid") from exc


def _token(
    payload: Mapping[str, object],
) -> tuple[str, int, tuple[str, ...], str | None, int | None]:
    try:
        access_token = required_text(payload, "access_token")
        expires_in = _positive_int(payload.get("expires_in"))
        scopes = tuple(required_text(payload, "scope").split())
        refresh_value = payload.get("refresh_token")
        refresh_token = (
            required_text(payload, "refresh_token")
            if refresh_value is not None
            else None
        )
        refresh_expiry = payload.get("refresh_token_expires_in")
        refresh_expires_in = (
            _positive_int(refresh_expiry)
            if refresh_expiry is not None and refresh_token is not None
            else None
        )
        if not scopes or len(scopes) != len(set(scopes)):
            raise ValueError
        return access_token, expires_in, scopes, refresh_token, refresh_expires_in
    except (LinkedInResponseError, TypeError, ValueError) as exc:
        raise LinkedInOAuthError("linkedin_token_response_invalid") from exc


def _positive_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError
    return value


__all__ = ["LinkedInOAuthError", "LinkedInOAuthProvider"]

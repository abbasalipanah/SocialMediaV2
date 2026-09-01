from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.ports import OAuthAccountGrant, OAuthChannelError, OAuthTokenRefresh
from app.application.ports.credentials import CredentialRef, SecretToken, TokenKind
from app.application.services.oauth_channel_access import OAuthChannelAccessManager
from app.domain.platforms import PlatformId

NOW = datetime(2026, 9, 1, 12, tzinfo=UTC)
SCOPES = ("channel.read", "analytics.read")
REFERENCE = "a" * 64


class MemoryCredentials:
    def __init__(self) -> None:
        self.values: dict[CredentialRef, SecretToken] = {}
        self.batches: list[tuple[tuple[CredentialRef, SecretToken], ...]] = []

    def put(self, reference, token) -> None:
        self.values[reference] = token

    def put_many(self, items) -> None:
        self.batches.append(items)
        for reference, token in items:
            self.values[reference] = token

    def get(self, reference):
        return self.values.get(reference)

    def revoke(self, reference):
        return self.values.pop(reference, None) is not None

    def rotate(self, reference, *, dry_run):
        raise AssertionError("unexpected_rotate")


class FakeProvider:
    platform = PlatformId.YOUTUBE
    activation_enabled = True
    redirect_uri = "https://social.example.test/api/social/youtube/oauth/callback"

    def __init__(self) -> None:
        self.refresh_calls: list[str] = []
        self.inspect_calls: list[str] = []
        self.accounts = (
            OAuthAccountGrant(PlatformId.YOUTUBE, "UC-channel", "Example Channel"),
        )
        self.refreshed = OAuthTokenRefresh(
            access_token="new-access",
            access_expires_in=3600,
            granted_scopes=SCOPES,
        )

    def refresh(self, *, refresh_token: str) -> OAuthTokenRefresh:
        self.refresh_calls.append(refresh_token)
        return self.refreshed

    def inspect_accounts(self, *, access_token: str):
        self.inspect_calls.append(access_token)
        return self.accounts

    def authorization_url(self, *, state, scopes):
        raise AssertionError("unexpected_authorization")

    def exchange_and_discover(self, *, authorization_code):
        raise AssertionError("unexpected_exchange")

    def revoke(self, *, access_token):
        raise AssertionError("unexpected_revoke")


def _reference(kind: TokenKind) -> CredentialRef:
    return CredentialRef(PlatformId.YOUTUBE, REFERENCE, kind)


def _manager(provider: FakeProvider, credentials: MemoryCredentials):
    return OAuthChannelAccessManager(
        platform=PlatformId.YOUTUBE,
        required_scopes=SCOPES,
        allowed_scopes=SCOPES,
        provider=provider,
        credential_store=credentials,
        clock=lambda: NOW,
    )


def test_oauth_access_rechecks_owned_account_without_refreshing_valid_token() -> None:
    provider = FakeProvider()
    credentials = MemoryCredentials()
    credentials.put(
        _reference(TokenKind.ACCESS),
        SecretToken("current-access", NOW + timedelta(minutes=30)),
    )

    context = _manager(provider, credentials).resolve(
        credential_reference=REFERENCE,
        external_id="UC-channel",
    )

    assert context.access_token == "current-access"
    assert provider.refresh_calls == []
    assert provider.inspect_calls == ["current-access"]


def test_oauth_access_refreshes_early_and_persists_rotated_tokens() -> None:
    provider = FakeProvider()
    provider.refreshed = OAuthTokenRefresh(
        access_token="new-access",
        access_expires_in=3600,
        granted_scopes=SCOPES,
        refresh_token="rotated-refresh",
        refresh_expires_in=7200,
    )
    credentials = MemoryCredentials()
    credentials.put(
        _reference(TokenKind.ACCESS),
        SecretToken("expiring-access", NOW + timedelta(minutes=4)),
    )
    credentials.put(
        _reference(TokenKind.REFRESH),
        SecretToken("current-refresh"),
    )

    context = _manager(provider, credentials).resolve(
        credential_reference=REFERENCE,
        external_id="UC-channel",
    )

    assert context.access_token == "new-access"
    assert provider.refresh_calls == ["current-refresh"]
    assert provider.inspect_calls == ["new-access"]
    assert len(credentials.batches[-1]) == 2
    assert credentials.values[_reference(TokenKind.REFRESH)].value == "rotated-refresh"


def test_oauth_access_rejects_scope_escalation_and_account_mismatch() -> None:
    provider = FakeProvider()
    provider.refreshed = OAuthTokenRefresh(
        access_token="new-access",
        access_expires_in=3600,
        granted_scopes=(*SCOPES, "admin.write"),
    )
    credentials = MemoryCredentials()
    credentials.put(_reference(TokenKind.REFRESH), SecretToken("current-refresh"))

    with pytest.raises(OAuthChannelError, match="^oauth_access_scope_rejected$"):
        _manager(provider, credentials).resolve(
            credential_reference=REFERENCE,
            external_id="UC-channel",
        )

    credentials.put(
        _reference(TokenKind.ACCESS),
        SecretToken("current-access", NOW + timedelta(minutes=30)),
    )
    provider.accounts = (
        OAuthAccountGrant(PlatformId.YOUTUBE, "UC-other", "Other Channel"),
    )
    with pytest.raises(OAuthChannelError, match="^oauth_access_identity_rejected$"):
        _manager(provider, credentials).resolve(
            credential_reference=REFERENCE,
            external_id="UC-channel",
        )

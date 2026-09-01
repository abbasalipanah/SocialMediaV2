from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import pytest

from app.application.ports import (
    ActivationContext,
    ActivationIntent,
    ActivationStateClaims,
    OAuthAccountGrant,
    OAuthChannelError,
    OAuthConnectionResult,
    OAuthDiscovery,
    OAuthLinkResult,
    OAuthLinkSelection,
    OAuthProviderGrant,
)
from app.application.ports.credentials import CredentialRef, SecretToken
from app.application.services.oauth_channel_activation import (
    OAuthChannelActivationCoordinator,
)
from app.application.services.tiktok_activation import ActivationGate
from app.core import RuntimeMode, WritePolicy
from app.domain.platforms import PlatformId

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)
SCOPES = ("channel.read", "analytics.read")


def _context() -> ActivationContext:
    return ActivationContext(
        user_id="owner-1",
        brand_id=17,
        session_binding="a" * 64,
        sso_jti_hash="b" * 64,
        sso_consumed_at=NOW,
    )


class MemoryIntentStore:
    def __init__(self) -> None:
        self.intent: ActivationIntent | None = None

    def create_and_lease(self, intent: ActivationIntent) -> bool:
        self.intent = intent
        return True

    def consume(self, *, reference_hash, expected_context, consumed_at):
        if self.intent is None or self.intent.context != expected_context:
            return None
        return self.intent


class MemoryState:
    def __init__(self, intents: MemoryIntentStore) -> None:
        self.intents = intents

    def issue(self, *, intent_hash, context, expires_at) -> str:
        return f"state-{intent_hash}"

    def consume(self, token, *, expected_context) -> ActivationStateClaims:
        assert self.intents.intent is not None
        return ActivationStateClaims(
            intent_hash=self.intents.intent.reference_hash,
            context=expected_context,
            expires_at=self.intents.intent.expires_at,
        )

    def verified_brand_id(self, token: str) -> int:
        return 17


class MemoryCredentials:
    def __init__(self) -> None:
        self.values: dict[CredentialRef, SecretToken] = {}
        self.revoked: list[CredentialRef] = []

    def put(self, reference: CredentialRef, token: SecretToken) -> None:
        self.values[reference] = token

    def put_many(self, items) -> None:
        for reference, token in items:
            self.put(reference, token)

    def get(self, reference: CredentialRef) -> SecretToken | None:
        return self.values.get(reference)

    def revoke(self, reference: CredentialRef) -> bool:
        self.revoked.append(reference)
        return self.values.pop(reference, None) is not None

    def rotate(self, reference: CredentialRef, *, dry_run: bool):
        raise AssertionError("unexpected_rotate")


class FakeProvider:
    platform = PlatformId.YOUTUBE
    activation_enabled = True
    redirect_uri = "https://social.example.test/api/social/youtube/oauth/callback"

    def __init__(self) -> None:
        self.revoked: list[str] = []
        self.grant = OAuthProviderGrant(
            provider_subject_id="google-user-1",
            access_token="access-value",
            refresh_token="refresh-value",
            access_expires_in=3600,
            granted_scopes=SCOPES,
            accounts=(
                OAuthAccountGrant(
                    platform=PlatformId.YOUTUBE,
                    external_id="UC-channel",
                    display_name="Example Channel",
                ),
            ),
        )

    def authorization_url(self, *, state: str, scopes: tuple[str, ...]) -> str:
        query = urlencode({"state": state, "scope": " ".join(scopes)})
        return f"https://accounts.example.test/auth?{query}"

    def exchange_and_discover(self, *, authorization_code: str) -> OAuthProviderGrant:
        assert authorization_code == "auth-code"
        return self.grant

    def revoke(self, *, access_token: str) -> None:
        self.revoked.append(access_token)


class MemoryConnections:
    def __init__(self) -> None:
        self.bindings = ()
        self.fail_create = False
        self.remaining_after_disconnect = 0

    def create_pending(
        self, *, brand_id, platform, provider_subject_id, credentials, expires_at
    ) -> OAuthConnectionResult:
        if self.fail_create:
            raise RuntimeError("database unavailable with secret-value")
        self.bindings = credentials
        return OAuthConnectionResult(
            41, brand_id, platform, "pending_verification", len(credentials)
        )

    def list_discoveries(self, *, brand_id, platform):
        return tuple(
            OAuthDiscovery(41, platform, item.external_id, item.display_name, "discovered")
            for item in self.bindings
        )

    def link_accounts(self, *, brand_id, platform, connection_id, selections):
        return OAuthLinkResult(connection_id, brand_id, platform, len(selections), "connected")

    def disconnect(self, *, brand_id, platform, external_id):
        return OAuthLinkResult(
            41,
            brand_id,
            platform,
            self.remaining_after_disconnect,
            "connected" if self.remaining_after_disconnect else "disconnected",
        )


def _coordinator():
    intents = MemoryIntentStore()
    provider = FakeProvider()
    credentials = MemoryCredentials()
    connections = MemoryConnections()
    coordinator = OAuthChannelActivationCoordinator(
        platform=PlatformId.YOUTUBE,
        gate=ActivationGate(True, "v1", "v1", NOW - timedelta(minutes=1), NOW + timedelta(hours=1)),
        write_policy=WritePolicy(RuntimeMode.DEVELOPMENT, True),
        requested_scopes=SCOPES,
        allowed_scopes=(*SCOPES, "optional.read"),
        intent_store=intents,
        state_port=MemoryState(intents),
        provider=provider,
        credential_store=credentials,
        connection_store=connections,
        authority=type("Authority", (), {"allows": lambda self, context: True})(),
        clock=lambda: NOW,
        random_bytes=lambda size: b"r" * size,
    )
    return coordinator, provider, credentials, connections


def test_oauth_channel_activation_discovers_accounts_and_stores_redacted_tokens() -> None:
    coordinator, _, credentials, connections = _coordinator()
    start = coordinator.start(_context())
    query = parse_qs(urlparse(start.authorization_url).query)
    state = query["state"][0]

    result = coordinator.complete(
        query={"code": "auth-code", "state": state, "scope": " ".join(SCOPES)},
        context=_context(),
    )

    assert result == OAuthConnectionResult(
        41, 17, PlatformId.YOUTUBE, "pending_verification", 1
    )
    assert len(credentials.values) == 2
    assert {reference.token_kind for reference in credentials.values} == {"access", "refresh"}
    assert connections.bindings[0].external_id == "UC-channel"
    assert "access-value" not in repr(result)
    assert coordinator.callback_brand_id(query={"code": "x", "state": state}) == 17


def test_oauth_channel_activation_lists_and_links_only_after_authorization() -> None:
    coordinator, _, _, _ = _coordinator()
    start = coordinator.start(_context())
    state = parse_qs(urlparse(start.authorization_url).query)["state"][0]
    coordinator.complete(query={"code": "auth-code", "state": state}, context=_context())

    discoveries = coordinator.list_discoveries(_context())
    result = coordinator.link_accounts(
        context=_context(),
        connection_id=41,
        selections=(OAuthLinkSelection("UC-channel"),),
    )

    assert discoveries[0].display_name == "Example Channel"
    assert result.state == "connected"
    assert result.linked_count == 1


def test_oauth_channel_unlink_disables_locally_before_best_effort_revoke() -> None:
    coordinator, provider, credentials, _ = _coordinator()
    state = parse_qs(urlparse(coordinator.start(_context()).authorization_url).query)["state"][0]
    coordinator.complete(query={"code": "auth-code", "state": state}, context=_context())

    result = coordinator.unlink(context=_context(), external_id="UC-channel")

    assert result.state == "disconnected"
    assert credentials.values == {}
    assert provider.revoked == ["access-value"]


def test_oauth_channel_unlink_preserves_provider_grant_for_remaining_account() -> None:
    coordinator, provider, credentials, connections = _coordinator()
    provider.grant = OAuthProviderGrant(
        provider_subject_id="google-user-1",
        access_token="shared-access",
        refresh_token="shared-refresh",
        access_expires_in=3600,
        granted_scopes=SCOPES,
        accounts=(
            OAuthAccountGrant(PlatformId.YOUTUBE, "UC-first", "First Channel"),
            OAuthAccountGrant(PlatformId.YOUTUBE, "UC-second", "Second Channel"),
        ),
    )
    state = parse_qs(urlparse(coordinator.start(_context()).authorization_url).query)[
        "state"
    ][0]
    coordinator.complete(query={"code": "auth-code", "state": state}, context=_context())
    connections.remaining_after_disconnect = 1

    result = coordinator.unlink(context=_context(), external_id="UC-first")

    assert result.state == "connected"
    assert result.linked_count == 1
    assert provider.revoked == []
    assert len(credentials.values) == 2


def test_oauth_channel_activation_revokes_credentials_on_persistence_failure() -> None:
    coordinator, provider, credentials, connections = _coordinator()
    connections.fail_create = True
    state = parse_qs(urlparse(coordinator.start(_context()).authorization_url).query)["state"][0]

    with pytest.raises(OAuthChannelError, match="^oauth_activation_completion_failed$") as raised:
        coordinator.complete(query={"code": "auth-code", "state": state}, context=_context())

    assert "secret-value" not in str(raised.value)
    assert len(credentials.revoked) == 2
    assert credentials.values == {}
    assert provider.revoked == ["access-value"]


def test_oauth_channel_activation_rejects_scope_or_platform_escalation() -> None:
    coordinator, provider, _, _ = _coordinator()
    provider.grant = OAuthProviderGrant(
        provider_subject_id="google-user-1",
        access_token="secret-value",
        access_expires_in=3600,
        granted_scopes=(*SCOPES, "admin.write"),
        accounts=(
            OAuthAccountGrant(PlatformId.YOUTUBE, "UC-channel", "Example Channel"),
        ),
    )
    state = parse_qs(urlparse(coordinator.start(_context()).authorization_url).query)["state"][0]

    with pytest.raises(OAuthChannelError, match="^oauth_activation_grant_denied$"):
        coordinator.complete(query={"code": "auth-code", "state": state}, context=_context())


def test_oauth_channel_activation_rejects_unknown_callback_fields() -> None:
    coordinator, _, _, _ = _coordinator()

    with pytest.raises(OAuthChannelError, match="^oauth_activation_callback_rejected$"):
        coordinator.callback_brand_id(
            query={"code": "auth-code", "state": "state", "access_token": "leak"}
        )

from __future__ import annotations

from app.application.ports.platforms import ProviderAccount, ProviderCredential
from app.capabilities.registry import (
    CapabilityId,
    CapabilityStatus,
    bootstrap_registry,
    supported_capabilities,
)
from app.core.config import (
    TIKTOK_ACCOUNT_AUTHORIZATION_URL,
    TIKTOK_ACCOUNT_COMMENT_LIST_URL,
    TIKTOK_ACCOUNT_PROFILE_URL,
    TIKTOK_ACCOUNT_REFRESH_URL,
    TIKTOK_ACCOUNT_REVOKE_URL,
    TIKTOK_ACCOUNT_TOKEN_INFO_URL,
    TIKTOK_ACCOUNT_TOKEN_URL,
    TIKTOK_ACCOUNT_VIDEO_LIST_URL,
    TIKTOK_ACTIVATION_LINK_BASE,
    TIKTOK_APP_ID,
    TIKTOK_OPTIONAL_SCOPES,
    TIKTOK_PROVIDER_PROFILE,
    TIKTOK_REDIRECT_URI,
    TIKTOK_REQUIRED_SCOPES,
    TikTokConfig,
)
from app.domain.platforms import PlatformId
from app.infrastructure.providers.tiktok.accounts import (
    TikTokAccountsWireMapper,
    TikTokWireError,
)


def tiktok_config() -> TikTokConfig:
    return TikTokConfig(
        provider_profile=TIKTOK_PROVIDER_PROFILE,
        app_id=TIKTOK_APP_ID,
        app_secret="disposable-test-value",
        secret_rotated_at=None,
        account_enabled=False,
        oauth_mode="disabled",
        collection_enabled=False,
        advertiser_enabled=False,
        required_scopes=TIKTOK_REQUIRED_SCOPES,
        optional_scopes=TIKTOK_OPTIONAL_SCOPES,
        authorization_url=TIKTOK_ACCOUNT_AUTHORIZATION_URL,
        token_url=TIKTOK_ACCOUNT_TOKEN_URL,
        refresh_url=TIKTOK_ACCOUNT_REFRESH_URL,
        revoke_url=TIKTOK_ACCOUNT_REVOKE_URL,
        token_info_url=TIKTOK_ACCOUNT_TOKEN_INFO_URL,
        profile_url=TIKTOK_ACCOUNT_PROFILE_URL,
        video_list_url=TIKTOK_ACCOUNT_VIDEO_LIST_URL,
        comment_list_url=TIKTOK_ACCOUNT_COMMENT_LIST_URL,
        redirect_uri=TIKTOK_REDIRECT_URI,
        activation_link_base=TIKTOK_ACTIVATION_LINK_BASE,
    )


def test_platform_ports_keep_credentials_out_of_repr() -> None:
    account = ProviderAccount(
        platform=PlatformId.FACEBOOK,
        account_id="page-1",
        credential=ProviderCredential(access_token="disposable-token-value"),
    )
    assert "disposable-token-value" not in repr(account)


def test_bootstrap_capability_registry_is_explicit_and_honest() -> None:
    registry = bootstrap_registry()
    assert len(registry.records()) == len(PlatformId) * len(CapabilityId)
    assert supported_capabilities() == ("profile", "content", "comments", "audience")
    assert not any(
        record.status is CapabilityStatus.AVAILABLE for record in registry.records()
    )
    assert (
        registry.get(PlatformId.TIKTOK, CapabilityId.COMMENTS).status
        is CapabilityStatus.NOT_APPROVED
    )
    assert (
        registry.get(PlatformId.TIKTOK, CapabilityId.PROFILE).status
        is CapabilityStatus.MANUAL_ACTIVATION_REQUIRED
    )


def test_tiktok_account_holder_wire_fields_are_exact() -> None:
    mapper = TikTokAccountsWireMapper(tiktok_config())
    requested = (*TIKTOK_REQUIRED_SCOPES, TIKTOK_OPTIONAL_SCOPES[0])
    authorization = mapper.authorization_fields(
        state="opaque-state", requested_scopes=requested
    )
    assert set(authorization) == {
        "client_key",
        "redirect_uri",
        "response_type",
        "scope",
        "state",
    }
    assert authorization["client_key"] == TIKTOK_APP_ID
    assert authorization["scope"].split(",") == list(requested)

    token = mapper.token_fields(auth_code="disposable-auth-value")
    assert set(token) == {
        "auth_code",
        "client_id",
        "client_secret",
        "grant_type",
        "redirect_uri",
    }
    assert token["client_id"] == TIKTOK_APP_ID
    assert "code" not in token

    refresh = mapper.refresh_fields(refresh_token="disposable-refresh-value")
    assert set(refresh) == {
        "client_id",
        "client_secret",
        "grant_type",
        "refresh_token",
    }
    revoke = mapper.revoke_fields(access_token="disposable-access-value")
    assert set(revoke) == {"access_token", "client_id", "client_secret"}


def test_tiktok_wire_rejects_missing_required_or_unknown_scope() -> None:
    mapper = TikTokAccountsWireMapper(tiktok_config())
    try:
        mapper.authorization_fields(
            state="opaque-state", requested_scopes=TIKTOK_REQUIRED_SCOPES[:-1]
        )
    except TikTokWireError as exc:
        assert str(exc) == "scope_contract_mismatch"
    else:
        raise AssertionError("missing required scope was accepted")

    try:
        mapper.authorization_fields(
            state="opaque-state", requested_scopes=(*TIKTOK_REQUIRED_SCOPES, "video.publish")
        )
    except TikTokWireError as exc:
        assert str(exc) == "scope_contract_mismatch"
    else:
        raise AssertionError("unknown scope was accepted")

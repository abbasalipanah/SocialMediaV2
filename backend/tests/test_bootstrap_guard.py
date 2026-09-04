from __future__ import annotations

import base64
import json

import pytest
from sqlalchemy import create_engine

from app.capabilities import CapabilityStatus, bootstrap_registry
from app.core import (
    RUNTIME_MODE_SEQUENCE,
    ConfigurationError,
    RuntimeMode,
    WritePolicy,
    load_settings,
)
from app.domain.platforms import CapabilityId, PlatformId
from app.infrastructure.providers.linkedin.runtime import create_linkedin_activation_runtime
from app.infrastructure.providers.meta.runtime import create_meta_activation_runtime
from app.infrastructure.providers.tiktok.runtime import create_tiktok_activation_runtime
from app.infrastructure.providers.x.runtime import create_x_activation_runtime
from app.infrastructure.providers.youtube.runtime import create_youtube_activation_runtime
from app.workers.runtime import settings_worker_config
from tests.test_phase6_dashboard_api import MemoryAuthority

CONFIG_KEYS = (
    "APP_ENV",
    "APP_NAME",
    "SOCIAL_RUNTIME_MODE",
    "SOCIAL_WRITES_ENABLED",
    "SOCIAL_DB_URL",
    "SOCIAL_DB_HOST",
    "SOCIAL_DB_PORT",
    "SOCIAL_DB_NAME",
    "SOCIAL_DB_USER",
    "SOCIAL_DB_REQUIRE_TLS",
    "SOCIAL_SSO_HS256_SECRET",
    "SOCIAL_SESSION_COOKIE_SECURE",
    "SOCIAL_TIKTOK_BUSINESS_APP_SECRET",
    "SOCIAL_TIKTOK_SECRET_ROTATED_AT",
    "SOCIAL_TIKTOK_ACCOUNT_ENABLED",
    "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE",
    "SOCIAL_TIKTOK_COLLECTION_ENABLED",
    "SOCIAL_TIKTOK_ADVERTISER_ENABLED",
    "SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED",
    "SOCIAL_TIKTOK_ACTIVATION_ENABLED_AT",
    "SOCIAL_TIKTOK_ACTIVATION_EXPIRES_AT",
    "SOCIAL_TIKTOK_OAUTH_STATE_SECRET",
    "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID",
    "SOCIAL_CREDENTIAL_KEYRING_JSON",
    "SOCIAL_META_APP_SECRET",
    "SOCIAL_META_ACCOUNT_ENABLED",
    "SOCIAL_META_ACCOUNT_OAUTH_MODE",
    "SOCIAL_META_COLLECTION_ENABLED",
    "SOCIAL_META_ACTIVATION_GATE_ENABLED",
    "SOCIAL_META_ACTIVATION_ENABLED_AT",
    "SOCIAL_META_ACTIVATION_EXPIRES_AT",
    "SOCIAL_META_OAUTH_STATE_SECRET",
    "SOCIAL_YOUTUBE_PROVIDER_PROFILE",
    "SOCIAL_YOUTUBE_OAUTH_APP_ID",
    "SOCIAL_YOUTUBE_OAUTH_APP_SECRET",
    "SOCIAL_YOUTUBE_ACCOUNT_ENABLED",
    "SOCIAL_YOUTUBE_ACCOUNT_OAUTH_MODE",
    "SOCIAL_YOUTUBE_COLLECTION_ENABLED",
    "SOCIAL_YOUTUBE_AUTHORIZATION_URL",
    "SOCIAL_YOUTUBE_TOKEN_URL",
    "SOCIAL_YOUTUBE_REVOKE_URL",
    "SOCIAL_YOUTUBE_USERINFO_URL",
    "SOCIAL_YOUTUBE_CHANNELS_URL",
    "SOCIAL_YOUTUBE_PLAYLIST_ITEMS_URL",
    "SOCIAL_YOUTUBE_VIDEOS_URL",
    "SOCIAL_YOUTUBE_COMMENT_THREADS_URL",
    "SOCIAL_YOUTUBE_ANALYTICS_REPORTS_URL",
    "SOCIAL_YOUTUBE_ACCOUNT_REQUIRED_SCOPES",
    "SOCIAL_YOUTUBE_REDIRECT_URI",
    "SOCIAL_YOUTUBE_OAUTH_STATE_SECRET",
    "SOCIAL_YOUTUBE_ACTIVATION_GATE_ENABLED",
    "SOCIAL_YOUTUBE_ACTIVATION_ENABLED_AT",
    "SOCIAL_YOUTUBE_ACTIVATION_EXPIRES_AT",
    "SOCIAL_YOUTUBE_PROVIDER_TIMEOUT_SECONDS",
    "SOCIAL_X_PROVIDER_PROFILE",
    "SOCIAL_X_OAUTH_APP_ID",
    "SOCIAL_X_OAUTH_APP_SECRET",
    "SOCIAL_X_ACCOUNT_ENABLED",
    "SOCIAL_X_ACCOUNT_OAUTH_MODE",
    "SOCIAL_X_COLLECTION_ENABLED",
    "SOCIAL_X_AUTHORIZATION_URL",
    "SOCIAL_X_TOKEN_URL",
    "SOCIAL_X_REVOKE_URL",
    "SOCIAL_X_USERS_ME_URL",
    "SOCIAL_X_API_BASE_URL",
    "SOCIAL_X_ACCOUNT_REQUIRED_SCOPES",
    "SOCIAL_X_REDIRECT_URI",
    "SOCIAL_X_OAUTH_STATE_SECRET",
    "SOCIAL_X_ACTIVATION_GATE_ENABLED",
    "SOCIAL_X_ACTIVATION_ENABLED_AT",
    "SOCIAL_X_ACTIVATION_EXPIRES_AT",
    "SOCIAL_X_PROVIDER_TIMEOUT_SECONDS",
    "SOCIAL_LINKEDIN_PROVIDER_PROFILE",
    "SOCIAL_LINKEDIN_API_VERSION",
    "SOCIAL_LINKEDIN_OAUTH_APP_ID",
    "SOCIAL_LINKEDIN_OAUTH_APP_SECRET",
    "SOCIAL_LINKEDIN_ACCOUNT_ENABLED",
    "SOCIAL_LINKEDIN_ACCOUNT_OAUTH_MODE",
    "SOCIAL_LINKEDIN_COLLECTION_ENABLED",
    "SOCIAL_LINKEDIN_AUTHORIZATION_URL",
    "SOCIAL_LINKEDIN_TOKEN_URL",
    "SOCIAL_LINKEDIN_REST_BASE_URL",
    "SOCIAL_LINKEDIN_ORGANIZATION_ACLS_URL",
    "SOCIAL_LINKEDIN_ORGANIZATIONS_URL",
    "SOCIAL_LINKEDIN_POSTS_URL",
    "SOCIAL_LINKEDIN_SHARE_STATISTICS_URL",
    "SOCIAL_LINKEDIN_FOLLOWER_STATISTICS_URL",
    "SOCIAL_LINKEDIN_PAGE_STATISTICS_URL",
    "SOCIAL_LINKEDIN_ACCOUNT_REQUIRED_SCOPES",
    "SOCIAL_LINKEDIN_REDIRECT_URI",
    "SOCIAL_LINKEDIN_OAUTH_STATE_SECRET",
    "SOCIAL_LINKEDIN_ACTIVATION_GATE_ENABLED",
    "SOCIAL_LINKEDIN_ACTIVATION_ENABLED_AT",
    "SOCIAL_LINKEDIN_ACTIVATION_EXPIRES_AT",
    "SOCIAL_LINKEDIN_PROVIDER_TIMEOUT_SECONDS",
    "SOCIAL_VAULT_ENABLED",
    "SOCIAL_WORKER_SCHEDULE_ENABLED",
    "SOCIAL_AI_SUMMARY_ENABLED",
    "SOCIAL_AI_OPENROUTER_API_KEY",
    "SOCIAL_AI_OPENROUTER_BASE_URL",
    "SOCIAL_AI_OPENROUTER_MODELS",
    "SOCIAL_AI_PROVIDER_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def clean_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in CONFIG_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_default_bootstrap_is_fail_closed() -> None:
    settings = load_settings()
    policy = WritePolicy.from_settings(settings)
    assert settings.runtime_mode is RuntimeMode.DEVELOPMENT
    assert settings.social_writes_enabled is False
    assert settings.db.configured is False
    assert policy.allows("sync") is False
    with pytest.raises(PermissionError):
        policy.assert_allows_mutation("sync")


def test_runtime_contract_has_only_the_standalone_state_sequence() -> None:
    assert tuple(mode.value for mode in RUNTIME_MODE_SEQUENCE) == (
        "development",
        "dormant",
        "staging",
        "standalone_ready",
        "active",
    )
    assert tuple(RuntimeMode) == RUNTIME_MODE_SEQUENCE


@pytest.mark.parametrize(
    "legacy_mode",
    (
        "cutover_read_only",
        "cutover_credential_migration",
        "cutover_canary",
        "cutover_control_plane_drain",
        "cutover_activation",
    ),
)
def test_legacy_runtime_modes_are_rejected(
    monkeypatch: pytest.MonkeyPatch, legacy_mode: str
) -> None:
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", legacy_mode)
    with pytest.raises(ConfigurationError, match="not recognized"):
        load_settings()


def test_production_standalone_ready_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "standalone_ready")
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "false")
    monkeypatch.setenv(
        "SOCIAL_DB_URL",
        "postgresql+psycopg://v2:secret@127.0.0.1/social_media_v2",
    )
    settings = load_settings()
    assert settings.runtime_mode is RuntimeMode.STANDALONE_READY
    assert WritePolicy.from_settings(settings).allows("sso_consume") is False
    assert settings.meta.account_enabled is False
    assert settings.tiktok.account_enabled is False
    assert settings.youtube.account_enabled is False
    assert settings.x.account_enabled is False
    assert settings.linkedin.account_enabled is False
    assert settings.worker_schedule_enabled is False

    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    with pytest.raises(ConfigurationError, match="standalone_ready runtime must remain"):
        load_settings()


def test_v2_owned_staging_is_the_only_writable_staging_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "staging")
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    monkeypatch.setenv(
        "SOCIAL_DB_URL",
        "postgresql+psycopg://v2:secret@127.0.0.1/social_media_v2_staging",
    )
    monkeypatch.setenv("SOCIAL_SSO_HS256_SECRET", "s" * 32)
    monkeypatch.setenv("SOCIAL_SESSION_COOKIE_SECURE", "true")
    settings = load_settings()
    assert settings.runtime_mode is RuntimeMode.STAGING
    assert WritePolicy.from_settings(settings).allows("sso_consume") is True

    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "active")
    with pytest.raises(ConfigurationError, match="not valid for APP_ENV=staging"):
        load_settings()


def test_active_production_accepts_only_a_dedicated_secure_v2_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "active")
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_DB_URL", "postgresql://v2:secret@db.example/social_media_v2")
    monkeypatch.setenv("SOCIAL_SSO_HS256_SECRET", "s" * 32)
    monkeypatch.setenv("SOCIAL_SESSION_COOKIE_SECURE", "true")
    with pytest.raises(ConfigurationError, match="require TLS"):
        load_settings()

    monkeypatch.setenv("SOCIAL_DB_REQUIRE_TLS", "true")
    settings = load_settings()
    assert settings.runtime_mode is RuntimeMode.ACTIVE
    assert WritePolicy.from_settings(settings).allows("sso_consume") is True


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("SOCIAL_DB_URL", "postgresql://user:pass@prod.example/social_v2"),
        ("SOCIAL_DB_NAME", "socialmedia_adv"),
    ),
)
def test_non_disposable_database_targets_are_rejected(
    monkeypatch: pytest.MonkeyPatch, key: str, value: str
) -> None:
    monkeypatch.setenv(key, value)
    if key == "SOCIAL_DB_NAME":
        monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    with pytest.raises(ConfigurationError):
        load_settings()


def test_invalid_boolean_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "sometimes")
    with pytest.raises(ConfigurationError, match="explicit boolean"):
        load_settings()


def test_local_development_write_policy_requires_explicit_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    with pytest.raises(ConfigurationError, match="explicit V2 database"):
        load_settings()

    monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("SOCIAL_DB_NAME", "social_media_v2_local")
    policy = WritePolicy.from_settings(load_settings())
    assert policy.allows("fixture_seed") is True


def test_tiktok_activation_requires_every_runtime_prerequisite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_TIKTOK_ACCOUNT_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE", "manual_intent_only")
    with pytest.raises(ConfigurationError, match="writable database URL"):
        load_settings()

    monkeypatch.setenv("SOCIAL_TIKTOK_ACCOUNT_ENABLED", "false")
    monkeypatch.setenv("SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE", "disabled")
    dormant = load_settings()
    assert dormant.tiktok.account_enabled is False


def test_complete_local_tiktok_activation_configuration_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = {
        "local-key": base64.b64encode(b"a" * 32).decode("ascii"),
    }
    values = {
        "SOCIAL_WRITES_ENABLED": "true",
        "SOCIAL_DB_URL": "postgresql+psycopg://local:local@127.0.0.1/social_media_v2_local",
        "SOCIAL_VAULT_ENABLED": "true",
        "SOCIAL_TIKTOK_ACCOUNT_ENABLED": "true",
        "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE": "manual_intent_only",
        "SOCIAL_TIKTOK_BUSINESS_APP_SECRET": "social-app-secret",
        "SOCIAL_TIKTOK_SECRET_ROTATED_AT": "2026-07-20T12:00:00Z",
        "SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED": "true",
        "SOCIAL_TIKTOK_ACTIVATION_ENABLED_AT": "2026-07-18T10:00:00Z",
        "SOCIAL_TIKTOK_ACTIVATION_EXPIRES_AT": "2026-07-18T12:00:00Z",
        "SOCIAL_TIKTOK_OAUTH_STATE_SECRET": "s" * 32,
        "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID": "local-key",
        "SOCIAL_CREDENTIAL_KEYRING_JSON": json.dumps(keyring),
    }
    rotated_at = values.pop("SOCIAL_TIKTOK_SECRET_ROTATED_AT")
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ConfigurationError, match="rotated-secret attestation"):
        load_settings()

    monkeypatch.setenv("SOCIAL_TIKTOK_SECRET_ROTATED_AT", rotated_at)

    settings = load_settings()
    assert settings.tiktok.account_enabled is True
    assert settings.tiktok_activation.gate_enabled is True
    assert settings.tiktok_activation.credential_active_key_id == "local-key"
    engine = create_engine(settings.db.url)
    try:
        coordinator = create_tiktok_activation_runtime(
            settings=settings,
            policy=WritePolicy.from_settings(settings),
            engine=engine,
            authority_store=MemoryAuthority(),
        )
    finally:
        engine.dispose()
    assert coordinator is not None


def test_complete_local_meta_activation_configuration_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = {
        "local-key": base64.b64encode(b"m" * 32).decode("ascii"),
    }
    values = {
        "SOCIAL_WRITES_ENABLED": "true",
        "SOCIAL_DB_URL": "postgresql+psycopg://local:local@127.0.0.1/social_media_v2_local",
        "SOCIAL_VAULT_ENABLED": "true",
        "SOCIAL_META_ACCOUNT_ENABLED": "true",
        "SOCIAL_META_ACCOUNT_OAUTH_MODE": "manual_intent_only",
        "SOCIAL_META_APP_SECRET": "meta-app-value",
        "SOCIAL_META_ACTIVATION_GATE_ENABLED": "true",
        "SOCIAL_META_ACTIVATION_ENABLED_AT": "2026-07-18T10:00:00Z",
        "SOCIAL_META_ACTIVATION_EXPIRES_AT": "2026-07-18T12:00:00Z",
        "SOCIAL_META_OAUTH_STATE_SECRET": "m" * 32,
        "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID": "local-key",
        "SOCIAL_CREDENTIAL_KEYRING_JSON": json.dumps(keyring),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    settings = load_settings()
    assert settings.meta.account_enabled is True
    assert settings.meta_activation.gate_enabled is True
    engine = create_engine(settings.db.url)
    try:
        coordinator = create_meta_activation_runtime(
            settings=settings,
            policy=WritePolicy.from_settings(settings),
            engine=engine,
            authority_store=MemoryAuthority(),
        )
    finally:
        engine.dispose()
    assert coordinator is not None


def test_complete_local_youtube_configuration_is_fail_closed_then_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = {
        "local-key": base64.b64encode(b"y" * 32).decode("ascii"),
    }
    values = {
        "SOCIAL_WRITES_ENABLED": "true",
        "SOCIAL_DB_URL": (
            "postgresql+psycopg://local:local@127.0.0.1/social_media_v2_local"
        ),
        "SOCIAL_VAULT_ENABLED": "true",
        "SOCIAL_YOUTUBE_ACCOUNT_ENABLED": "true",
        "SOCIAL_YOUTUBE_ACCOUNT_OAUTH_MODE": "manual_intent_only",
        "SOCIAL_YOUTUBE_OAUTH_APP_ID": "local-oauth-app.apps.googleusercontent.com",
        "SOCIAL_YOUTUBE_OAUTH_APP_SECRET": "local-oauth-app-secret",
        "SOCIAL_YOUTUBE_ACTIVATION_GATE_ENABLED": "true",
        "SOCIAL_YOUTUBE_ACTIVATION_ENABLED_AT": "2026-08-31T10:00:00Z",
        "SOCIAL_YOUTUBE_ACTIVATION_EXPIRES_AT": "2026-09-30T10:00:00Z",
        "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID": "local-key",
        "SOCIAL_CREDENTIAL_KEYRING_JSON": json.dumps(keyring),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ConfigurationError, match="state secret"):
        load_settings()

    monkeypatch.setenv("SOCIAL_YOUTUBE_OAUTH_STATE_SECRET", "y" * 32)
    settings = load_settings()

    assert settings.youtube.account_enabled is True
    assert settings.youtube.collection_enabled is False
    assert settings.youtube_activation.gate_enabled is True

    monkeypatch.setenv("SOCIAL_YOUTUBE_COLLECTION_ENABLED", "true")
    settings = load_settings()
    registry = bootstrap_registry(settings)
    assert settings_worker_config(settings).provider_egress_enabled is True
    assert registry.get(
        PlatformId.YOUTUBE,
        CapabilityId.PROFILE,
    ).status is CapabilityStatus.AVAILABLE
    assert registry.get(
        PlatformId.YOUTUBE,
        CapabilityId.AUDIENCE,
    ).status is CapabilityStatus.PARTIAL
    assert registry.get(
        PlatformId.YOUTUBE,
        CapabilityId.AUDIENCE,
    ).reason == "playback_audience_breakdowns_available"
    engine = create_engine(settings.db.url)
    try:
        coordinator = create_youtube_activation_runtime(
            settings=settings,
            policy=WritePolicy.from_settings(settings),
            engine=engine,
            authority_store=MemoryAuthority(),
        )
    finally:
        engine.dispose()
    assert coordinator is not None


def test_youtube_endpoint_and_collection_gates_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_YOUTUBE_AUTHORIZATION_URL", "https://example.test/oauth")
    with pytest.raises(ConfigurationError, match="endpoint set"):
        load_settings()

    monkeypatch.delenv("SOCIAL_YOUTUBE_AUTHORIZATION_URL")
    monkeypatch.setenv("SOCIAL_YOUTUBE_COLLECTION_ENABLED", "true")
    with pytest.raises(ConfigurationError, match="requires the account integration"):
        load_settings()


def test_complete_local_x_configuration_is_fail_closed_then_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = {"local-key": base64.b64encode(b"x" * 32).decode("ascii")}
    values = {
        "SOCIAL_WRITES_ENABLED": "true",
        "SOCIAL_DB_URL": (
            "postgresql+psycopg://local:local@127.0.0.1/social_media_v2_local"
        ),
        "SOCIAL_VAULT_ENABLED": "true",
        "SOCIAL_X_ACCOUNT_ENABLED": "true",
        "SOCIAL_X_ACCOUNT_OAUTH_MODE": "manual_intent_only",
        "SOCIAL_X_OAUTH_APP_ID": "local-x-client-id",
        "SOCIAL_X_OAUTH_APP_SECRET": "local-x-client-secret",
        "SOCIAL_X_ACTIVATION_GATE_ENABLED": "true",
        "SOCIAL_X_ACTIVATION_ENABLED_AT": "2026-08-31T10:00:00Z",
        "SOCIAL_X_ACTIVATION_EXPIRES_AT": "2026-09-30T10:00:00Z",
        "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID": "local-key",
        "SOCIAL_CREDENTIAL_KEYRING_JSON": json.dumps(keyring),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ConfigurationError, match="state secret"):
        load_settings()

    monkeypatch.setenv("SOCIAL_X_OAUTH_STATE_SECRET", "x" * 32)
    settings = load_settings()

    assert settings.x.account_enabled is True
    assert settings.x.collection_enabled is False
    assert settings.x_activation.gate_enabled is True

    monkeypatch.setenv("SOCIAL_X_COLLECTION_ENABLED", "true")
    settings = load_settings()
    registry = bootstrap_registry(settings)
    assert settings_worker_config(settings).provider_egress_enabled is True
    assert registry.get(
        PlatformId.X,
        CapabilityId.PROFILE,
    ).status is CapabilityStatus.AVAILABLE
    assert registry.get(
        PlatformId.X,
        CapabilityId.CONTENT,
    ).status is CapabilityStatus.AVAILABLE
    assert registry.get(
        PlatformId.X,
        CapabilityId.COMMENTS,
    ).status is CapabilityStatus.PARTIAL
    assert registry.get(
        PlatformId.X,
        CapabilityId.COMMENTS,
    ).reason == "account_mentions_only"
    engine = create_engine(settings.db.url)
    try:
        coordinator = create_x_activation_runtime(
            settings=settings,
            policy=WritePolicy.from_settings(settings),
            engine=engine,
            authority_store=MemoryAuthority(),
        )
    finally:
        engine.dispose()
    assert coordinator is not None


def test_x_endpoint_and_collection_gates_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_X_AUTHORIZATION_URL", "https://example.test/oauth")
    with pytest.raises(ConfigurationError, match="endpoint set"):
        load_settings()

    monkeypatch.delenv("SOCIAL_X_AUTHORIZATION_URL")
    monkeypatch.setenv("SOCIAL_X_COLLECTION_ENABLED", "true")
    with pytest.raises(ConfigurationError, match="requires the account integration"):
        load_settings()


def test_complete_local_linkedin_configuration_is_fail_closed_then_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    keyring = {"local-key": base64.b64encode(b"l" * 32).decode("ascii")}
    values = {
        "SOCIAL_WRITES_ENABLED": "true",
        "SOCIAL_DB_URL": (
            "postgresql+psycopg://local:local@127.0.0.1/social_media_v2_local"
        ),
        "SOCIAL_VAULT_ENABLED": "true",
        "SOCIAL_LINKEDIN_ACCOUNT_ENABLED": "true",
        "SOCIAL_LINKEDIN_ACCOUNT_OAUTH_MODE": "manual_intent_only",
        "SOCIAL_LINKEDIN_OAUTH_APP_ID": "local-linkedin-client-id",
        "SOCIAL_LINKEDIN_OAUTH_APP_SECRET": "local-linkedin-client-secret",
        "SOCIAL_LINKEDIN_ACTIVATION_GATE_ENABLED": "true",
        "SOCIAL_LINKEDIN_ACTIVATION_ENABLED_AT": "2026-08-31T10:00:00Z",
        "SOCIAL_LINKEDIN_ACTIVATION_EXPIRES_AT": "2026-09-30T10:00:00Z",
        "SOCIAL_CREDENTIAL_ACTIVE_KEY_ID": "local-key",
        "SOCIAL_CREDENTIAL_KEYRING_JSON": json.dumps(keyring),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ConfigurationError, match="state secret"):
        load_settings()

    monkeypatch.setenv("SOCIAL_LINKEDIN_OAUTH_STATE_SECRET", "l" * 32)
    settings = load_settings()

    assert settings.linkedin.account_enabled is True
    assert settings.linkedin.collection_enabled is False
    assert settings.linkedin.api_version == "202608"
    assert settings.linkedin_activation.gate_enabled is True

    monkeypatch.setenv("SOCIAL_LINKEDIN_COLLECTION_ENABLED", "true")
    settings = load_settings()
    assert settings_worker_config(settings).provider_egress_enabled is True
    engine = create_engine(settings.db.url)
    try:
        coordinator = create_linkedin_activation_runtime(
            settings=settings,
            policy=WritePolicy.from_settings(settings),
            engine=engine,
            authority_store=MemoryAuthority(),
        )
    finally:
        engine.dispose()
    assert coordinator is not None


def test_linkedin_endpoint_and_collection_gates_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_LINKEDIN_API_VERSION", "202507")
    with pytest.raises(ConfigurationError, match="API version"):
        load_settings()

    monkeypatch.delenv("SOCIAL_LINKEDIN_API_VERSION")
    monkeypatch.setenv("SOCIAL_LINKEDIN_COLLECTION_ENABLED", "true")
    with pytest.raises(ConfigurationError, match="requires the account integration"):
        load_settings()

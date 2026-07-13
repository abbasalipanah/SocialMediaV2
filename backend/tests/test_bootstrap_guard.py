from __future__ import annotations

import pytest

from app.core import ConfigurationError, RuntimeMode, WritePolicy, load_settings

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
    "SOCIAL_TIKTOK_BUSINESS_APP_SECRET",
    "SOCIAL_TIKTOK_ACCOUNT_ENABLED",
    "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE",
    "SOCIAL_TIKTOK_COLLECTION_ENABLED",
    "SOCIAL_TIKTOK_ADVERTISER_ENABLED",
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


def test_production_like_environment_rejects_database_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "dormant")
    monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    with pytest.raises(ConfigurationError, match="cannot receive a database"):
        load_settings()


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
    with pytest.raises(ConfigurationError, match="explicit disposable database"):
        load_settings()

    monkeypatch.setenv("SOCIAL_DB_HOST", "127.0.0.1")
    monkeypatch.setenv("SOCIAL_DB_NAME", "social_media_v2_local")
    policy = WritePolicy.from_settings(load_settings())
    assert policy.allows("fixture_seed") is True


def test_tiktok_gates_and_secret_are_blocked_during_bootstrap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SOCIAL_TIKTOK_ACCOUNT_ENABLED", "true")
    with pytest.raises(ConfigurationError, match="runtime gates"):
        load_settings()

    monkeypatch.setenv("SOCIAL_TIKTOK_ACCOUNT_ENABLED", "false")
    monkeypatch.setenv("SOCIAL_TIKTOK_BUSINESS_APP_SECRET", "must-not-load")
    with pytest.raises(ConfigurationError, match="must not be loaded"):
        load_settings()

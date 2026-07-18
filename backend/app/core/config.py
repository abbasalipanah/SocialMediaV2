"""Fail-closed application configuration owned by the canonical backend tree."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse


class ConfigurationError(RuntimeError):
    """Raised before startup when a runtime setting violates a safety gate."""


class RuntimeMode(StrEnum):
    DEVELOPMENT = "development"
    DORMANT = "dormant"
    CUTOVER_READ_ONLY = "cutover_read_only"
    CUTOVER_CREDENTIAL_MIGRATION = "cutover_credential_migration"
    CUTOVER_CANARY = "cutover_canary"
    CUTOVER_CONTROL_PLANE_DRAIN = "cutover_control_plane_drain"
    CUTOVER_ACTIVATION = "cutover_activation"
    ACTIVE = "active"


TIKTOK_PROVIDER_PROFILE = "tiktok_business_accounts_v1_3"
TIKTOK_APP_ID = "7657818426198474768"
TIKTOK_ACCOUNT_AUTHORIZATION_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_ACCOUNT_TOKEN_URL = "https://business-api.tiktok.com/open_api/v1.3/tt_user/oauth2/token/"
TIKTOK_ACCOUNT_REFRESH_URL = (
    "https://business-api.tiktok.com/open_api/v1.3/tt_user/oauth2/refresh_token/"
)
TIKTOK_ACCOUNT_REVOKE_URL = "https://business-api.tiktok.com/open_api/v1.3/tt_user/oauth2/revoke/"
TIKTOK_ACCOUNT_TOKEN_INFO_URL = (
    "https://business-api.tiktok.com/open_api/v1.3/tt_user/token_info/get/"
)
TIKTOK_ACCOUNT_PROFILE_URL = "https://business-api.tiktok.com/open_api/v1.3/business/get/"
TIKTOK_ACCOUNT_VIDEO_LIST_URL = "https://business-api.tiktok.com/open_api/v1.3/business/video/list/"
TIKTOK_REDIRECT_URI = "https://social.theaccumulate.com/api/social/tiktok/oauth/callback"
TIKTOK_ACTIVATION_LINK_BASE = "https://social.theaccumulate.com/settings/tiktok/connect"
TIKTOK_REQUIRED_SCOPES = (
    "user.info.basic",
    "user.info.stats",
    "user.insights",
    "video.list",
    "video.insights",
)
TIKTOK_OPTIONAL_SCOPES = (
    "user.info.username",
    "user.info.profile",
    "user.account.type",
    "comment.list",
)

LOCAL_DB_HOSTS = {"127.0.0.1", "localhost", "::1", "postgres", "db"}
PRODUCTION_DB_NAMES = {"socialmedia_adv"}
PRODUCTION_LIKE_ENVS = {"production", "prod", "staging"}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be an explicit boolean")


def _csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = _env(name, ",".join(default))
    values = tuple(item.strip() for item in raw.split(",") if item.strip())
    if len(values) != len(set(values)):
        raise ConfigurationError(f"{name} contains duplicate values")
    return values


@dataclass(frozen=True)
class DatabaseConfig:
    url: str
    host: str
    port: int
    name: str
    user: str
    require_tls: bool

    @property
    def configured(self) -> bool:
        return bool(self.url or self.host or self.name or self.user)

    @property
    def resolved_host(self) -> str:
        if self.url:
            return (urlparse(self.url).hostname or "").lower()
        return self.host.lower()

    @property
    def resolved_name(self) -> str:
        if self.url:
            return urlparse(self.url).path.lstrip("/").split("/", 1)[0].lower()
        return self.name.lower()


@dataclass(frozen=True)
class TikTokConfig:
    provider_profile: str
    app_id: str
    app_secret: str
    account_enabled: bool
    oauth_mode: str
    collection_enabled: bool
    advertiser_enabled: bool
    required_scopes: tuple[str, ...]
    optional_scopes: tuple[str, ...]
    authorization_url: str
    token_url: str
    refresh_url: str
    revoke_url: str
    token_info_url: str
    profile_url: str
    video_list_url: str
    redirect_uri: str
    activation_link_base: str


@dataclass(frozen=True)
class AppSettings:
    app_env: str
    app_name: str
    runtime_mode: RuntimeMode
    social_writes_enabled: bool
    db: DatabaseConfig
    vault_enabled: bool
    log_level: str
    sso_hs256_secret: str
    provisioning_hmac_secret: str
    session_cookie_secure: bool
    media_storage_root: str
    tiktok: TikTokConfig


def _validate_database(app_env: str, mode: RuntimeMode, writes: bool, db: DatabaseConfig) -> None:
    if db.port < 1 or db.port > 65535:
        raise ConfigurationError("SOCIAL_DB_PORT must be between 1 and 65535")
    if app_env in PRODUCTION_LIKE_ENVS and db.configured:
        raise ConfigurationError("Production-like bootstrap cannot receive a database connection")
    if db.resolved_name in PRODUCTION_DB_NAMES:
        raise ConfigurationError(
            "Production social database is blocked before the final cutover gate"
        )
    if db.configured and db.resolved_host not in LOCAL_DB_HOSTS:
        raise ConfigurationError(
            "Only disposable local database hosts are allowed during bootstrap"
        )
    if writes and (app_env != "development" or mode is not RuntimeMode.DEVELOPMENT):
        raise ConfigurationError("Writes may only be enabled in disposable development mode")
    if writes and not db.configured:
        raise ConfigurationError("Development writes require an explicit disposable database")


def _validate_tiktok(config: TikTokConfig) -> None:
    if config.provider_profile != TIKTOK_PROVIDER_PROFILE:
        raise ConfigurationError("TikTok provider profile does not match the canonical contract")
    if not re.fullmatch(r"[0-9]{19}", config.app_id) or config.app_id != TIKTOK_APP_ID:
        raise ConfigurationError("TikTok App ID must be the exact canonical opaque string")
    if config.oauth_mode not in {"disabled", "manual_intent_only"}:
        raise ConfigurationError("Unsupported TikTok account OAuth mode")
    if not config.account_enabled and config.oauth_mode != "disabled":
        raise ConfigurationError(
            "TikTok OAuth mode must remain disabled while the account gate is off"
        )
    if config.account_enabled or config.collection_enabled or config.advertiser_enabled:
        raise ConfigurationError("TikTok runtime gates must remain disabled during safe bootstrap")
    if config.app_secret:
        raise ConfigurationError("TikTok app secret must not be loaded during safe bootstrap")
    if config.required_scopes != TIKTOK_REQUIRED_SCOPES:
        raise ConfigurationError("TikTok required scope set differs from the canonical contract")
    if not set(config.optional_scopes).issubset(TIKTOK_OPTIONAL_SCOPES):
        raise ConfigurationError("TikTok optional scopes contain an unsupported scope")


def load_settings() -> AppSettings:
    app_env = _env("APP_ENV", "development").lower()
    try:
        runtime_mode = RuntimeMode(_env("SOCIAL_RUNTIME_MODE", "development").lower())
    except ValueError as exc:
        raise ConfigurationError("SOCIAL_RUNTIME_MODE is not recognized") from exc
    try:
        db_port = int(_env("SOCIAL_DB_PORT", "5432"))
    except ValueError as exc:
        raise ConfigurationError("SOCIAL_DB_PORT must be an integer") from exc

    db = DatabaseConfig(
        url=_env("SOCIAL_DB_URL"),
        host=_env("SOCIAL_DB_HOST"),
        port=db_port,
        name=_env("SOCIAL_DB_NAME"),
        user=_env("SOCIAL_DB_USER"),
        require_tls=_bool("SOCIAL_DB_REQUIRE_TLS"),
    )
    writes = _bool("SOCIAL_WRITES_ENABLED")
    tiktok = TikTokConfig(
        provider_profile=_env("SOCIAL_TIKTOK_PROVIDER_PROFILE", TIKTOK_PROVIDER_PROFILE),
        app_id=_env("SOCIAL_TIKTOK_BUSINESS_APP_ID", TIKTOK_APP_ID),
        app_secret=_env("SOCIAL_TIKTOK_BUSINESS_APP_SECRET"),
        account_enabled=_bool("SOCIAL_TIKTOK_ACCOUNT_ENABLED"),
        oauth_mode=_env("SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE", "disabled"),
        collection_enabled=_bool("SOCIAL_TIKTOK_COLLECTION_ENABLED"),
        advertiser_enabled=_bool("SOCIAL_TIKTOK_ADVERTISER_ENABLED"),
        required_scopes=_csv("SOCIAL_TIKTOK_ACCOUNT_REQUIRED_SCOPES", TIKTOK_REQUIRED_SCOPES),
        optional_scopes=_csv("SOCIAL_TIKTOK_ACCOUNT_OPTIONAL_SCOPES", TIKTOK_OPTIONAL_SCOPES),
        authorization_url=_env(
            "SOCIAL_TIKTOK_ACCOUNT_AUTHORIZATION_URL",
            TIKTOK_ACCOUNT_AUTHORIZATION_URL,
        ),
        token_url=_env("SOCIAL_TIKTOK_ACCOUNT_TOKEN_URL", TIKTOK_ACCOUNT_TOKEN_URL),
        refresh_url=_env("SOCIAL_TIKTOK_ACCOUNT_REFRESH_URL", TIKTOK_ACCOUNT_REFRESH_URL),
        revoke_url=_env("SOCIAL_TIKTOK_ACCOUNT_REVOKE_URL", TIKTOK_ACCOUNT_REVOKE_URL),
        token_info_url=_env("SOCIAL_TIKTOK_ACCOUNT_TOKEN_INFO_URL", TIKTOK_ACCOUNT_TOKEN_INFO_URL),
        profile_url=_env("SOCIAL_TIKTOK_ACCOUNT_PROFILE_URL", TIKTOK_ACCOUNT_PROFILE_URL),
        video_list_url=_env("SOCIAL_TIKTOK_ACCOUNT_VIDEO_LIST_URL", TIKTOK_ACCOUNT_VIDEO_LIST_URL),
        redirect_uri=_env("SOCIAL_TIKTOK_REDIRECT_URI", TIKTOK_REDIRECT_URI),
        activation_link_base=_env(
            "SOCIAL_TIKTOK_ACTIVATION_LINK_BASE",
            TIKTOK_ACTIVATION_LINK_BASE,
        ),
    )
    _validate_database(app_env, runtime_mode, writes, db)
    _validate_tiktok(tiktok)
    sso_secret = _env("SOCIAL_SSO_HS256_SECRET")
    provisioning_secret = _env("SOCIAL_PROVISIONING_HMAC_SECRET")
    if app_env in PRODUCTION_LIKE_ENVS and (sso_secret or provisioning_secret):
        raise ConfigurationError("Production secrets are blocked before final cutover")
    return AppSettings(
        app_env=app_env,
        app_name=_env("APP_NAME", "social_media"),
        runtime_mode=runtime_mode,
        social_writes_enabled=writes,
        db=db,
        vault_enabled=_bool("SOCIAL_VAULT_ENABLED"),
        log_level=_env("SOCIAL_LOG_LEVEL", "INFO").upper(),
        sso_hs256_secret=sso_secret,
        provisioning_hmac_secret=provisioning_secret,
        session_cookie_secure=_bool("SOCIAL_SESSION_COOKIE_SECURE"),
        media_storage_root=_env("SOCIAL_MEDIA_STORAGE_ROOT"),
        tiktok=tiktok,
    )

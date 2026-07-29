"""Fail-closed application configuration owned by the canonical backend tree."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
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

META_APP_ID = "1133669534788144"
META_GRAPH_VERSION = "v23.0"
META_GRAPH_BASE_URL = "https://graph.facebook.com"
META_AUTHORIZATION_URL = f"https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth"
META_TOKEN_URL = f"{META_GRAPH_BASE_URL}/{META_GRAPH_VERSION}/oauth/access_token"
META_REDIRECT_URI = "https://social.theaccumulate.com/api/social/meta/oauth/callback"
META_REQUIRED_SCOPES = (
    "pages_show_list",
    "pages_read_engagement",
    "pages_read_user_content",
    "read_insights",
    "instagram_basic",
    "instagram_manage_insights",
    "instagram_manage_comments",
)

LOCAL_DB_HOSTS = {"127.0.0.1", "localhost", "::1", "postgres", "db"}
BLOCKED_SOURCE_DB_NAMES = {"socialmedia_adv"}
V2_DATABASE_PREFIX = "social_media_v2"
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


def _optional_datetime(name: str) -> datetime | None:
    raw = _env(name)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ConfigurationError(f"{name} must include a timezone")
    return parsed.astimezone(UTC)


def _positive_float(name: str, default: str) -> float:
    try:
        value = float(_env(name, default))
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be numeric") from exc
    if value <= 0 or value > 120:
        raise ConfigurationError(f"{name} must be greater than 0 and at most 120")
    return value


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
    secret_rotated_at: datetime | None
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
class TikTokActivationRuntimeConfig:
    gate_enabled: bool
    gate_enabled_at: datetime | None
    gate_expires_at: datetime | None
    oauth_state_secret: str
    credential_active_key_id: str
    credential_keyring_json: str
    provider_timeout_seconds: float
    requested_optional_scopes: tuple[str, ...]


@dataclass(frozen=True)
class MetaConfig:
    app_id: str
    app_secret: str
    account_enabled: bool
    oauth_mode: str
    graph_version: str
    graph_base_url: str
    authorization_url: str
    token_url: str
    redirect_uri: str
    required_scopes: tuple[str, ...]
    collection_enabled: bool = False


@dataclass(frozen=True)
class MetaActivationRuntimeConfig:
    gate_enabled: bool
    gate_enabled_at: datetime | None
    gate_expires_at: datetime | None
    oauth_state_secret: str
    credential_active_key_id: str
    credential_keyring_json: str
    provider_timeout_seconds: float


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
    session_cookie_secure: bool
    media_storage_root: str
    worker_schedule_enabled: bool
    tiktok: TikTokConfig
    tiktok_activation: TikTokActivationRuntimeConfig
    meta: MetaConfig
    meta_activation: MetaActivationRuntimeConfig


def _validate_database(app_env: str, mode: RuntimeMode, writes: bool, db: DatabaseConfig) -> None:
    if db.port < 1 or db.port > 65535:
        raise ConfigurationError("SOCIAL_DB_PORT must be between 1 and 65535")
    if db.resolved_name in BLOCKED_SOURCE_DB_NAMES:
        raise ConfigurationError("A live source-project database can never be used by V2")
    production_like = app_env in PRODUCTION_LIKE_ENVS
    if production_like and mode is RuntimeMode.ACTIVE:
        if not db.url or not db.resolved_name.startswith(V2_DATABASE_PREFIX):
            raise ConfigurationError("Active runtime requires a dedicated Social Media V2 database")
        if not writes:
            raise ConfigurationError("Active runtime requires local session and provider writes")
        if db.resolved_host not in LOCAL_DB_HOSTS and not db.require_tls:
            raise ConfigurationError("Remote production database connections require TLS")
    if not production_like and db.configured and db.resolved_host not in LOCAL_DB_HOSTS:
        raise ConfigurationError(
            "Development may only use a local Social Media V2 database"
        )
    if writes and not (
        (app_env == "development" and mode is RuntimeMode.DEVELOPMENT)
        or (production_like and mode is RuntimeMode.ACTIVE)
    ):
        raise ConfigurationError("Writes require development mode or the active V2 runtime")
    if writes and not db.configured:
        raise ConfigurationError("Writes require an explicit V2 database")


def _validate_tiktok(
    config: TikTokConfig,
    activation: TikTokActivationRuntimeConfig,
    *,
    writes: bool,
    db: DatabaseConfig,
    vault_enabled: bool,
    production_like: bool,
) -> None:
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
    if config.advertiser_enabled:
        raise ConfigurationError("TikTok advertiser integration is not available")
    _validate_public_endpoint(
        config.redirect_uri,
        expected_path="/api/social/tiktok/oauth/callback",
        label="TikTok OAuth redirect URI",
        production_like=production_like,
    )
    _validate_public_endpoint(
        config.activation_link_base,
        expected_path="/settings/tiktok/connect",
        label="TikTok activation link",
        production_like=production_like,
    )
    if _origin(config.redirect_uri) != _origin(config.activation_link_base):
        raise ConfigurationError("TikTok callback and activation link must use the same origin")
    if config.required_scopes != TIKTOK_REQUIRED_SCOPES:
        raise ConfigurationError("TikTok required scope set differs from the canonical contract")
    if not set(config.optional_scopes).issubset(TIKTOK_OPTIONAL_SCOPES):
        raise ConfigurationError("TikTok optional scopes contain an unsupported scope")
    if not config.account_enabled:
        if activation.gate_enabled:
            raise ConfigurationError("TikTok activation gate requires the account gate")
        if config.collection_enabled:
            raise ConfigurationError("TikTok collection requires the account integration")
        return
    if config.oauth_mode != "manual_intent_only":
        raise ConfigurationError("TikTok account activation requires manual_intent_only mode")
    if not writes or not db.url:
        raise ConfigurationError("TikTok account activation requires a writable database URL")
    if not config.app_secret:
        raise ConfigurationError("TikTok account activation requires the Business App secret")
    if config.secret_rotated_at is None:
        raise ConfigurationError(
            "TikTok account activation requires a rotated-secret attestation"
        )
    if not vault_enabled:
        raise ConfigurationError("TikTok account activation requires the credential vault")
    if not activation.gate_enabled:
        raise ConfigurationError("TikTok account activation requires the time-boxed gate")
    if (
        activation.gate_enabled_at is None
        or activation.gate_expires_at is None
        or activation.gate_enabled_at >= activation.gate_expires_at
    ):
        raise ConfigurationError("TikTok activation gate window is invalid")
    if len(activation.oauth_state_secret.encode("utf-8")) < 32:
        raise ConfigurationError("TikTok OAuth state secret must contain at least 32 bytes")
    if not activation.credential_active_key_id or not activation.credential_keyring_json:
        raise ConfigurationError("TikTok credential keyring is not configured")
    if not set(activation.requested_optional_scopes).issubset(config.optional_scopes):
        raise ConfigurationError("TikTok requested optional scopes are not allowed")
    if config.collection_enabled and not vault_enabled:
        raise ConfigurationError("TikTok collection requires the credential vault")


def _validate_meta(
    config: MetaConfig,
    activation: MetaActivationRuntimeConfig,
    *,
    writes: bool,
    db: DatabaseConfig,
    vault_enabled: bool,
    production_like: bool,
) -> None:
    if config.app_id != META_APP_ID or not re.fullmatch(r"[0-9]{16}", config.app_id):
        raise ConfigurationError("Meta App ID must match the approved Social application")
    if config.oauth_mode not in {"disabled", "manual_intent_only"}:
        raise ConfigurationError("Unsupported Meta account OAuth mode")
    if config.graph_version != META_GRAPH_VERSION:
        raise ConfigurationError("Meta Graph version differs from the approved contract")
    if config.graph_base_url != META_GRAPH_BASE_URL:
        raise ConfigurationError("Meta Graph base URL differs from the approved contract")
    if config.authorization_url != META_AUTHORIZATION_URL or config.token_url != META_TOKEN_URL:
        raise ConfigurationError("Meta OAuth endpoints differ from the approved contract")
    _validate_public_endpoint(
        config.redirect_uri,
        expected_path="/api/social/meta/oauth/callback",
        label="Meta OAuth redirect URI",
        production_like=production_like,
    )
    if config.required_scopes != META_REQUIRED_SCOPES:
        raise ConfigurationError("Meta OAuth scope set differs from the approved contract")
    if not config.account_enabled:
        if config.oauth_mode != "disabled" or activation.gate_enabled:
            raise ConfigurationError("Meta OAuth gates must remain disabled together")
        if config.collection_enabled:
            raise ConfigurationError("Meta collection requires the account integration")
        return
    if config.oauth_mode != "manual_intent_only":
        raise ConfigurationError("Meta account activation requires manual_intent_only mode")
    if not writes or not db.url:
        raise ConfigurationError("Meta account activation requires a writable database URL")
    if not config.app_secret:
        raise ConfigurationError("Meta account activation requires the app secret")
    if not vault_enabled:
        raise ConfigurationError("Meta account activation requires the credential vault")
    if not activation.gate_enabled:
        raise ConfigurationError("Meta account activation requires the time-boxed gate")
    if (
        activation.gate_enabled_at is None
        or activation.gate_expires_at is None
        or activation.gate_enabled_at >= activation.gate_expires_at
    ):
        raise ConfigurationError("Meta activation gate window is invalid")
    if len(activation.oauth_state_secret.encode("utf-8")) < 32:
        raise ConfigurationError("Meta OAuth state secret must contain at least 32 bytes")
    if not activation.credential_active_key_id or not activation.credential_keyring_json:
        raise ConfigurationError("Meta credential keyring is not configured")
    if config.collection_enabled and not vault_enabled:
        raise ConfigurationError("Meta collection requires the credential vault")


def _origin(value: str) -> tuple[str, str, int | None]:
    parsed = urlparse(value)
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), parsed.port


def _validate_public_endpoint(
    value: str,
    *,
    expected_path: str,
    label: str,
    production_like: bool,
) -> None:
    parsed = urlparse(value)
    if (
        not parsed.hostname
        or parsed.path != expected_path
        or parsed.params
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise ConfigurationError(f"{label} is invalid")
    if production_like and parsed.scheme != "https":
        raise ConfigurationError(f"{label} must use HTTPS")
    if not production_like and parsed.scheme not in {"http", "https"}:
        raise ConfigurationError(f"{label} must use HTTP or HTTPS")


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
        secret_rotated_at=_optional_datetime("SOCIAL_TIKTOK_SECRET_ROTATED_AT"),
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
    tiktok_activation = TikTokActivationRuntimeConfig(
        gate_enabled=_bool("SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED"),
        gate_enabled_at=_optional_datetime("SOCIAL_TIKTOK_ACTIVATION_ENABLED_AT"),
        gate_expires_at=_optional_datetime("SOCIAL_TIKTOK_ACTIVATION_EXPIRES_AT"),
        oauth_state_secret=_env("SOCIAL_TIKTOK_OAUTH_STATE_SECRET"),
        credential_active_key_id=_env("SOCIAL_CREDENTIAL_ACTIVE_KEY_ID"),
        credential_keyring_json=_env("SOCIAL_CREDENTIAL_KEYRING_JSON"),
        provider_timeout_seconds=_positive_float(
            "SOCIAL_TIKTOK_PROVIDER_TIMEOUT_SECONDS",
            "30",
        ),
        requested_optional_scopes=_csv(
            "SOCIAL_TIKTOK_ACCOUNT_REQUESTED_OPTIONAL_SCOPES",
            (),
        ),
    )
    meta = MetaConfig(
        app_id=_env("SOCIAL_META_APP_ID", META_APP_ID),
        app_secret=_env("SOCIAL_META_APP_SECRET"),
        account_enabled=_bool("SOCIAL_META_ACCOUNT_ENABLED"),
        oauth_mode=_env("SOCIAL_META_ACCOUNT_OAUTH_MODE", "disabled"),
        collection_enabled=_bool("SOCIAL_META_COLLECTION_ENABLED"),
        graph_version=_env("SOCIAL_META_GRAPH_VERSION", META_GRAPH_VERSION),
        graph_base_url=_env("SOCIAL_META_GRAPH_BASE_URL", META_GRAPH_BASE_URL),
        authorization_url=_env("SOCIAL_META_AUTHORIZATION_URL", META_AUTHORIZATION_URL),
        token_url=_env("SOCIAL_META_TOKEN_URL", META_TOKEN_URL),
        redirect_uri=_env("SOCIAL_META_REDIRECT_URI", META_REDIRECT_URI),
        required_scopes=_csv("SOCIAL_META_ACCOUNT_REQUIRED_SCOPES", META_REQUIRED_SCOPES),
    )
    meta_activation = MetaActivationRuntimeConfig(
        gate_enabled=_bool("SOCIAL_META_ACTIVATION_GATE_ENABLED"),
        gate_enabled_at=_optional_datetime("SOCIAL_META_ACTIVATION_ENABLED_AT"),
        gate_expires_at=_optional_datetime("SOCIAL_META_ACTIVATION_EXPIRES_AT"),
        oauth_state_secret=_env("SOCIAL_META_OAUTH_STATE_SECRET"),
        credential_active_key_id=_env("SOCIAL_CREDENTIAL_ACTIVE_KEY_ID"),
        credential_keyring_json=_env("SOCIAL_CREDENTIAL_KEYRING_JSON"),
        provider_timeout_seconds=_positive_float(
            "SOCIAL_META_PROVIDER_TIMEOUT_SECONDS",
            "30",
        ),
    )
    _validate_database(app_env, runtime_mode, writes, db)
    vault_enabled = _bool("SOCIAL_VAULT_ENABLED")
    _validate_tiktok(
        tiktok,
        tiktok_activation,
        writes=writes,
        db=db,
        vault_enabled=vault_enabled,
        production_like=app_env in PRODUCTION_LIKE_ENVS,
    )
    _validate_meta(
        meta,
        meta_activation,
        writes=writes,
        db=db,
        vault_enabled=vault_enabled,
        production_like=app_env in PRODUCTION_LIKE_ENVS,
    )
    sso_secret = _env("SOCIAL_SSO_HS256_SECRET")
    session_cookie_secure = _bool("SOCIAL_SESSION_COOKIE_SECURE")
    worker_schedule_enabled = _bool("SOCIAL_WORKER_SCHEDULE_ENABLED")
    if worker_schedule_enabled and (
        not writes
        or not db.url
        or not (meta.collection_enabled or tiktok.collection_enabled)
    ):
        raise ConfigurationError(
            "Worker schedule requires a writable V2 database and an enabled collector"
        )
    if app_env in PRODUCTION_LIKE_ENVS and runtime_mode is RuntimeMode.ACTIVE:
        if len(sso_secret.encode()) < 32:
            raise ConfigurationError("Active runtime requires a strong SSO secret")
        if not session_cookie_secure:
            raise ConfigurationError("Active runtime requires secure session cookies")
    return AppSettings(
        app_env=app_env,
        app_name=_env("APP_NAME", "social_media_v2"),
        runtime_mode=runtime_mode,
        social_writes_enabled=writes,
        db=db,
        vault_enabled=vault_enabled,
        log_level=_env("SOCIAL_LOG_LEVEL", "INFO").upper(),
        sso_hs256_secret=sso_secret,
        session_cookie_secure=session_cookie_secure,
        media_storage_root=_env("SOCIAL_MEDIA_STORAGE_ROOT"),
        worker_schedule_enabled=worker_schedule_enabled,
        tiktok=tiktok,
        tiktok_activation=tiktok_activation,
        meta=meta,
        meta_activation=meta_activation,
    )

"""Explicit runtime composition for time-boxed TikTok account activation."""

from __future__ import annotations

from sqlalchemy import Engine

from app.application.ports import AuthorityStore
from app.application.ports.credentials import CredentialError
from app.application.services.tiktok_activation import (
    ActivationGate,
    SessionActivationAuthority,
    TikTokActivationCoordinator,
)
from app.core import AppSettings, ConfigurationError, WritePolicy
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore
from app.infrastructure.persistence.social_v2.tiktok_activation import (
    ProjectionTikTokActivationStore,
)

from .accounts import (
    TikTokAccountsActivationProvider,
    TikTokActivationStateAdapter,
    TikTokHttpTransport,
    TikTokStateCodec,
    activation_config_version,
)


def create_tiktok_activation_runtime(
    *,
    settings: AppSettings,
    policy: WritePolicy,
    engine: Engine,
    authority_store: AuthorityStore,
) -> TikTokActivationCoordinator | None:
    if not settings.tiktok.account_enabled:
        return None
    runtime = settings.tiktok_activation
    if runtime.gate_enabled_at is None or runtime.gate_expires_at is None:
        raise ConfigurationError("TikTok activation gate window is missing")
    try:
        vault = AesGcmTokenVault.from_json(
            active_key_id=runtime.credential_active_key_id,
            keyring_json=runtime.credential_keyring_json,
        )
    except CredentialError as exc:
        raise ConfigurationError("TikTok credential keyring is invalid") from exc

    checkpoint_store = ProjectionCheckpointStore(engine, policy)
    activation_store = ProjectionTikTokActivationStore(engine, policy)
    provider_transport = TikTokHttpTransport(
        post_urls=(settings.tiktok.token_url, settings.tiktok.revoke_url),
        get_urls=(settings.tiktok.token_info_url,),
        timeout_seconds=runtime.provider_timeout_seconds,
    )
    provider = TikTokAccountsActivationProvider(
        config=settings.tiktok,
        transport=provider_transport,
    )
    config_version = activation_config_version(settings.tiktok)
    return TikTokActivationCoordinator(
        gate=ActivationGate(
            active=runtime.gate_enabled,
            config_version=config_version,
            expected_config_version=config_version,
            enabled_at=runtime.gate_enabled_at,
            expires_at=runtime.gate_expires_at,
        ),
        write_policy=policy,
        requested_scopes=(
            *settings.tiktok.required_scopes,
            *runtime.requested_optional_scopes,
        ),
        required_scopes=settings.tiktok.required_scopes,
        optional_scopes=settings.tiktok.optional_scopes,
        intent_store=activation_store,
        state_port=TikTokActivationStateAdapter(
            TikTokStateCodec(
                secret=runtime.oauth_state_secret.encode("utf-8"),
                replay_store=checkpoint_store,
            )
        ),
        provider=provider,
        credential_store=ProjectionCredentialStore(engine, policy, vault),
        link_store=activation_store,
        authority=SessionActivationAuthority(authority_store),
    )


__all__ = ["create_tiktok_activation_runtime"]

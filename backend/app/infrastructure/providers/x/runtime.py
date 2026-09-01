"""Runtime composition for time-boxed X account activation."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import Engine

from app.application.ports import AuthorityStore
from app.application.ports.credentials import CredentialError
from app.application.services.oauth_channel_activation import OAuthChannelActivationCoordinator
from app.application.services.tiktok_activation import ActivationGate, SessionActivationAuthority
from app.core import AppSettings, ConfigurationError, WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore
from app.infrastructure.persistence.social_v2 import (
    ProjectionOAuthConnectionStore,
    ProjectionOAuthIntentStore,
)
from app.infrastructure.providers.oauth_state import OAuthActivationStateAdapter, OAuthStateCodec

from .oauth import XOAuthProvider
from .oauth_transport import XOAuthTransport


def create_x_activation_runtime(
    *,
    settings: AppSettings,
    policy: WritePolicy,
    engine: Engine,
    authority_store: AuthorityStore,
) -> OAuthChannelActivationCoordinator | None:
    if not settings.x.account_enabled:
        return None
    runtime = settings.x_activation
    if runtime.gate_enabled_at is None or runtime.gate_expires_at is None:
        raise ConfigurationError("X activation gate window is missing")
    try:
        vault = AesGcmTokenVault.from_json(
            active_key_id=runtime.credential_active_key_id,
            keyring_json=runtime.credential_keyring_json,
        )
    except CredentialError as exc:
        raise ConfigurationError("X credential keyring is invalid") from exc
    checkpoint_store = ProjectionCheckpointStore(engine, policy)
    provider = XOAuthProvider(
        config=settings.x,
        transport=XOAuthTransport(
            client_id=settings.x.oauth_client_id,
            client_secret=settings.x.oauth_client_secret,
            token_url=settings.x.token_url,
            revoke_url=settings.x.revoke_url,
            get_urls=(settings.x.users_me_url,),
            timeout_seconds=runtime.provider_timeout_seconds,
        ),
        pkce_secret=runtime.oauth_state_secret.encode(),
    )
    config_version = _config_version(settings)
    return OAuthChannelActivationCoordinator(
        platform=PlatformId.X,
        gate=ActivationGate(
            active=runtime.gate_enabled,
            config_version=config_version,
            expected_config_version=config_version,
            enabled_at=runtime.gate_enabled_at,
            expires_at=runtime.gate_expires_at,
        ),
        write_policy=policy,
        requested_scopes=settings.x.required_scopes,
        allowed_scopes=settings.x.required_scopes,
        intent_store=ProjectionOAuthIntentStore(engine, policy, PlatformId.X),
        state_port=OAuthActivationStateAdapter(
            OAuthStateCodec(
                platform=PlatformId.X,
                provider_profile=settings.x.provider_profile,
                redirect_uri=settings.x.redirect_uri,
                secret=runtime.oauth_state_secret.encode(),
                replay_store=checkpoint_store,
            )
        ),
        provider=provider,
        credential_store=ProjectionCredentialStore(engine, policy, vault),
        connection_store=ProjectionOAuthConnectionStore(engine, policy, PlatformId.X),
        authority=SessionActivationAuthority(authority_store),
    )


def _config_version(settings: AppSettings) -> str:
    payload = {
        "authorization_url": settings.x.authorization_url,
        "oauth_client_id": settings.x.oauth_client_id,
        "provider_profile": settings.x.provider_profile,
        "redirect_uri": settings.x.redirect_uri,
        "required_scopes": settings.x.required_scopes,
        "token_url": settings.x.token_url,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


__all__ = ["create_x_activation_runtime"]

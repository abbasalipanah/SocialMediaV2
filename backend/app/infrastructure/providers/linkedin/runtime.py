"""Runtime composition for time-boxed LinkedIn Company Page activation."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import Engine

from app.application.ports import AuthorityStore
from app.application.ports.credentials import CredentialError
from app.application.services.oauth_channel_activation import (
    OAuthChannelActivationCoordinator,
)
from app.application.services.tiktok_activation import (
    ActivationGate,
    SessionActivationAuthority,
)
from app.core import AppSettings, ConfigurationError, WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore
from app.infrastructure.persistence.social_v2 import (
    ProjectionOAuthConnectionStore,
    ProjectionOAuthIntentStore,
)
from app.infrastructure.providers.oauth_state import (
    OAuthActivationStateAdapter,
    OAuthStateCodec,
)

from .oauth import LinkedInOAuthProvider
from .oauth_transport import LinkedInOAuthTransport


def create_linkedin_activation_runtime(
    *,
    settings: AppSettings,
    policy: WritePolicy,
    engine: Engine,
    authority_store: AuthorityStore,
) -> OAuthChannelActivationCoordinator | None:
    if not settings.linkedin.account_enabled:
        return None
    runtime = settings.linkedin_activation
    if runtime.gate_enabled_at is None or runtime.gate_expires_at is None:
        raise ConfigurationError("LinkedIn activation gate window is missing")
    try:
        vault = AesGcmTokenVault.from_json(
            active_key_id=runtime.credential_active_key_id,
            keyring_json=runtime.credential_keyring_json,
        )
    except CredentialError as exc:
        raise ConfigurationError("LinkedIn credential keyring is invalid") from exc
    checkpoint_store = ProjectionCheckpointStore(engine, policy)
    provider = LinkedInOAuthProvider(
        config=settings.linkedin,
        transport=LinkedInOAuthTransport(
            app_id=settings.linkedin.oauth_app_id,
            app_secret=settings.linkedin.oauth_app_secret,
            token_url=settings.linkedin.token_url,
            organization_acls_url=settings.linkedin.organization_acls_url,
            organizations_url=settings.linkedin.organizations_url,
            api_version=settings.linkedin.api_version,
            timeout_seconds=runtime.provider_timeout_seconds,
        ),
    )
    config_version = _config_version(settings)
    return OAuthChannelActivationCoordinator(
        platform=PlatformId.LINKEDIN,
        gate=ActivationGate(
            active=runtime.gate_enabled,
            config_version=config_version,
            expected_config_version=config_version,
            enabled_at=runtime.gate_enabled_at,
            expires_at=runtime.gate_expires_at,
        ),
        write_policy=policy,
        requested_scopes=settings.linkedin.required_scopes,
        allowed_scopes=settings.linkedin.required_scopes,
        intent_store=ProjectionOAuthIntentStore(engine, policy, PlatformId.LINKEDIN),
        state_port=OAuthActivationStateAdapter(
            OAuthStateCodec(
                platform=PlatformId.LINKEDIN,
                provider_profile=settings.linkedin.provider_profile,
                redirect_uri=settings.linkedin.redirect_uri,
                secret=runtime.oauth_state_secret.encode(),
                replay_store=checkpoint_store,
            )
        ),
        provider=provider,
        credential_store=ProjectionCredentialStore(engine, policy, vault),
        connection_store=ProjectionOAuthConnectionStore(
            engine,
            policy,
            PlatformId.LINKEDIN,
        ),
        authority=SessionActivationAuthority(authority_store),
    )


def _config_version(settings: AppSettings) -> str:
    payload = {
        "api_version": settings.linkedin.api_version,
        "authorization_url": settings.linkedin.authorization_url,
        "oauth_app_id": settings.linkedin.oauth_app_id,
        "provider_profile": settings.linkedin.provider_profile,
        "redirect_uri": settings.linkedin.redirect_uri,
        "required_scopes": settings.linkedin.required_scopes,
        "token_url": settings.linkedin.token_url,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


__all__ = ["create_linkedin_activation_runtime"]

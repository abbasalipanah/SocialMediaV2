"""Explicit runtime composition for time-boxed Meta self-service connection."""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import Engine

from app.application.ports import AuthorityStore
from app.application.ports.credentials import CredentialError
from app.application.services.meta_activation import MetaActivationCoordinator
from app.application.services.tiktok_activation import (
    ActivationGate,
    ProjectionActivationAuthority,
)
from app.core import AppSettings, ConfigurationError, WritePolicy
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore
from app.infrastructure.persistence.legacy_socialmedia import ProjectionMetaConnectionStore

from .oauth import MetaAccountsActivationProvider, MetaOAuthTransport
from .oauth_state import MetaActivationStateAdapter, MetaStateCodec


def create_meta_activation_runtime(
    *,
    settings: AppSettings,
    policy: WritePolicy,
    engine: Engine,
    authority_store: AuthorityStore,
) -> MetaActivationCoordinator | None:
    if not settings.meta.account_enabled:
        return None
    runtime = settings.meta_activation
    if runtime.gate_enabled_at is None or runtime.gate_expires_at is None:
        raise ConfigurationError("Meta activation gate window is missing")
    try:
        vault = AesGcmTokenVault.from_json(
            active_key_id=runtime.credential_active_key_id,
            keyring_json=runtime.credential_keyring_json,
        )
    except CredentialError as exc:
        raise ConfigurationError("Meta credential keyring is invalid") from exc
    checkpoint_store = ProjectionCheckpointStore(engine, policy)
    connection_store = ProjectionMetaConnectionStore(engine, policy)
    oauth_transport = MetaOAuthTransport(
        token_url=settings.meta.token_url,
        graph_base_url=settings.meta.graph_base_url,
        graph_version=settings.meta.graph_version,
        timeout_seconds=runtime.provider_timeout_seconds,
    )
    provider = MetaAccountsActivationProvider(
        config=settings.meta,
        oauth_transport=oauth_transport,
    )
    config_version = _config_version(settings)
    return MetaActivationCoordinator(
        gate=ActivationGate(
            active=runtime.gate_enabled,
            config_version=config_version,
            expected_config_version=config_version,
            enabled_at=runtime.gate_enabled_at,
            expires_at=runtime.gate_expires_at,
        ),
        write_policy=policy,
        requested_scopes=settings.meta.required_scopes,
        intent_store=connection_store,
        state_port=MetaActivationStateAdapter(
            MetaStateCodec(
                secret=runtime.oauth_state_secret.encode(),
                replay_store=checkpoint_store,
            )
        ),
        provider=provider,
        credential_store=ProjectionCredentialStore(engine, policy, vault),
        connection_store=connection_store,
        authority=ProjectionActivationAuthority(authority_store),
    )


def _config_version(settings: AppSettings) -> str:
    payload = {
        "app_id": settings.meta.app_id,
        "authorization_url": settings.meta.authorization_url,
        "graph_base_url": settings.meta.graph_base_url,
        "graph_version": settings.meta.graph_version,
        "redirect_uri": settings.meta.redirect_uri,
        "required_scopes": settings.meta.required_scopes,
        "token_url": settings.meta.token_url,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()


__all__ = ["create_meta_activation_runtime"]

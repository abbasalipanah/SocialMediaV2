from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.core.config import (
    META_APP_ID,
    META_AUTHORIZATION_URL,
    META_GRAPH_BASE_URL,
    META_GRAPH_VERSION,
    META_REDIRECT_URI,
    META_REQUIRED_SCOPES,
    META_TOKEN_URL,
    MetaConfig,
)
from app.domain.platforms import PlatformId
from app.infrastructure.providers.meta import (
    MetaAccountsActivationProvider,
    MetaOAuthTransport,
    MetaStateBinding,
    MetaStateCodec,
    MetaStateError,
)

NOW = datetime(2026, 7, 18, 12, tzinfo=UTC)


class MemoryReplayStore:
    def __init__(self) -> None:
        self.claims: set[str] = set()

    def get(self, key: CheckpointKey) -> ProviderCheckpoint | None:
        return None

    def put(
        self,
        checkpoint: ProviderCheckpoint,
        *,
        expected_version: int | None,
    ) -> bool:
        return False

    def claim_once(
        self,
        key: CheckpointKey,
        operation_id: str,
        expires_at: datetime,
    ) -> bool:
        claim = f"{key.account_id}:{operation_id}"
        if claim in self.claims:
            return False
        self.claims.add(claim)
        return True


def _config() -> MetaConfig:
    return MetaConfig(
        app_id=META_APP_ID,
        app_secret="fixture-meta-value",
        account_enabled=True,
        oauth_mode="manual_intent_only",
        graph_version=META_GRAPH_VERSION,
        graph_base_url=META_GRAPH_BASE_URL,
        authorization_url=META_AUTHORIZATION_URL,
        token_url=META_TOKEN_URL,
        redirect_uri=META_REDIRECT_URI,
        required_scopes=META_REQUIRED_SCOPES,
    )


def test_meta_state_is_bound_and_single_use() -> None:
    store = MemoryReplayStore()
    codec = MetaStateCodec(
        secret=b"m" * 32,
        replay_store=store,
        clock=lambda: NOW,
    )
    binding = MetaStateBinding(
        nonce="meta-state-nonce-123456",
        intent_hash=hashlib.sha256(b"intent").hexdigest(),
        user_id="user-1",
        brand_id=101,
        session_binding=hashlib.sha256(b"session").hexdigest(),
        expires_at=NOW + timedelta(minutes=15),
    )
    token = codec.issue(binding)
    assert (
        codec.consume(
            token,
            expected_user_id="user-1",
            expected_brand_id=101,
            expected_session_binding=binding.session_binding,
        )
        == binding
    )
    with pytest.raises(MetaStateError, match="meta_state_replayed"):
        codec.consume(
            token,
            expected_user_id="user-1",
            expected_brand_id=101,
            expected_session_binding=binding.session_binding,
        )


def test_meta_exchange_discovers_facebook_and_instagram_without_token_echo() -> None:
    token_requests: list[httpx.Request] = []
    graph_requests: list[httpx.Request] = []

    def token_handler(request: httpx.Request) -> httpx.Response:
        token_requests.append(request)
        if request.url.params.get("grant_type") == "fb_exchange_token":
            return httpx.Response(
                200,
                json={"access_token": "long-user-value", "expires_in": 5_184_000},
                request=request,
            )
        return httpx.Response(
            200,
            json={"access_token": "short-user-value"},
            request=request,
        )

    def graph_handler(request: httpx.Request) -> httpx.Response:
        graph_requests.append(request)
        path = request.url.path
        if path.endswith("/me/permissions"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"permission": scope, "status": "granted"} for scope in META_REQUIRED_SCOPES
                    ]
                },
                request=request,
            )
        if path.endswith("/me/accounts"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "10001",
                            "name": "Coastal Page",
                            "access_token": "page-access-value",
                            "instagram_business_account": {
                                "id": "20002",
                                "username": "coastal.hotel",
                            },
                        }
                    ]
                },
                request=request,
            )
        return httpx.Response(200, json={"id": "30003"}, request=request)

    token_session = httpx.Client(transport=httpx.MockTransport(token_handler))
    oauth_transport = MetaOAuthTransport(
        token_url=META_TOKEN_URL,
        graph_base_url=META_GRAPH_BASE_URL,
        graph_version=META_GRAPH_VERSION,
        timeout_seconds=5,
        sender=token_session.request,
    )
    provider = MetaAccountsActivationProvider(
        config=_config(),
        oauth_transport=oauth_transport,
        graph_wire=httpx.MockTransport(graph_handler),
    )

    grant = provider.exchange_and_discover(authorization_code="authorization-value")

    assert grant.provider_user_id == "30003"
    assert grant.granted_scopes == META_REQUIRED_SCOPES
    assert [(item.platform, item.external_id, item.display_name) for item in grant.accounts] == [
        (PlatformId.FACEBOOK, "10001", "Coastal Page"),
        (PlatformId.INSTAGRAM, "20002", "coastal.hotel"),
    ]
    assert "long-user-value" not in repr(grant)
    assert "page-access-value" not in repr(grant)
    assert len(token_requests) == 2
    assert all(request.url.host == "graph.facebook.com" for request in graph_requests)
    assert all(
        request.headers["authorization"] == "Bearer long-user-value" for request in graph_requests
    )

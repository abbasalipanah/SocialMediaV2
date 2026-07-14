from __future__ import annotations

import json
import os
import secrets
from collections.abc import Callable, Iterator, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, create_engine, text

from app.api.auth import COOKIE_NAME
from app.application.ports import ActivationContext, TikTokActivationError
from app.application.ports.credentials import CredentialRef, TokenKind
from app.application.services.provisioning import SignedRequest, apply_signed_event, sign_request
from app.application.services.sso import consume_sso
from app.application.services.tiktok_activation import (
    ActivationGate,
    ProjectionActivationAuthority,
    TikTokActivationCoordinator,
)
from app.core.config import (
    TIKTOK_ACCOUNT_AUTHORIZATION_URL,
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
    RuntimeMode,
    TikTokConfig,
    load_settings,
)
from app.core.security import sha256_text
from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore
from app.infrastructure.persistence.legacy_socialmedia.tiktok_activation import (
    ProjectionTikTokActivationStore,
)
from app.infrastructure.persistence.projection_state import ProjectionStateStore
from app.infrastructure.providers.tiktok.accounts import (
    TikTokAccountsActivationProvider,
    TikTokActivationStateAdapter,
    TikTokStateCodec,
    activation_config_version,
)
from app.main import create_app

DATABASE_URL = os.getenv("PHASE9_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="PHASE9_POSTGRES_URL is not configured",
)
OUTBOX = Path(__file__).parent / "fixtures" / "phase9" / "accumulate_outbox.json"
PATH = "/internal/provisioning/events"


class EmptyReporting:
    def list_connections(self, *, brand_ids: tuple[str, ...]):
        del brand_ids
        return ()


class FakeActivationTransport:
    def __init__(
        self,
        *,
        scopes: tuple[str, ...],
        on_inspect: Callable[[], None] | None = None,
    ) -> None:
        self.scopes = scopes
        self.on_inspect = on_inspect
        self.access_value = secrets.token_urlsafe(36)
        self.refresh_value = secrets.token_urlsafe(36)
        self.business_id = f"phase9-business-{secrets.token_hex(4)}"
        self.calls: list[str] = []

    def post(self, url: str, *, data: Mapping[str, str]) -> Mapping[str, object]:
        del data
        if url == TIKTOK_ACCOUNT_TOKEN_URL:
            self.calls.append("exchange")
            return {
                "code": 0,
                "message": "OK",
                "request_id": "phase9-token",
                "data": {
                    "access_token": self.access_value,
                    "refresh_token": self.refresh_value,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "refresh_expires_in": 7200,
                    "scope": list(self.scopes),
                },
            }
        if url == TIKTOK_ACCOUNT_REVOKE_URL:
            self.calls.append("revoke")
            return {
                "code": 0,
                "message": "OK",
                "request_id": "phase9-revoke",
                "data": {},
            }
        raise AssertionError("unexpected_fake_provider_post")

    def get(self, url: str, *, headers: Mapping[str, str]) -> Mapping[str, object]:
        del headers
        if url != TIKTOK_ACCOUNT_TOKEN_INFO_URL:
            raise AssertionError("unexpected_fake_provider_get")
        self.calls.append("inspect")
        if self.on_inspect:
            self.on_inspect()
        return {
            "code": 0,
            "message": "OK",
            "request_id": "phase9-info",
            "data": {
                "business_id": self.business_id,
                "scope": list(self.scopes),
            },
        }

    def appears_in(self, value: str) -> bool:
        return self.access_value in value or self.refresh_value in value


@pytest.fixture()
def engine() -> Iterator[Engine]:
    assert DATABASE_URL
    result = create_engine(DATABASE_URL)
    with result.begin() as connection:
        connection.execute(
            text("DELETE FROM linked_social_accounts WHERE brand_id IN (9901, 9902)")
        )
        connection.execute(
            text("DELETE FROM platform_connections WHERE brand_id IN (9901, 9902)")
        )
        connection.execute(
            text("DELETE FROM social_projection_state WHERE projection_key LIKE 'v2:%'")
        )
        connection.execute(text("DELETE FROM brands WHERE id IN (9901, 9902)"))
        connection.execute(text("DELETE FROM tenants WHERE id=9901"))
        connection.execute(
            text("INSERT INTO tenants (id, name, slug) VALUES (9901, 'Phase 9', 'phase9')")
        )
        connection.execute(
            text(
                """INSERT INTO brands (id, tenant_id, name, slug, status, parent_brand_id)
                   VALUES (9901, 9901, 'Phase 9 Primary Brand', 'phase9-primary',
                           'active', NULL),
                          (9902, 9901, 'Phase 9 Secondary Brand', 'phase9-secondary',
                           'active', 9901)"""
            )
        )
    yield result
    result.dispose()


def _drain_outbox(engine: Engine) -> tuple[ProjectionStateStore, dict[str, int]]:
    fixture = json.loads(OUTBOX.read_text(encoding="utf-8"))
    store = ProjectionStateStore(engine=engine)
    secret = secrets.token_urlsafe(40)
    applied_watermark = 0
    duplicate_acknowledged = 0
    snapshot_applied = 0
    for row in fixture["events"]:
        body = json.dumps(row["event"], separators=(",", ":"), sort_keys=True).encode()
        timestamp = str(int(datetime.now(UTC).timestamp()))
        nonce = secrets.token_hex(16)
        signed = SignedRequest(
            timestamp=timestamp,
            nonce=nonce,
            signature=sign_request(secret, "POST", PATH, timestamp, nonce, body),
        )
        status = apply_signed_event(
            secret=secret,
            method="POST",
            path=PATH,
            body=body,
            signed=signed,
            store=store,
        )
        if status not in {"applied", "duplicate_ignored", "stale_ignored"}:
            raise AssertionError("outbox_event_not_acknowledged")
        applied_watermark = int(row["sequence"])
        if applied_watermark == fixture["snapshot_sequence"]:
            snapshot_applied = applied_watermark
        if applied_watermark == 2:
            replay_nonce = secrets.token_hex(16)
            replay_signed = SignedRequest(
                timestamp=timestamp,
                nonce=replay_nonce,
                signature=sign_request(
                    secret,
                    "POST",
                    PATH,
                    timestamp,
                    replay_nonce,
                    body,
                ),
            )
            replay = apply_signed_event(
                secret=secret,
                method="POST",
                path=PATH,
                body=body,
                signed=replay_signed,
                store=store,
            )
            duplicate_acknowledged += int(replay == "duplicate_ignored")
    return store, {
        "applied": applied_watermark,
        "duplicate_acknowledged": duplicate_acknowledged,
        "emitted": int(fixture["emitted_watermark"]),
        "snapshot_applied": snapshot_applied,
    }


def _config() -> TikTokConfig:
    return TikTokConfig(
        provider_profile=TIKTOK_PROVIDER_PROFILE,
        app_id=TIKTOK_APP_ID,
        app_secret=secrets.token_urlsafe(40),
        account_enabled=True,
        oauth_mode="manual_intent_only",
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
        redirect_uri=TIKTOK_REDIRECT_URI,
        activation_link_base=TIKTOK_ACTIVATION_LINK_BASE,
    )


def _coordinator(
    *,
    engine: Engine,
    authority_store: ProjectionStateStore,
    transport: FakeActivationTransport,
    gate_active: bool = True,
    gate_enabled_at: datetime | None = None,
) -> tuple[TikTokActivationCoordinator, ProjectionCredentialStore]:
    config = _config()
    policy = WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True)
    checkpoint = ProjectionCheckpointStore(engine, policy)
    vault = AesGcmTokenVault(
        active_key_id="phase9-runtime-key",
        keys={"phase9-runtime-key": secrets.token_bytes(32)},
    )
    credentials = ProjectionCredentialStore(engine, policy, vault)
    version = activation_config_version(config)
    coordinator = TikTokActivationCoordinator(
        gate=ActivationGate(
            active=gate_active,
            config_version=version,
            expected_config_version=version,
            enabled_at=gate_enabled_at or datetime.now(UTC) - timedelta(minutes=1),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
        write_policy=policy,
        requested_scopes=(*TIKTOK_REQUIRED_SCOPES, TIKTOK_OPTIONAL_SCOPES[0]),
        required_scopes=TIKTOK_REQUIRED_SCOPES,
        optional_scopes=TIKTOK_OPTIONAL_SCOPES,
        intent_store=ProjectionTikTokActivationStore(engine, policy),
        state_port=TikTokActivationStateAdapter(
            TikTokStateCodec(secret=secrets.token_bytes(32), replay_store=checkpoint)
        ),
        provider=TikTokAccountsActivationProvider(config=config, transport=transport),
        credential_store=credentials,
        link_store=ProjectionTikTokActivationStore(engine, policy),
        authority=ProjectionActivationAuthority(authority_store),
    )
    return coordinator, credentials


def _owner_token(secret: str) -> str:
    now = datetime.now(UTC)
    contract = {
        "version": "v1",
        "issued_at": now.isoformat(),
        "user_id": "phase9-owner",
        "email": "owner@example.test",
        "brand_id": 9901,
        "brand_status": "active",
        "role": "agency_admin",
        "platform_role": "agency_admin",
        "effective_role": "agency_admin",
        "app_id": "social_media",
        "entitlement_status": "enabled",
        "access_mode": "write",
        "access_start_at": None,
        "access_expires_at": None,
        "allowed_apps": ["social_media"],
        "is_internal_staff": True,
        "settings_visible": True,
        "platform_branch_scope_mode": "all",
        "platform_branches": [],
    }
    claims = {
        "sub": "phase9-owner",
        "aud": "social_media",
        "token_type": "app_sso",
        "jti": secrets.token_urlsafe(24),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "launch_target": "tiktok_owner_activation",
        "sso_contract": contract,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def _context(*, consumed_at: datetime | None = None) -> ActivationContext:
    return ActivationContext(
        user_id="phase9-owner",
        brand_id=9901,
        session_binding=sha256_text(secrets.token_urlsafe(32)),
        sso_jti_hash=sha256_text(secrets.token_urlsafe(32)),
        sso_consumed_at=consumed_at or datetime.now(UTC),
    )


def test_outbox_watermark_full_snapshot_drain_and_replay(engine: Engine) -> None:
    store, watermark = _drain_outbox(engine)
    assert watermark == {
        "applied": 5,
        "duplicate_acknowledged": 1,
        "emitted": 5,
        "snapshot_applied": 4,
    }
    access = store.list_projections("v2:brand-access:phase9-owner:")
    assert {row["brand_id"] for row in access if row["active"]} == {"9901", "9902"}
    updated = store.get_projection("v2:brand-shell:9902")
    assert updated is not None
    assert updated["name"] == "Phase 9 Secondary Brand Updated"


@pytest.mark.asyncio
async def test_fake_owner_activation_end_to_end_after_projection_drain(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_store, watermark = _drain_outbox(engine)
    assert watermark["applied"] == watermark["emitted"]
    scopes = (*TIKTOK_REQUIRED_SCOPES, TIKTOK_OPTIONAL_SCOPES[0])
    transport = FakeActivationTransport(scopes=scopes)
    coordinator, credentials = _coordinator(
        engine=engine,
        authority_store=authority_store,
        transport=transport,
    )
    assert DATABASE_URL
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SOCIAL_RUNTIME_MODE", "development")
    monkeypatch.setenv("SOCIAL_WRITES_ENABLED", "true")
    monkeypatch.setenv("SOCIAL_DB_URL", DATABASE_URL)
    application = create_app(
        authority_store,
        EmptyReporting(),
        tiktok_activation=coordinator,
    )

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
        follow_redirects=False,
    ) as anonymous:
        prefetched = await anonymous.get(
            "/api/settings/tiktok/activation-readiness",
            params={"brand_id": "9901"},
        )
    assert prefetched.status_code == 401
    assert transport.calls == []

    with pytest.raises(TikTokActivationError, match="activation_authority_denied"):
        coordinator.start(_context(consumed_at=datetime.now(UTC) - timedelta(minutes=2)))
    assert transport.calls == []

    future_gate, _ = _coordinator(
        engine=engine,
        authority_store=authority_store,
        transport=transport,
        gate_enabled_at=datetime.now(UTC) + timedelta(seconds=1),
    )
    with pytest.raises(TikTokActivationError, match="activation_disabled"):
        future_gate.start(_context())
    assert transport.calls == []

    sso_secret = secrets.token_urlsafe(40)
    raw_session, _ = consume_sso(
        _owner_token(sso_secret),
        sso_secret,
        authority_store,
    )
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
        cookies={COOKIE_NAME: raw_session},
        follow_redirects=False,
    ) as browser:
        ready = await browser.get(
            "/api/settings/tiktok/activation-readiness",
            params={"brand_id": "9901"},
        )
        assert ready.status_code == 200
        assert ready.json()["oauth_start_available"] is True
        started = await browser.post(
            "/api/settings/tiktok/oauth/account/start",
            headers={"Origin": "http://test"},
        )
        assert started.status_code == 303
        state_values = parse_qs(urlparse(started.headers["location"]).query).get("state")
        if not state_values or len(state_values) != 1:
            pytest.fail("authorization_state_missing")
        callback = await browser.get(
            "/api/social/tiktok/oauth/callback",
            params={"auth_code": secrets.token_urlsafe(24), "state": state_values[0]},
        )
        assert callback.status_code == 303
        calls_after_success = len(transport.calls)
        replay = await browser.get(
            "/api/social/tiktok/oauth/callback",
            params={"auth_code": secrets.token_urlsafe(24), "state": state_values[0]},
        )
        assert replay.status_code == 400
        assert len(transport.calls) == calls_after_success

    assert transport.calls == ["exchange", "inspect"]
    with engine.connect() as connection:
        link = connection.execute(
            text(
                """SELECT l.id, l.connection_id, l.status, p.status AS connection_status,
                          p.access_token_enc, p.refresh_token_enc
                   FROM linked_social_accounts l
                   JOIN platform_connections p ON p.id=l.connection_id
                   WHERE l.brand_id=9901 AND l.platform='tiktok'"""
            )
        ).mappings().one()
        other_brand_count = connection.execute(
            text(
                """SELECT count(*) FROM linked_social_accounts
                   WHERE brand_id=9902 AND platform='tiktok'"""
            )
        ).scalar_one()
        association = connection.execute(
            text(
                """SELECT payload_json FROM social_projection_state
                   WHERE projection_key=:key"""
            ),
            {"key": f"v2:tiktok:connection-credential:{link['connection_id']}"},
        ).scalar_one()
        sealed_payloads = connection.execute(
            text(
                """SELECT payload_json::text FROM social_projection_state
                   WHERE projection_key LIKE 'v2:credential:tiktok:%'"""
            )
        ).scalars().all()
    assert link["status"] == link["connection_status"] == "pending_verification"
    assert link["access_token_enc"] is None and link["refresh_token_enc"] is None
    assert other_brand_count == 0
    assert association["brand_id"] == 9901
    assert all(not transport.appears_in(payload) for payload in sealed_payloads)
    reference = str(association["credential_reference"])
    assert credentials.get(
        CredentialRef(PlatformId.TIKTOK, reference, TokenKind.ACCESS)
    ) is not None
    assert credentials.get(
        CredentialRef(PlatformId.TIKTOK, reference, TokenKind.REFRESH)
    ) is not None


def test_access_revoke_between_exchange_and_persistence_discards_token(engine: Engine) -> None:
    authority_store, _ = _drain_outbox(engine)

    def revoke_access() -> None:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET payload_json=payload_json || jsonb_build_object('active', false)
                       WHERE projection_key='v2:brand-access:phase9-owner:9901'"""
                )
            )

    transport = FakeActivationTransport(
        scopes=(*TIKTOK_REQUIRED_SCOPES, TIKTOK_OPTIONAL_SCOPES[0]),
        on_inspect=revoke_access,
    )
    coordinator, _ = _coordinator(
        engine=engine,
        authority_store=authority_store,
        transport=transport,
    )
    context = _context()
    started = coordinator.start(context)
    state_values = parse_qs(urlparse(started.authorization_url).query).get("state")
    if not state_values:
        pytest.fail("authorization_state_missing")
    with pytest.raises(TikTokActivationError, match="activation_authority_denied"):
        coordinator.complete(
            query={"auth_code": secrets.token_urlsafe(24), "state": state_values[0]},
            context=context,
        )
    assert transport.calls == ["exchange", "inspect", "revoke"]
    with engine.connect() as connection:
        links = connection.execute(
            text(
                """SELECT count(*) FROM linked_social_accounts
                   WHERE brand_id=9901 AND platform='tiktok'"""
            )
        ).scalar_one()
        credentials = connection.execute(
            text(
                """SELECT count(*) FROM social_projection_state
                   WHERE projection_key LIKE 'v2:credential:tiktok:%'"""
            )
        ).scalar_one()
    assert links == credentials == 0


def test_missing_required_scope_revokes_without_credential_or_link(engine: Engine) -> None:
    authority_store, _ = _drain_outbox(engine)
    transport = FakeActivationTransport(scopes=TIKTOK_REQUIRED_SCOPES[:-1])
    coordinator, _ = _coordinator(
        engine=engine,
        authority_store=authority_store,
        transport=transport,
    )
    context = _context()
    started = coordinator.start(context)
    state_values = parse_qs(urlparse(started.authorization_url).query).get("state")
    if not state_values:
        pytest.fail("authorization_state_missing")
    with pytest.raises(TikTokActivationError, match="activation_scope_denied"):
        coordinator.complete(
            query={"auth_code": secrets.token_urlsafe(24), "state": state_values[0]},
            context=context,
        )
    assert transport.calls == ["exchange", "inspect", "revoke"]
    with engine.connect() as connection:
        links = connection.execute(
            text(
                """SELECT count(*) FROM linked_social_accounts
                   WHERE brand_id=9901 AND platform='tiktok'"""
            )
        ).scalar_one()
        credentials = connection.execute(
            text(
                """SELECT count(*) FROM social_projection_state
                   WHERE projection_key LIKE 'v2:credential:tiktok:%'"""
            )
        ).scalar_one()
    assert links == credentials == 0


@pytest.mark.asyncio
async def test_production_defaults_and_missing_coordinator_have_zero_provider_egress(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_store, _ = _drain_outbox(engine)
    transport = FakeActivationTransport(scopes=TIKTOK_REQUIRED_SCOPES)
    coordinator, _ = _coordinator(
        engine=engine,
        authority_store=authority_store,
        transport=transport,
        gate_active=False,
    )
    with pytest.raises(TikTokActivationError, match="activation_disabled"):
        coordinator.start(_context())
    assert transport.calls == []

    active_coordinator, _ = _coordinator(
        engine=engine,
        authority_store=authority_store,
        transport=transport,
    )
    with pytest.raises(TikTokActivationError, match="activation_callback_rejected"):
        active_coordinator.complete(
            query={"auth_code": secrets.token_urlsafe(24), "state": "invalid-state"},
            context=_context(),
        )
    assert transport.calls == []

    monkeypatch.delenv("SOCIAL_TIKTOK_ACCOUNT_ENABLED", raising=False)
    monkeypatch.delenv("SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE", raising=False)
    monkeypatch.delenv("SOCIAL_TIKTOK_COLLECTION_ENABLED", raising=False)
    monkeypatch.delenv("SOCIAL_TIKTOK_ADVERTISER_ENABLED", raising=False)
    settings = load_settings()
    assert settings.tiktok.account_enabled is False
    assert settings.tiktok.oauth_mode == "disabled"
    assert settings.tiktok.collection_enabled is False
    assert settings.tiktok.advertiser_enabled is False

    application = create_app(authority_store, EmptyReporting())
    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
        follow_redirects=False,
    ) as browser:
        blocked = await browser.post(
            "/api/settings/tiktok/oauth/account/start",
            headers={"Origin": "http://test"},
        )
    assert blocked.status_code == 503
    assert transport.calls == []

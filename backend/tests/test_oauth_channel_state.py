from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application.ports import ActivationContext
from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.domain.platforms import PlatformId
from app.infrastructure.providers.oauth_state import (
    OAuthActivationStateAdapter,
    OAuthStateCodec,
    OAuthStateError,
)

NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


class ReplayStore:
    def __init__(self) -> None:
        self.claimed: set[tuple[CheckpointKey, str]] = set()

    def get(self, key: CheckpointKey) -> ProviderCheckpoint | None:
        return None

    def put(
        self, checkpoint: ProviderCheckpoint, *, expected_version: int | None
    ) -> bool:
        return True

    def claim_once(self, key: CheckpointKey, operation_id: str, expires_at: datetime) -> bool:
        claim = (key, operation_id)
        if claim in self.claimed:
            return False
        self.claimed.add(claim)
        return True


def _context(brand_id: int = 17) -> ActivationContext:
    return ActivationContext(
        user_id="owner-1",
        brand_id=brand_id,
        session_binding="a" * 64,
        sso_jti_hash="b" * 64,
        sso_consumed_at=NOW,
    )


def _adapter(
    platform: PlatformId, store: ReplayStore | None = None
) -> OAuthActivationStateAdapter:
    return OAuthActivationStateAdapter(
        OAuthStateCodec(
            platform=platform,
            provider_profile=f"{platform.value}_oauth_v1",
            redirect_uri=f"https://social.example.test/api/social/{platform.value}/oauth/callback",
            secret=b"state-secret-that-is-at-least-32-bytes",
            replay_store=store or ReplayStore(),
            clock=lambda: NOW,
        )
    )


def test_oauth_channel_state_is_bound_and_single_use() -> None:
    adapter = _adapter(PlatformId.YOUTUBE)
    context = _context()
    token = adapter.issue(
        intent_hash="c" * 64,
        context=context,
        expires_at=NOW + timedelta(minutes=15),
    )

    assert adapter.verified_brand_id(token) == 17
    claims = adapter.consume(token, expected_context=context)
    assert claims.context == context
    assert claims.intent_hash == "c" * 64
    with pytest.raises(OAuthStateError, match="^oauth_state_replayed$"):
        adapter.consume(token, expected_context=context)


def test_oauth_channel_state_rejects_other_brand_and_provider() -> None:
    token = _adapter(PlatformId.YOUTUBE).issue(
        intent_hash="c" * 64,
        context=_context(),
        expires_at=NOW + timedelta(minutes=15),
    )

    with pytest.raises(OAuthStateError, match="^oauth_state_binding_mismatch$"):
        _adapter(PlatformId.YOUTUBE).consume(token, expected_context=_context(brand_id=18))
    with pytest.raises(OAuthStateError, match="^oauth_state_binding_invalid$"):
        _adapter(PlatformId.LINKEDIN).verified_brand_id(token)


def test_oauth_channel_state_rejects_tampering_and_expiry() -> None:
    adapter = _adapter(PlatformId.X)
    token = adapter.issue(
        intent_hash="c" * 64,
        context=_context(),
        expires_at=NOW + timedelta(minutes=15),
    )

    body, signature = token.split(".", 1)
    changed_first = "A" if signature[0] != "A" else "B"
    with pytest.raises(OAuthStateError, match="^oauth_state_signature_invalid$"):
        adapter.verified_brand_id(f"{body}.{changed_first}{signature[1:]}")

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    final_index = alphabet.index(signature[-1])
    assert final_index % 4 == 0
    equivalent_noncanonical = alphabet[final_index + 1]
    with pytest.raises(OAuthStateError, match="^oauth_state_signature_invalid$"):
        adapter.verified_brand_id(f"{body}.{signature[:-1]}{equivalent_noncanonical}")

    expired = OAuthActivationStateAdapter(
        OAuthStateCodec(
            platform=PlatformId.X,
            provider_profile="x_oauth_v1",
            redirect_uri="https://social.example.test/api/social/x/oauth/callback",
            secret=b"state-secret-that-is-at-least-32-bytes",
            replay_store=ReplayStore(),
            clock=lambda: NOW + timedelta(hours=1),
        )
    )
    with pytest.raises(OAuthStateError, match="^oauth_state_expired$"):
        expired.verified_brand_id(token)


@pytest.mark.parametrize("platform", (PlatformId.FACEBOOK, PlatformId.TIKTOK))
def test_oauth_channel_state_rejects_existing_provider_families(
    platform: PlatformId,
) -> None:
    with pytest.raises(ValueError, match="^oauth_channel_platform_invalid$"):
        OAuthStateCodec(
            platform=platform,
            provider_profile="invalid_oauth_v1",
            redirect_uri="https://social.example.test/callback",
            secret=b"state-secret-that-is-at-least-32-bytes",
            replay_store=ReplayStore(),
        )

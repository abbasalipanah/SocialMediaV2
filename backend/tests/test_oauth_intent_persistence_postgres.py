from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, create_engine, text

from app.application.ports import ActivationContext, ActivationIntent
from app.core import RuntimeMode, WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.oauth_intents import ProjectionOAuthIntentStore

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured"
)
NOW = datetime(2026, 8, 31, 12, tzinfo=UTC)


@pytest.fixture()
def engine() -> Iterator[Engine]:
    assert DATABASE_URL
    value = create_engine(DATABASE_URL)
    with value.begin() as connection:
        connection.execute(text("TRUNCATE TABLE social_projection_state"))
    yield value
    value.dispose()


def test_oauth_intent_is_consumed_once_and_bound_to_platform(engine: Engine) -> None:
    store = ProjectionOAuthIntentStore(
        engine,
        WritePolicy(RuntimeMode.DEVELOPMENT, True),
        PlatformId.YOUTUBE,
    )
    context = ActivationContext(
        user_id="owner-1",
        brand_id=17,
        session_binding="a" * 64,
        sso_jti_hash="b" * 64,
        sso_consumed_at=NOW,
    )
    intent = ActivationIntent(
        reference_hash="c" * 64,
        context=context,
        requested_scopes=("channel.read",),
        redirect_uri="https://social.example.test/api/social/youtube/oauth/callback",
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=15),
        leased_at=NOW,
    )

    assert store.create_and_lease(intent) is True
    assert store.create_and_lease(intent) is False
    consumed = store.consume(
        reference_hash=intent.reference_hash,
        expected_context=context,
        consumed_at=NOW + timedelta(minutes=1),
    )

    assert consumed is not None
    assert consumed.consumed_at == NOW + timedelta(minutes=1)
    assert (
        store.consume(
            reference_hash=intent.reference_hash,
            expected_context=context,
            consumed_at=NOW + timedelta(minutes=2),
        )
        is None
    )

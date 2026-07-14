from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, create_engine, text

from app.core.config import RuntimeMode
from app.core.write_policy import WritePolicy
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.providers.tiktok.accounts import (
    TikTokStateBinding,
    TikTokStateCodec,
    TikTokStateError,
)

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")
NOW = datetime.now(UTC)
SESSION_BINDING = hashlib.sha256(b"postgres-fixture-session").hexdigest()


@pytest.fixture()
def engine() -> Iterator[Engine]:
    assert DATABASE_URL
    result = create_engine(DATABASE_URL)
    with result.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS social_projection_state"))
        connection.execute(
            text(
                """CREATE TABLE social_projection_state (
                       projection_key varchar(512) PRIMARY KEY,
                       payload_json jsonb NOT NULL,
                       updated_at timestamptz NOT NULL DEFAULT now()
                   )"""
            )
        )
    yield result
    with result.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS social_projection_state"))
    result.dispose()


def test_tiktok_state_replay_claim_is_durable_in_postgres(engine: Engine) -> None:
    policy = WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True)
    codec = TikTokStateCodec(
        secret=b"s" * 32,
        replay_store=ProjectionCheckpointStore(engine, policy, clock=lambda: NOW),
        clock=lambda: NOW,
    )
    token = codec.issue(
        TikTokStateBinding(
            nonce="postgres-nonce-fixture-1234",
            user_id="user-1",
            brand_id=7,
            session_binding=SESSION_BINDING,
            expires_at=NOW + timedelta(minutes=5),
        )
    )
    assert (
        codec.consume(
            token,
            expected_user_id="user-1",
            expected_brand_id=7,
            expected_session_binding=SESSION_BINDING,
        ).brand_id
        == 7
    )
    with pytest.raises(TikTokStateError, match="state_replayed"):
        TikTokStateCodec(
            secret=b"s" * 32,
            replay_store=ProjectionCheckpointStore(engine, policy, clock=lambda: NOW),
            clock=lambda: NOW,
        ).consume(
            token,
            expected_user_id="user-1",
            expected_brand_id=7,
            expected_session_binding=SESSION_BINDING,
        )
    with engine.connect() as connection:
        claims = connection.execute(
            text(
                """SELECT count(*) FROM social_projection_state
                   WHERE projection_key LIKE 'v2:checkpoint-once:%'"""
            )
        ).scalar_one()
    assert claims == 1

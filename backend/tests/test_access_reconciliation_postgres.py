from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text

from app.core import RuntimeMode, WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.access_reconciliation import (
    AccessReconciliationError,
    AccountAccessReconciliationStore,
    ExactAccountRef,
)

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")


@pytest.fixture()
def engine() -> Iterator[Engine]:
    assert DATABASE_URL
    value = create_engine(DATABASE_URL)
    _drop(value)
    with value.begin() as connection:
        for statement in _schema():
            connection.execute(text(statement))
        for statement in _seed():
            connection.execute(text(statement))
    yield value
    _drop(value)
    value.dispose()


def _store(engine: Engine) -> AccountAccessReconciliationStore:
    return AccountAccessReconciliationStore(
        engine,
        WritePolicy(runtime_mode=RuntimeMode.STAGING, writes_enabled=True),
    )


def _targets() -> tuple[ExactAccountRef, ...]:
    return (
        ExactAccountRef(31, 101, PlatformId.FACEBOOK, "page-1"),
        ExactAccountRef(33, 102, PlatformId.FACEBOOK, "page-2"),
        ExactAccountRef(34, 103, PlatformId.TIKTOK, "business-1"),
    )


def test_dry_run_predicts_connection_states_without_writes(engine: Engine) -> None:
    results = _store(engine).reconcile(
        _targets(),
        reason="access_disconnected",
        apply=False,
        revoke_tiktok_credentials=True,
    )

    assert {result.connection_id: result.next_connection_status for result in results} == {
        91: "connected",
        92: "disconnected",
        93: "disconnected",
    }
    assert all(not result.applied for result in results)
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT status FROM linked_social_accounts WHERE id=31")
        ).scalar_one() == "connected"
        assert connection.execute(
            text(
                "SELECT payload_json->>'revoked' FROM social_projection_state "
                "WHERE projection_key='v2:credential:tiktok:reference-1:refresh'"
            )
        ).scalar_one() == "false"


def test_apply_preserves_sibling_and_history_but_removes_targets(engine: Engine) -> None:
    results = _store(engine).reconcile(
        _targets(),
        reason="reauthorization_required",
        apply=True,
        revoke_tiktok_credentials=True,
    )

    assert all(result.applied for result in results)
    with engine.connect() as connection:
        assert dict(
            connection.execute(
                text("SELECT id, status FROM platform_connections ORDER BY id")
            ).all()
        ) == {91: "connected", 92: "disconnected", 93: "disconnected"}
        assert dict(
            connection.execute(
                text("SELECT id, status FROM linked_social_accounts ORDER BY id")
            ).all()
        ) == {
            31: "disconnected",
            32: "connected",
            33: "disconnected",
            34: "disconnected",
        }
        assert dict(
            connection.execute(text("SELECT id, status FROM assets ORDER BY id")).all()
        ) == {11: "inactive", 12: "active", 13: "inactive", 14: "inactive"}
        assert dict(
            connection.execute(
                text("SELECT id, status FROM brand_social_account_discoveries ORDER BY id")
            ).all()
        ) == {21: "available", 22: "linked", 23: "available"}
        assert connection.execute(
            text("SELECT count(*) FROM metrics_daily")
        ).scalar_one() == 3
        assert connection.execute(
            text(
                """SELECT bool_and((payload_json->>'revoked')::boolean)
                   FROM social_projection_state
                   WHERE projection_key LIKE 'v2:credential:tiktok:reference-1:%'"""
            )
        ).scalar_one() is True
        assert dict(
            connection.execute(
                text(
                    """SELECT projection_key, status
                       FROM social_projection_state
                       WHERE projection_key IN (
                         'v2:meta:connection:91',
                         'v2:meta:connection:92',
                         'v2:tiktok:connection-credential:93'
                       )
                       ORDER BY projection_key"""
                )
            ).all()
        ) == {
            "v2:meta:connection:91": "active",
            "v2:meta:connection:92": "inactive",
            "v2:tiktok:connection-credential:93": "inactive",
        }


def test_tiktok_credentials_cannot_be_revoked_while_a_sibling_remains_active(
    engine: Engine,
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO assets VALUES "
                "(15, 103, 'tiktok', 'business-2', 'active', now())"
            )
        )
        connection.execute(
            text(
                "INSERT INTO linked_social_accounts VALUES "
                "(35, 103, 'tiktok', 'business-2', 93, 15, "
                "'connected', 'healthy', true, now())"
            )
        )

    with pytest.raises(
        AccessReconciliationError,
        match="^tiktok_credential_connection_still_active$",
    ):
        _store(engine).reconcile(
            (ExactAccountRef(34, 103, PlatformId.TIKTOK, "business-1"),),
            reason="reauthorization_required",
            apply=True,
            revoke_tiktok_credentials=True,
        )

    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT status FROM linked_social_accounts WHERE id=34")
        ).scalar_one() == "connected"
        assert connection.execute(
            text(
                "SELECT payload_json->>'revoked' FROM social_projection_state "
                "WHERE projection_key='v2:credential:tiktok:reference-1:access'"
            )
        ).scalar_one() == "false"


def _drop(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in (
            "metrics_daily",
            "asset_sync_state",
            "brand_social_account_discoveries",
            "linked_social_accounts",
            "assets",
            "platform_connections",
            "social_projection_state",
        ):
            connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))


def _schema() -> tuple[str, ...]:
    return (
        """CREATE TABLE platform_connections (
               id bigint PRIMARY KEY, brand_id bigint NOT NULL,
               platform varchar(32) NOT NULL, status varchar(64) NOT NULL,
               updated_at timestamptz NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE assets (
               id bigint PRIMARY KEY, brand_id bigint NOT NULL,
               platform varchar(32) NOT NULL, external_id varchar(255) NOT NULL,
               status varchar(64) NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE linked_social_accounts (
               id bigint PRIMARY KEY, brand_id bigint NOT NULL,
               platform varchar(32) NOT NULL, external_id varchar(255) NOT NULL,
               connection_id bigint NOT NULL, asset_id bigint NOT NULL,
               status varchar(64) NOT NULL, health_status varchar(64) NOT NULL,
               nightly_enabled boolean NOT NULL,
               updated_at timestamptz NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE brand_social_account_discoveries (
               id bigint PRIMARY KEY, brand_id bigint NOT NULL,
               platform varchar(32) NOT NULL, external_id varchar(255) NOT NULL,
               status varchar(64) NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE asset_sync_state (
               asset_id bigint PRIMARY KEY, last_error varchar(1024),
               updated_at timestamptz NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE social_projection_state (
               projection_key varchar(255) PRIMARY KEY,
               status varchar(32) NOT NULL DEFAULT 'active',
               payload_json jsonb NOT NULL,
               updated_at timestamptz NOT NULL DEFAULT now()
           )""",
        """CREATE TABLE metrics_daily (
               id bigint PRIMARY KEY, asset_id bigint NOT NULL, value_numeric numeric NOT NULL
           )""",
    )


def _seed() -> tuple[str, ...]:
    return (
        """INSERT INTO platform_connections VALUES
             (91, 101, 'facebook', 'connected', now()),
             (92, 102, 'facebook', 'connected', now()),
             (93, 103, 'tiktok', 'connected', now())""",
        """INSERT INTO assets VALUES
             (11, 101, 'facebook', 'page-1', 'active', now()),
             (12, 101, 'instagram', 'ig-1', 'active', now()),
             (13, 102, 'facebook', 'page-2', 'active', now()),
             (14, 103, 'tiktok', 'business-1', 'active', now())""",
        """INSERT INTO linked_social_accounts VALUES
             (31, 101, 'facebook', 'page-1', 91, 11, 'connected', 'error', true, now()),
             (32, 101, 'instagram', 'ig-1', 91, 12, 'connected', 'healthy', true, now()),
             (33, 102, 'facebook', 'page-2', 92, 13, 'connected', 'error', true, now()),
             (34, 103, 'tiktok', 'business-1', 93, 14, 'connected', 'error', true, now())""",
        """INSERT INTO brand_social_account_discoveries VALUES
             (21, 101, 'facebook', 'page-1', 'linked', now()),
             (22, 101, 'instagram', 'ig-1', 'linked', now()),
             (23, 102, 'facebook', 'page-2', 'linked', now())""",
        """INSERT INTO asset_sync_state VALUES
             (11, 'old-error', now()), (12, NULL, now()),
             (13, 'old-error', now()), (14, 'old-error', now())""",
        """INSERT INTO social_projection_state VALUES
             ('v2:meta:connection:91', 'active', '{"state":"connected"}', now()),
             ('v2:meta:connection:92', 'active', '{"state":"connected"}', now()),
             ('v2:tiktok:connection-credential:93', 'active',
              '{"state":"connected","credential_reference":"reference-1"}', now()),
             ('v2:credential:tiktok:reference-1:access', 'active',
              jsonb_build_object('revoked', false), now()),
             ('v2:credential:tiktok:reference-1:refresh', 'active',
              jsonb_build_object('revoked', false), now())""",
        """INSERT INTO metrics_daily VALUES
             (1, 11, 1), (2, 13, 2), (3, 14, 3)""",
    )

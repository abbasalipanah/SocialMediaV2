from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text

from app.application.ports import MetaLinkSelection
from app.core import RuntimeMode, WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2 import (
    ProjectionMetaConnectionStore,
    SocialReportingStore,
)

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")

TABLES = (
    "asset_sync_state",
    "linked_social_accounts",
    "brand_social_account_discoveries",
    "assets",
    "meta_accounts",
    "social_projection_state",
    "platform_connections",
    "brands",
)


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


def test_saving_meta_selection_replaces_the_brands_current_accounts(engine: Engine) -> None:
    store = ProjectionMetaConnectionStore(
        engine,
        WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True),
    )

    result = store.link_accounts(
        brand_id=101,
        connection_id=91,
        selections=(MetaLinkSelection(PlatformId.FACEBOOK, "10001"),),
    )

    assert result.linked_count == 1
    assert _states(engine) == {
        ("facebook", "10001"): ("connected", "active", "linked"),
        ("instagram", "20002"): ("disconnected", "inactive", "available"),
    }
    assert [
        (item.platform, item.external_id, item.status)
        for item in store.list_discoveries(brand_id=101)
    ] == [
        (PlatformId.FACEBOOK, "10001", "linked"),
        (PlatformId.INSTAGRAM, "20002", "available"),
    ]
    assert [
        (item.platform, item.external_id)
        for item in SocialReportingStore(engine).list_accounts(brand_ids=("101",))
    ] == [(PlatformId.FACEBOOK, "10001")]

    store.link_accounts(
        brand_id=101,
        connection_id=91,
        selections=(MetaLinkSelection(PlatformId.INSTAGRAM, "20002"),),
    )

    assert _states(engine) == {
        ("facebook", "10001"): ("disconnected", "inactive", "available"),
        ("instagram", "20002"): ("connected", "active", "linked"),
    }


def _states(engine: Engine) -> dict[tuple[str, str], tuple[str, str, str]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """SELECT la.platform, la.external_id, la.status AS link_status,
                          a.status AS asset_status, d.status AS discovery_status
                   FROM linked_social_accounts AS la
                   JOIN assets AS a ON a.id=la.asset_id
                   JOIN brand_social_account_discoveries AS d
                     ON d.brand_id=la.brand_id AND d.platform=la.platform
                    AND d.external_id=la.external_id
                   WHERE la.brand_id=101
                   ORDER BY la.platform"""
            )
        ).mappings()
        return {
            (str(row["platform"]), str(row["external_id"])): (
                str(row["link_status"]),
                str(row["asset_status"]),
                str(row["discovery_status"]),
            )
            for row in rows
        }


def _drop(engine: Engine) -> None:
    with engine.begin() as connection:
        for table in TABLES:
            connection.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))


def _schema() -> tuple[str, ...]:
    return (
        "CREATE TABLE brands (id integer PRIMARY KEY, tenant_id integer NOT NULL)",
        """CREATE TABLE platform_connections (
            id integer PRIMARY KEY, tenant_id integer NOT NULL, brand_id integer NOT NULL,
            platform varchar(32) NOT NULL, status varchar(64) NOT NULL,
            expires_at timestamptz, projected_at timestamptz,
            projection_source varchar(64), updated_at timestamptz NOT NULL DEFAULT now()
        )""",
        """CREATE TABLE meta_accounts (
            id integer PRIMARY KEY, platform varchar(32) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255) NOT NULL,
            status varchar(64) NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
        )""",
        """CREATE TABLE assets (
            id integer PRIMARY KEY, tenant_id integer NOT NULL, brand_id integer NOT NULL,
            platform varchar(32) NOT NULL, asset_type varchar(32) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255) NOT NULL,
            meta_account_id integer, status varchar(64) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (brand_id, platform, external_id)
        )""",
        """CREATE TABLE brand_social_account_discoveries (
            id integer PRIMARY KEY, brand_id integer NOT NULL, connection_id integer NOT NULL,
            meta_account_id integer NOT NULL, platform varchar(32) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255),
            status varchar(32) NOT NULL, updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (brand_id, platform, external_id)
        )""",
        """CREATE TABLE linked_social_accounts (
            id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            brand_id integer NOT NULL, platform varchar(32) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255) NOT NULL,
            connection_id integer, meta_account_id integer, asset_id integer,
            status varchar(64) NOT NULL, health_status varchar(64) NOT NULL,
            backfill_status varchar(64) NOT NULL, nightly_enabled boolean NOT NULL DEFAULT false,
            last_synced_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (brand_id, platform, external_id)
        )""",
        """CREATE TABLE asset_sync_state (
            asset_id integer PRIMARY KEY, last_synced_at timestamptz, last_error varchar(1024)
        )""",
        """CREATE TABLE social_projection_state (
            projection_key varchar(255) PRIMARY KEY, status varchar(32) NOT NULL,
            payload_json jsonb NOT NULL, updated_at timestamptz NOT NULL DEFAULT now()
        )""",
    )


def _seed() -> tuple[str, ...]:
    return (
        "INSERT INTO brands VALUES (101, 1)",
        """INSERT INTO platform_connections VALUES
            (91, 1, 101, 'facebook', 'connected', NULL, now(), 'test', now())""",
        """INSERT INTO meta_accounts VALUES
            (1, 'facebook', '10001', 'Coastal Page', 'active', now()),
            (2, 'instagram', '20002', 'coastal.hotel', 'active', now())""",
        """INSERT INTO assets VALUES
            (11, 1, 101, 'facebook', 'page', '10001', 'Coastal Page', 1, 'active', now(), now()),
            (12, 1, 101, 'instagram', 'profile', '20002', 'coastal.hotel', 2,
             'active', now(), now())""",
        """INSERT INTO brand_social_account_discoveries VALUES
            (21, 101, 91, 1, 'facebook', '10001', 'Coastal Page', 'linked', now()),
            (22, 101, 91, 2, 'instagram', '20002', 'coastal.hotel', 'linked', now())""",
        """INSERT INTO linked_social_accounts VALUES
            (31, 101, 'facebook', '10001', 'Coastal Page', 91, 1, 11,
             'connected', 'healthy', 'complete', true, now(), now(), now()),
            (32, 101, 'instagram', '20002', 'coastal.hotel', 91, 2, 12,
             'connected', 'healthy', 'complete', true, now(), now(), now())""",
        """INSERT INTO social_projection_state VALUES
            ('v2:meta:connection:91', 'active', '{"state":"connected"}'::jsonb, now())""",
    )

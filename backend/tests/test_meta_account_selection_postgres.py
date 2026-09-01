from __future__ import annotations

import os
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import Engine, create_engine, text

from app.application.ports import MetaCredentialBinding, MetaLinkSelection
from app.core import RuntimeMode, WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2 import (
    ProjectionMetaConnectionStore,
    SocialReportingStore,
)

DATABASE_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="TEST_POSTGRES_URL is not configured")

@pytest.fixture()
def engine() -> Iterator[Engine]:
    assert DATABASE_URL
    schema = f"test_meta_selection_{uuid4().hex}"
    database_engine = create_engine(DATABASE_URL)
    with database_engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    value = create_engine(
        DATABASE_URL,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        with value.begin() as connection:
            for statement in _schema():
                connection.execute(text(statement))
            for statement in _seed():
                connection.execute(text(statement))
        yield value
    finally:
        value.dispose()
        with database_engine.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        database_engine.dispose()


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


def test_legacy_links_are_editable_without_discovery_rows(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM brand_social_account_discoveries"))
    store = ProjectionMetaConnectionStore(
        engine,
        WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True),
    )

    assert [
        (item.connection_id, item.platform, item.external_id, item.status)
        for item in store.list_discoveries(brand_id=101)
    ] == [
        (91, PlatformId.FACEBOOK, "10001", "linked"),
        (91, PlatformId.INSTAGRAM, "20002", "linked"),
    ]

    kept_all = store.link_accounts(
        brand_id=101,
        connection_id=91,
        selections=(
            MetaLinkSelection(PlatformId.FACEBOOK, "10001"),
            MetaLinkSelection(PlatformId.INSTAGRAM, "20002"),
        ),
    )
    assert kept_all.linked_count == 2
    assert [
        (item.platform, item.external_id)
        for item in SocialReportingStore(engine).list_accounts(brand_ids=("101",))
    ] == [
        (PlatformId.FACEBOOK, "10001"),
        (PlatformId.INSTAGRAM, "20002"),
    ]

    kept = store.link_accounts(
        brand_id=101,
        connection_id=91,
        selections=(MetaLinkSelection(PlatformId.INSTAGRAM, "20002"),),
    )
    assert kept.linked_count == 1
    assert kept.state == "connected"
    assert [
        (item.platform, item.external_id)
        for item in SocialReportingStore(engine).list_accounts(brand_ids=("101",))
    ] == [(PlatformId.INSTAGRAM, "20002")]

    removed = store.link_accounts(brand_id=101, connection_id=91, selections=())
    assert removed.linked_count == 0
    assert removed.state == "disconnected"
    assert SocialReportingStore(engine).list_accounts(brand_ids=("101",)) == ()
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT status FROM platform_connections WHERE id=91")
        ).scalar_one() == "disconnected"


def test_saved_meta_access_refreshes_all_available_accounts_without_oauth(
    engine: Engine,
) -> None:
    store = ProjectionMetaConnectionStore(
        engine,
        WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True),
    )

    refresh_connection = store.latest_refresh_connection(brand_id=101)
    assert refresh_connection is not None
    assert refresh_connection.connection_id == 91
    assert refresh_connection.user_credential_reference == "saved-user-reference"

    result = store.refresh_discoveries(
        brand_id=101,
        connection_id=91,
        credentials=(
            MetaCredentialBinding(
                PlatformId.FACEBOOK, "10001", "Coastal Page", "page-reference-1"
            ),
            MetaCredentialBinding(
                PlatformId.INSTAGRAM, "20002", "coastal.hotel", "ig-reference-1"
            ),
            MetaCredentialBinding(
                PlatformId.FACEBOOK, "30003", "Mountain Page", "page-reference-2"
            ),
            MetaCredentialBinding(
                PlatformId.INSTAGRAM, "40004", "mountain.hotel", "ig-reference-2"
            ),
        ),
    )

    assert result.facebook_count == 2
    assert result.instagram_count == 2
    assert [
        (item.platform, item.external_id, item.status)
        for item in store.list_discoveries(brand_id=101)
    ] == [
        (PlatformId.FACEBOOK, "10001", "linked"),
        (PlatformId.FACEBOOK, "30003", "available"),
        (PlatformId.INSTAGRAM, "20002", "linked"),
        (PlatformId.INSTAGRAM, "40004", "available"),
    ]
    with engine.connect() as connection:
        payload = connection.execute(
            text(
                "SELECT payload_json FROM social_projection_state "
                "WHERE projection_key='v2:meta:connection:91'"
            )
        ).scalar_one()
    assert len(payload["accounts"]) == 4
    assert payload["last_refreshed_at"]


def test_meta_app_catalog_can_be_mapped_to_a_new_brand(engine: Engine) -> None:
    store = ProjectionMetaConnectionStore(
        engine,
        WritePolicy(runtime_mode=RuntimeMode.DEVELOPMENT, writes_enabled=True),
    )

    assert [
        (item.platform, item.external_id, item.display_name)
        for item in store.list_catalog_accounts(brand_id=202)
    ] == [
        (PlatformId.FACEBOOK, "10001", "Coastal Page"),
        (PlatformId.INSTAGRAM, "20002", "coastal.hotel"),
    ]

    prepared = store.create_catalog_connection(
        brand_id=202,
        selections=(MetaLinkSelection(PlatformId.FACEBOOK, "10001"),),
    )
    linked = store.link_accounts(
        brand_id=202,
        connection_id=prepared.connection_id,
        selections=(MetaLinkSelection(PlatformId.FACEBOOK, "10001"),),
    )

    assert linked.brand_id == 202
    assert linked.linked_count == 1
    assert [
        (item.platform, item.external_id)
        for item in SocialReportingStore(engine).list_accounts(brand_ids=("202",))
    ] == [(PlatformId.FACEBOOK, "10001")]
    with engine.connect() as connection:
        payload = connection.execute(
            text(
                "SELECT payload_json FROM social_projection_state "
                "WHERE projection_key=:key"
            ),
            {"key": f"v2:meta:connection:{prepared.connection_id}"},
        ).scalar_one()
    assert payload["accounts"] == [{
        "platform": "facebook",
        "external_id": "10001",
        "credential_reference": "page-reference-1",
    }]


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


def _schema() -> tuple[str, ...]:
    return (
        "CREATE TABLE brands (id integer PRIMARY KEY, tenant_id integer NOT NULL)",
        """CREATE TABLE platform_connections (
            id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            tenant_id integer NOT NULL, brand_id integer NOT NULL,
            platform varchar(32) NOT NULL, status varchar(64) NOT NULL,
            expires_at timestamptz, projected_at timestamptz,
            projection_source varchar(64), updated_at timestamptz NOT NULL DEFAULT now()
        )""",
        """CREATE TABLE meta_accounts (
            id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            platform varchar(32) NOT NULL, asset_type varchar(32) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255) NOT NULL,
            status varchar(64) NOT NULL, last_discovered_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (platform, external_id)
        )""",
        """CREATE TABLE assets (
            id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            tenant_id integer NOT NULL, brand_id integer NOT NULL,
            platform varchar(32) NOT NULL, asset_type varchar(32) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255) NOT NULL,
            meta_account_id integer, status varchar(64) NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (brand_id, platform, external_id)
        )""",
        """CREATE TABLE brand_social_account_discoveries (
            id integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
            brand_id integer NOT NULL, connection_id integer NOT NULL,
            meta_account_id integer NOT NULL, platform varchar(32) NOT NULL,
            external_id varchar(255) NOT NULL, display_name varchar(255),
            status varchar(32) NOT NULL, last_discovered_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
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
            brand_id integer, projection_source varchar(64) NOT NULL DEFAULT 'test',
            projected_at timestamptz, payload_json jsonb NOT NULL,
            updated_at timestamptz NOT NULL DEFAULT now()
        )""",
    )


def _seed() -> tuple[str, ...]:
    return (
        "INSERT INTO brands VALUES (101, 1), (202, 1)",
        """INSERT INTO platform_connections VALUES
            (91, 1, 101, 'facebook', 'connected', NULL, now(), 'test', now())""",
        "ALTER TABLE platform_connections ALTER COLUMN id RESTART WITH 92",
        """INSERT INTO meta_accounts
            (id, platform, asset_type, external_id, display_name, status,
             last_discovered_at, created_at, updated_at) VALUES
            (1, 'facebook', 'page', '10001', 'Coastal Page', 'active', now(), now(), now()),
            (2, 'instagram', 'profile', '20002', 'coastal.hotel', 'active', now(), now(), now())""",
        "ALTER TABLE meta_accounts ALTER COLUMN id RESTART WITH 3",
        """INSERT INTO assets VALUES
            (11, 1, 101, 'facebook', 'page', '10001', 'Coastal Page', 1, 'active', now(), now()),
            (12, 1, 101, 'instagram', 'profile', '20002', 'coastal.hotel', 2,
             'active', now(), now())""",
        """INSERT INTO brand_social_account_discoveries
            (id, brand_id, connection_id, meta_account_id, platform, external_id,
             display_name, status, last_discovered_at, created_at, updated_at) VALUES
            (21, 101, 91, 1, 'facebook', '10001', 'Coastal Page', 'linked',
             now(), now(), now()),
            (22, 101, 91, 2, 'instagram', '20002', 'coastal.hotel', 'linked',
             now(), now(), now())""",
        "ALTER TABLE brand_social_account_discoveries ALTER COLUMN id RESTART WITH 23",
        """INSERT INTO linked_social_accounts VALUES
            (31, 101, 'facebook', '10001', 'Coastal Page', 91, 1, 11,
             'connected', 'healthy', 'complete', true, now(), now(), now()),
            (32, 101, 'instagram', '20002', 'coastal.hotel', 91, 2, 12,
             'connected', 'healthy', 'complete', true, now(), now(), now())""",
        """INSERT INTO social_projection_state
            (projection_key, status, projected_at, payload_json, updated_at) VALUES
            ('v2:meta:connection:91', 'active', now(),
             '{
               "state": "connected",
               "user_credential_reference": "saved-user-reference",
               "accounts": [
                 {"platform": "facebook", "external_id": "10001",
                  "credential_reference": "page-reference-1"},
                 {"platform": "instagram", "external_id": "20002",
                  "credential_reference": "ig-reference-1"}
               ]
             }'::jsonb,
             now())""",
    )

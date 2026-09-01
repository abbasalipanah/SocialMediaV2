from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping
from typing import Any, cast

from sqlalchemy import Engine

from app.core.config import RuntimeMode
from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.collection_targets import (
    CollectionTargetRow,
    SocialCollectionTargetStore,
)


class _MappingRows:
    def __init__(self, rows: list[Mapping[str, Any]]) -> None:
        self._rows = rows

    def mappings(self) -> _MappingRows:
        return self

    def __iter__(self) -> Iterator[Mapping[str, Any]]:
        return iter(self._rows)


class _Connection:
    def __init__(self, rows: list[Mapping[str, Any]]) -> None:
        self._rows = rows
        self.statement = ""
        self.parameters: Mapping[str, object] = {}

    def __enter__(self) -> _Connection:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def execute(self, statement: object, parameters: Mapping[str, object]) -> _MappingRows:
        self.statement = str(statement)
        self.parameters = parameters
        return _MappingRows(self._rows)


class _Engine:
    def __init__(self, rows: list[Mapping[str, Any]]) -> None:
        self.connection = _Connection(rows)

    def connect(self) -> _Connection:
        return self.connection


def test_list_connected_accepts_legacy_active_and_canonical_connected_statuses() -> None:
    engine = _Engine(
        [
            {
                "link_id": 11,
                "connection_id": 21,
                "asset_id": 31,
                "brand_id": 69,
                "platform": "facebook",
                "external_id": "page-1",
                "display_name": "Page One",
                "backfill_status": "complete",
                "payload_json": {
                    "accounts": [
                        {
                            "platform": "facebook",
                            "external_id": "page-1",
                            "credential_reference": "vault:meta:21",
                        }
                    ]
                },
            }
        ]
    )
    store = SocialCollectionTargetStore(
        cast(Engine, engine),
        WritePolicy(runtime_mode=RuntimeMode.STAGING, writes_enabled=False),
    )

    targets = store.list_connected(platforms=(PlatformId.FACEBOOK,), brand_id=69)

    assert "la.status IN ('active', 'connected')" in engine.connection.statement
    assert "pc.status='connected'" in engine.connection.statement
    assert "pc.brand_id=la.brand_id" in engine.connection.statement
    assert engine.connection.parameters == {"platforms": ["facebook"], "brand_id": 69}
    assert targets == (
        CollectionTargetRow(
            link_id=11,
            connection_id=21,
            asset_id=31,
            brand_id=69,
            platform=PlatformId.FACEBOOK,
            external_id="page-1",
            display_name="Page One",
            credential_reference="vault:meta:21",
            backfill_status="complete",
        ),
    )


def test_list_connected_reads_generic_oauth_projection_for_youtube() -> None:
    engine = _Engine(
        [
            {
                "link_id": 12,
                "connection_id": 22,
                "asset_id": 32,
                "brand_id": 69,
                "platform": "youtube",
                "external_id": "UC-channel",
                "display_name": "Example Channel",
                "backfill_status": "pending",
                "payload_json": {
                    "format_version": 1,
                    "platform": "youtube",
                    "accounts": [
                        {
                            "platform": "youtube",
                            "external_id": "UC-channel",
                            "display_name": "Example Channel",
                            "credential_reference": "vault-youtube-22",
                        }
                    ],
                },
            }
        ]
    )
    store = SocialCollectionTargetStore(
        cast(Engine, engine),
        WritePolicy(runtime_mode=RuntimeMode.STAGING, writes_enabled=False),
    )

    targets = store.list_connected(platforms=(PlatformId.YOUTUBE,), brand_id=69)

    assert targets[0].credential_reference == "vault-youtube-22"
    assert "'v2:oauth:' || la.platform" in engine.connection.statement


def test_new_account_fast_lane_keeps_incomplete_backfills_selected() -> None:
    engine = _Engine([])
    store = SocialCollectionTargetStore(
        cast(Engine, engine),
        WritePolicy(runtime_mode=RuntimeMode.STAGING, writes_enabled=False),
    )

    store.list_connected(
        platforms=(PlatformId.INSTAGRAM,),
        only_new=True,
    )

    assert "la.last_synced_at IS NULL" in engine.connection.statement
    assert "lower(la.backfill_status) NOT IN ('complete', 'completed')" in (
        engine.connection.statement
    )


def test_list_connected_skips_only_invalid_meta_target(caplog: Any) -> None:
    engine = _Engine(
        [
            {
                "link_id": 57,
                "connection_id": 47,
                "asset_id": 2819,
                "brand_id": 286189,
                "platform": "instagram",
                "external_id": "17841471029369177",
                "display_name": "CTG Elektrik",
                "backfill_status": "error",
                "payload_json": {"accounts": []},
            },
            {
                "link_id": 13,
                "connection_id": 12,
                "asset_id": 2636,
                "brand_id": 73,
                "platform": "instagram",
                "external_id": "17841401178603358",
                "display_name": "Turk Eximbank",
                "backfill_status": "complete",
                "payload_json": {
                    "accounts": [
                        {
                            "platform": "instagram",
                            "external_id": "17841401178603358",
                            "credential_reference": "vault:meta:12",
                        }
                    ]
                },
            },
        ]
    )
    store = SocialCollectionTargetStore(
        cast(Engine, engine),
        WritePolicy(runtime_mode=RuntimeMode.STAGING, writes_enabled=False),
    )

    with caplog.at_level(logging.WARNING):
        targets = store.list_connected(platforms=(PlatformId.INSTAGRAM,))

    assert [target.link_id for target in targets] == [13]
    assert "social_collection_target_skipped link_id=57" in caplog.text
    assert "meta_connection_payload_invalid" in caplog.text

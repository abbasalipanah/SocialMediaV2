from __future__ import annotations

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

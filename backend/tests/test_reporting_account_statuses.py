from __future__ import annotations

from datetime import UTC, datetime

from app.domain.platforms import PlatformId
from app.infrastructure.persistence.social_v2.reporting import (
    _REPORTABLE_ASSET_STATUSES,
    SocialReportingStore,
)


class _Rows:
    def mappings(self):
        return iter(
            (
                {
                    "id": 2862,
                    "brand_id": "18",
                    "platform": "tiktok",
                    "external_id": "business-account",
                    "display_name": "Pine Beach Belek",
                    "status": "limited",
                    "connection_state": "connected",
                    "link_status": "active",
                    "health_status": "healthy",
                    "backfill_status": "ready",
                    "nightly_enabled": True,
                    "last_synced_at": datetime(2026, 8, 25, tzinfo=UTC),
                },
            )
        )


class _Connection:
    def __init__(self) -> None:
        self.parameters: dict[str, object] = {}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, _statement, parameters):
        self.parameters = parameters
        return _Rows()


class _Engine:
    def __init__(self) -> None:
        self.connection = _Connection()

    def connect(self):
        return self.connection


def test_limited_migrated_asset_is_included_in_reporting_scope() -> None:
    engine = _Engine()
    store = SocialReportingStore(engine)  # type: ignore[arg-type]

    accounts = store.list_accounts(brand_ids=("18",), platform=PlatformId.TIKTOK)

    assert tuple(account.account_id for account in accounts) == (2862,)
    assert engine.connection.parameters["asset_statuses"] == ("active", "limited")
    assert _REPORTABLE_ASSET_STATUSES == ("active", "limited")

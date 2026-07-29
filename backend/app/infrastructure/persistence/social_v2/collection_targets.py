"""V2-owned worker target selection and sync-state updates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine, text

from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId


@dataclass(frozen=True)
class CollectionTargetRow:
    link_id: int
    connection_id: int
    asset_id: int
    brand_id: int
    platform: PlatformId
    external_id: str
    display_name: str
    credential_reference: str
    backfill_status: str


@dataclass(frozen=True)
class PendingTikTokTarget:
    link_id: int
    connection_id: int
    brand_id: int
    external_id: str
    display_name: str
    credential_reference: str


class SocialCollectionTargetStore:
    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        self.engine = engine
        self._write_policy = write_policy

    def list_connected(
        self,
        *,
        platforms: tuple[PlatformId, ...],
        brand_id: int | None = None,
        asset_id: int | None = None,
    ) -> tuple[CollectionTargetRow, ...]:
        if not platforms:
            return ()
        clauses = [
            "la.status='connected'",
            "pc.status='connected'",
            "la.asset_id IS NOT NULL",
            "la.platform = ANY(:platforms)",
        ]
        parameters: dict[str, object] = {
            "platforms": [platform.value for platform in platforms]
        }
        if brand_id is not None:
            clauses.append("la.brand_id=:brand_id")
            parameters["brand_id"] = brand_id
        if asset_id is not None:
            clauses.append("la.asset_id=:asset_id")
            parameters["asset_id"] = asset_id
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    f"""SELECT la.id AS link_id, la.connection_id, la.asset_id,
                               la.brand_id, la.platform, la.external_id,
                               COALESCE(
                                   NULLIF(la.display_name, ''), la.external_id
                               ) AS display_name,
                               la.backfill_status, ps.payload_json
                        FROM linked_social_accounts AS la
                        JOIN platform_connections AS pc ON pc.id=la.connection_id
                        JOIN social_projection_state AS ps
                          ON ps.projection_key=CASE
                            WHEN la.platform='tiktok'
                              THEN 'v2:tiktok:connection-credential:' || la.connection_id
                            ELSE 'v2:meta:connection:' || la.connection_id
                          END
                        WHERE {' AND '.join(clauses)}
                        ORDER BY la.platform, la.brand_id, la.id"""
                ),
                parameters,
            ).mappings()
            return tuple(_connected_target(row) for row in rows)

    def pending_tiktok(self, connection_id: int) -> PendingTikTokTarget | None:
        if connection_id < 1:
            raise ValueError("connection_id_invalid")
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """SELECT la.id AS link_id, la.connection_id, la.brand_id,
                              la.external_id,
                              COALESCE(NULLIF(la.display_name, ''), la.external_id) AS display_name,
                              ps.payload_json
                       FROM linked_social_accounts AS la
                       JOIN platform_connections AS pc ON pc.id=la.connection_id
                       JOIN social_projection_state AS ps
                         ON ps.projection_key='v2:tiktok:connection-credential:' || la.connection_id
                       WHERE la.connection_id=:connection_id
                         AND la.platform='tiktok'
                         AND la.status='pending_verification'
                         AND pc.status='pending_verification'"""
                ),
                {"connection_id": connection_id},
            ).mappings().one_or_none()
        if row is None:
            return None
        payload = _payload(row["payload_json"])
        if (
            payload.get("format_version") != 1
            or str(payload.get("business_id") or "") != str(row["external_id"])
        ):
            raise ValueError("tiktok_connection_payload_invalid")
        return PendingTikTokTarget(
            link_id=int(row["link_id"]),
            connection_id=int(row["connection_id"]),
            brand_id=int(row["brand_id"]),
            external_id=str(row["external_id"]),
            display_name=str(row["display_name"]),
            credential_reference=_credential_reference(payload),
        )

    def create_tiktok_asset(self, target: PendingTikTokTarget, display_name: str) -> int:
        self._write_policy.assert_allows_mutation("tiktok_canary_asset_create")
        with self.engine.begin() as connection:
            tenant_id = connection.execute(
                text("SELECT tenant_id FROM brands WHERE id=:brand_id"),
                {"brand_id": target.brand_id},
            ).scalar_one()
            return int(
                connection.execute(
                    text(
                        """INSERT INTO assets
                           (tenant_id, brand_id, platform, asset_type, external_id,
                            display_name, status, created_at, updated_at)
                           VALUES (:tenant_id, :brand_id, 'tiktok', 'profile', :external_id,
                                   :display_name, 'active', now(), now())
                           ON CONFLICT (brand_id, platform, external_id) DO UPDATE
                           SET display_name=EXCLUDED.display_name, status='active', updated_at=now()
                           RETURNING id"""
                    ),
                    {
                        "tenant_id": int(tenant_id),
                        "brand_id": target.brand_id,
                        "external_id": target.external_id,
                        "display_name": display_name or target.display_name,
                    },
                ).scalar_one()
            )

    def complete_tiktok_canary(
        self, target: PendingTikTokTarget, *, asset_id: int, synced_at: datetime
    ) -> None:
        self._write_policy.assert_allows_mutation("tiktok_canary_complete")
        with self.engine.begin() as connection:
            updated = connection.execute(
                text(
                    """UPDATE linked_social_accounts
                       SET asset_id=:asset_id, status='connected', health_status='healthy',
                           backfill_status='complete', last_synced_at=:synced_at,
                           updated_at=now()
                       WHERE id=:link_id AND connection_id=:connection_id
                         AND brand_id=:brand_id AND status='pending_verification'"""
                ),
                {
                    "asset_id": asset_id,
                    "synced_at": synced_at,
                    "link_id": target.link_id,
                    "connection_id": target.connection_id,
                    "brand_id": target.brand_id,
                },
            )
            if updated.rowcount != 1:
                raise RuntimeError("tiktok_canary_state_changed")
            connection.execute(
                text(
                    """UPDATE platform_connections SET status='connected', updated_at=now()
                       WHERE id=:connection_id AND brand_id=:brand_id
                         AND status='pending_verification'"""
                ),
                {"connection_id": target.connection_id, "brand_id": target.brand_id},
            )
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET status='active',
                           payload_json=payload_json || jsonb_build_object('state', 'connected'),
                           updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {"key": f"v2:tiktok:connection-credential:{target.connection_id}"},
            )
            self._upsert_sync_state(connection, asset_id, synced_at=synced_at, error=None)

    def mark_success(self, target: CollectionTargetRow, synced_at: datetime) -> None:
        self._write_policy.assert_allows_mutation("collection_mark_success")
        with self.engine.begin() as connection:
            self._upsert_sync_state(
                connection, target.asset_id, synced_at=synced_at, error=None
            )
            connection.execute(
                text(
                    """UPDATE linked_social_accounts
                       SET health_status='healthy', backfill_status='complete',
                           last_synced_at=:synced_at, updated_at=now()
                       WHERE id=:link_id AND asset_id=:asset_id"""
                ),
                {
                    "link_id": target.link_id,
                    "asset_id": target.asset_id,
                    "synced_at": synced_at,
                },
            )

    def mark_failure(self, target: CollectionTargetRow, error_code: str) -> None:
        self._write_policy.assert_allows_mutation("collection_mark_failure")
        safe_error = error_code[:120]
        with self.engine.begin() as connection:
            self._upsert_sync_state(
                connection, target.asset_id, synced_at=None, error=safe_error
            )
            connection.execute(
                text(
                    """UPDATE linked_social_accounts
                       SET health_status='error', updated_at=now()
                       WHERE id=:link_id AND asset_id=:asset_id"""
                ),
                {"link_id": target.link_id, "asset_id": target.asset_id},
            )

    @staticmethod
    def _upsert_sync_state(connection, asset_id: int, *, synced_at, error) -> None:
        connection.execute(
            text(
                """INSERT INTO asset_sync_state
                   (asset_id, last_synced_at, last_error, updated_at)
                   VALUES (:asset_id, :synced_at, :error, now())
                   ON CONFLICT (asset_id) DO UPDATE
                   SET last_synced_at=COALESCE(EXCLUDED.last_synced_at,
                                               asset_sync_state.last_synced_at),
                       last_error=EXCLUDED.last_error, updated_at=now()"""
            ),
            {"asset_id": asset_id, "synced_at": synced_at, "error": error},
        )


def _connected_target(row: Mapping[str, object]) -> CollectionTargetRow:
    platform = PlatformId(str(row["platform"]))
    payload = _payload(row["payload_json"])
    if platform is PlatformId.TIKTOK:
        reference = _credential_reference(payload)
    else:
        accounts = payload.get("accounts")
        if not isinstance(accounts, list):
            raise ValueError("meta_connection_payload_invalid")
        matches = [
            item
            for item in accounts
            if isinstance(item, Mapping)
            and item.get("platform") == platform.value
            and str(item.get("external_id") or "") == str(row["external_id"])
        ]
        if len(matches) != 1:
            raise ValueError("meta_connection_payload_invalid")
        reference = _credential_reference(matches[0])
    return CollectionTargetRow(
        link_id=int(row["link_id"]),
        connection_id=int(row["connection_id"]),
        asset_id=int(row["asset_id"]),
        brand_id=int(row["brand_id"]),
        platform=platform,
        external_id=str(row["external_id"]),
        display_name=str(row["display_name"]),
            credential_reference=reference,
        backfill_status=str(row["backfill_status"]),
    )


def _payload(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("connection_payload_invalid")
    return value


def _credential_reference(payload: Mapping[str, object]) -> str:
    reference = payload.get("credential_reference")
    if not isinstance(reference, str) or not reference:
        raise ValueError("credential_reference_missing")
    return reference


__all__ = [
    "CollectionTargetRow",
    "PendingTikTokTarget",
    "SocialCollectionTargetStore",
]

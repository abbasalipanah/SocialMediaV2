"""V2-owned Meta OAuth intent, discovery and Brand-link persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text

from app.application.ports import (
    ActivationContext,
    ActivationIntent,
    MetaActivationError,
    MetaCatalogAccount,
    MetaConnectionResult,
    MetaCredentialBinding,
    MetaDiscovery,
    MetaLinkResult,
    MetaLinkSelection,
    MetaRefreshConnection,
)
from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId

_CATALOG_CREDENTIALS_SQL = """
    WITH target_brand AS (
        SELECT tenant_id FROM brands WHERE id=:brand_id
    )
    SELECT DISTINCT ON (ma.platform, ma.external_id)
           ma.id AS meta_account_id, ma.platform, ma.external_id,
           COALESCE(NULLIF(ma.display_name, ''), ma.external_id) AS display_name,
           account_row->>'credential_reference' AS credential_reference
    FROM target_brand AS target
    JOIN platform_connections AS pc ON pc.tenant_id=target.tenant_id
    JOIN social_projection_state AS ps
      ON ps.projection_key='v2:meta:connection:' || pc.id::text
    CROSS JOIN LATERAL jsonb_array_elements(
        CASE
            WHEN jsonb_typeof(ps.payload_json->'accounts')='array'
                THEN ps.payload_json->'accounts'
            ELSE '[]'::jsonb
        END
    ) AS account_row
    JOIN meta_accounts AS ma
      ON ma.platform=account_row->>'platform'
     AND ma.external_id=account_row->>'external_id'
    WHERE pc.platform='facebook'
      AND pc.status IN ('pending_verification', 'connected', 'disconnected')
      AND ma.platform IN ('facebook', 'instagram')
      AND ma.status='active'
      AND length(account_row->>'credential_reference') > 0
    ORDER BY ma.platform, ma.external_id,
             pc.projected_at DESC NULLS LAST, pc.id DESC
"""


class ProjectionMetaConnectionStore:
    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        self.engine = engine
        self._write_policy = write_policy

    def create_and_lease(self, intent: ActivationIntent) -> bool:
        self._write_policy.assert_allows_mutation("meta_activation_intent_create")
        with self.engine.begin() as connection:
            applied = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                       (projection_key, payload_json, updated_at)
                       VALUES (:key, CAST(:payload AS jsonb), now())
                       ON CONFLICT (projection_key) DO NOTHING
                       RETURNING projection_key"""
                ),
                {
                    "key": self._intent_key(intent.reference_hash),
                    "payload": _json(_intent_payload(intent)),
                },
            ).scalar_one_or_none()
        return applied is not None

    def consume(
        self,
        *,
        reference_hash: str,
        expected_context: ActivationContext,
        consumed_at: datetime,
    ) -> ActivationIntent | None:
        self._write_policy.assert_allows_mutation("meta_activation_intent_consume")
        if consumed_at.tzinfo is None:
            raise MetaActivationError("meta_activation_intent_invalid")
        with self.engine.begin() as connection:
            payload = connection.execute(
                text(
                    """SELECT payload_json FROM social_projection_state
                       WHERE projection_key=:key FOR UPDATE"""
                ),
                {"key": self._intent_key(reference_hash)},
            ).scalar_one_or_none()
            if payload is None:
                return None
            intent = _parse_intent(reference_hash, payload)
            if (
                intent.context != expected_context
                or intent.consumed_at is not None
                or consumed_at >= intent.expires_at
            ):
                return None
            updated = ActivationIntent(
                reference_hash=intent.reference_hash,
                context=intent.context,
                requested_scopes=intent.requested_scopes,
                redirect_uri=intent.redirect_uri,
                created_at=intent.created_at,
                expires_at=intent.expires_at,
                leased_at=intent.leased_at,
                consumed_at=consumed_at.astimezone(UTC),
            )
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET payload_json=CAST(:payload AS jsonb), updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {
                    "key": self._intent_key(reference_hash),
                    "payload": _json(_intent_payload(updated)),
                },
            )
            return updated

    def create_pending(
        self,
        *,
        brand_id: int,
        provider_user_id: str,
        user_credential_reference: str,
        credentials: tuple[MetaCredentialBinding, ...],
        expires_at: datetime,
    ) -> MetaConnectionResult:
        self._write_policy.assert_allows_mutation("meta_activation_connection_create")
        if brand_id < 1 or not provider_user_id or not credentials or expires_at.tzinfo is None:
            raise MetaActivationError("meta_activation_connection_invalid")
        with self.engine.begin() as connection:
            brand = (
                connection.execute(
                    text("SELECT tenant_id FROM brands WHERE id=:brand_id FOR UPDATE"),
                    {"brand_id": brand_id},
                )
                .mappings()
                .one_or_none()
            )
            if brand is None:
                raise MetaActivationError("meta_activation_brand_unavailable")
            connection_id = int(
                connection.execute(
                    text(
                        """INSERT INTO platform_connections
                           (tenant_id, brand_id, platform, status, expires_at,
                            projected_at, projection_source)
                           VALUES (:tenant_id, :brand_id, 'facebook',
                                   'pending_verification', :expires_at, now(),
                                   'v2_meta_self_service')
                           RETURNING id"""
                    ),
                    {
                        "tenant_id": int(brand["tenant_id"]),
                        "brand_id": brand_id,
                        "expires_at": expires_at,
                    },
                ).scalar_one()
            )
            credential_rows: list[dict[str, object]] = []
            for item in credentials:
                meta_account_id = _upsert_meta_account(connection, item)
                connection.execute(
                    text(
                        """INSERT INTO brand_social_account_discoveries
                           (brand_id, connection_id, meta_account_id, platform,
                            external_id, display_name, status, last_discovered_at,
                            created_at, updated_at)
                           VALUES (:brand_id, :connection_id, :meta_account_id, :platform,
                                   :external_id, :display_name, 'discovered', now(), now(), now())
                           ON CONFLICT (brand_id, platform, external_id) DO UPDATE
                           SET connection_id=EXCLUDED.connection_id,
                               meta_account_id=EXCLUDED.meta_account_id,
                               display_name=EXCLUDED.display_name,
                               status='discovered', last_discovered_at=now(), updated_at=now()"""
                    ),
                    {
                        "brand_id": brand_id,
                        "connection_id": connection_id,
                        "meta_account_id": meta_account_id,
                        "platform": item.platform.value,
                        "external_id": item.external_id,
                        "display_name": item.display_name,
                    },
                )
                credential_rows.append(
                    {
                        "platform": item.platform.value,
                        "external_id": item.external_id,
                        "credential_reference": item.credential_reference,
                    }
                )
            connection.execute(
                text(
                    """INSERT INTO social_projection_state
                       (projection_key, brand_id, status, projection_source,
                        projected_at, payload_json, updated_at)
                       VALUES (:key, :brand_id, 'pending', 'v2_meta_self_service',
                               now(), CAST(:payload AS jsonb), now())
                       ON CONFLICT (projection_key) DO UPDATE
                       SET status=EXCLUDED.status, projected_at=now(),
                           payload_json=EXCLUDED.payload_json, updated_at=now()"""
                ),
                {
                    "key": self._connection_key(connection_id),
                    "brand_id": brand_id,
                    "payload": _json(
                        {
                            "format_version": 1,
                            "brand_id": brand_id,
                            "provider_user_id": provider_user_id,
                            "user_credential_reference": user_credential_reference,
                            "accounts": credential_rows,
                            "state": "pending_verification",
                        }
                    ),
                },
            )
        return MetaConnectionResult(
            connection_id=connection_id,
            brand_id=brand_id,
            state="pending_verification",
            facebook_count=sum(item.platform is PlatformId.FACEBOOK for item in credentials),
            instagram_count=sum(item.platform is PlatformId.INSTAGRAM for item in credentials),
        )

    def list_discoveries(self, *, brand_id: int) -> tuple[MetaDiscovery, ...]:
        if brand_id < 1:
            raise MetaActivationError("meta_activation_brand_invalid")
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """SELECT connection_id, platform, external_id, display_name, status
                       FROM (
                           SELECT d.connection_id, d.platform, d.external_id,
                                  COALESCE(d.display_name, d.external_id) AS display_name,
                                  d.status
                           FROM brand_social_account_discoveries AS d
                           WHERE d.brand_id=:brand_id
                             AND d.status IN ('available', 'discovered', 'linked')
                           UNION ALL
                           SELECT la.connection_id, la.platform, la.external_id,
                                  COALESCE(NULLIF(la.display_name, ''), la.external_id),
                                  'linked' AS status
                           FROM linked_social_accounts AS la
                           WHERE la.brand_id=:brand_id
                             AND la.platform IN ('facebook', 'instagram')
                             AND la.status IN ('active', 'connected')
                             AND la.connection_id IS NOT NULL
                             AND NOT EXISTS (
                                 SELECT 1
                                 FROM brand_social_account_discoveries AS d
                                 WHERE d.brand_id=la.brand_id
                                   AND d.platform=la.platform
                                   AND d.external_id=la.external_id
                             )
                       ) AS editable_accounts
                       ORDER BY platform, display_name, external_id"""
                ),
                {"brand_id": brand_id},
            ).mappings()
            return tuple(
                MetaDiscovery(
                    connection_id=int(row["connection_id"]),
                    platform=PlatformId(str(row["platform"])),
                    external_id=str(row["external_id"]),
                    display_name=str(row["display_name"]),
                    status=str(row["status"]),
                )
                for row in rows
            )

    def list_catalog_accounts(self, *, brand_id: int) -> tuple[MetaCatalogAccount, ...]:
        """List tenant-local Meta App accounts that still have a usable credential."""

        if brand_id < 1:
            raise MetaActivationError("meta_activation_brand_invalid")
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(_CATALOG_CREDENTIALS_SQL),
                {"brand_id": brand_id},
            ).mappings()
            return tuple(
                MetaCatalogAccount(
                    platform=PlatformId(str(row["platform"])),
                    external_id=str(row["external_id"]),
                    display_name=str(row["display_name"]),
                )
                for row in rows
            )

    def create_catalog_connection(
        self,
        *,
        brand_id: int,
        selections: tuple[MetaLinkSelection, ...],
    ) -> MetaConnectionResult:
        """Materialize an admin-only Brand connection from Meta App credentials."""

        self._write_policy.assert_allows_mutation("meta_catalog_connection_create")
        if brand_id < 1 or len(
            {(item.platform, item.external_id) for item in selections}
        ) != len(selections):
            raise MetaActivationError("meta_catalog_selection_invalid")
        with self.engine.begin() as connection:
            brand = connection.execute(
                text("SELECT tenant_id FROM brands WHERE id=:brand_id FOR UPDATE"),
                {"brand_id": brand_id},
            ).mappings().one_or_none()
            if brand is None:
                raise MetaActivationError("meta_activation_brand_unavailable")
            catalog_rows = tuple(
                connection.execute(
                    text(_CATALOG_CREDENTIALS_SQL),
                    {"brand_id": brand_id},
                ).mappings()
            )
            catalog = {
                (PlatformId(str(row["platform"])), str(row["external_id"])): row
                for row in catalog_rows
            }
            selected_rows = []
            for selection in selections:
                row = catalog.get((selection.platform, selection.external_id))
                if row is None:
                    raise MetaActivationError("meta_catalog_selection_invalid")
                selected_rows.append(row)
            connection_id = int(
                connection.execute(
                    text(
                        """INSERT INTO platform_connections
                           (tenant_id, brand_id, platform, status, expires_at,
                            projected_at, projection_source)
                           VALUES (:tenant_id, :brand_id, 'facebook',
                                   'pending_verification', NULL, now(),
                                   'meta_app_catalog')
                           RETURNING id"""
                    ),
                    {"tenant_id": int(brand["tenant_id"]), "brand_id": brand_id},
                ).scalar_one()
            )
            credential_rows: list[dict[str, str]] = []
            for row in selected_rows:
                connection.execute(
                    text(
                        """INSERT INTO brand_social_account_discoveries
                           (brand_id, connection_id, meta_account_id, platform,
                            external_id, display_name, status, last_discovered_at,
                            created_at, updated_at)
                           VALUES (:brand_id, :connection_id, :meta_account_id, :platform,
                                   :external_id, :display_name, 'available', now(), now(), now())
                           ON CONFLICT (brand_id, platform, external_id) DO UPDATE
                           SET connection_id=EXCLUDED.connection_id,
                               meta_account_id=EXCLUDED.meta_account_id,
                               display_name=EXCLUDED.display_name,
                               status='available', last_discovered_at=now(), updated_at=now()"""
                    ),
                    {
                        "brand_id": brand_id,
                        "connection_id": connection_id,
                        "meta_account_id": int(row["meta_account_id"]),
                        "platform": str(row["platform"]),
                        "external_id": str(row["external_id"]),
                        "display_name": str(row["display_name"]),
                    },
                )
                credential_rows.append(
                    {
                        "platform": str(row["platform"]),
                        "external_id": str(row["external_id"]),
                        "credential_reference": str(row["credential_reference"]),
                    }
                )
            connection.execute(
                text(
                    """INSERT INTO social_projection_state
                       (projection_key, brand_id, status, projection_source,
                        projected_at, payload_json, updated_at)
                       VALUES (:key, :brand_id, 'pending', 'meta_app_catalog',
                               now(), CAST(:payload AS jsonb), now())"""
                ),
                {
                    "key": self._connection_key(connection_id),
                    "brand_id": brand_id,
                    "payload": _json(
                        {
                            "format_version": 1,
                            "brand_id": brand_id,
                            "accounts": credential_rows,
                            "state": "pending_verification",
                        }
                    ),
                },
            )
        return MetaConnectionResult(
            connection_id=connection_id,
            brand_id=brand_id,
            state="pending_verification",
            facebook_count=sum(
                item.platform is PlatformId.FACEBOOK for item in selections
            ),
            instagram_count=sum(
                item.platform is PlatformId.INSTAGRAM for item in selections
            ),
        )

    def latest_refresh_connection(self, *, brand_id: int) -> MetaRefreshConnection | None:
        if brand_id < 1:
            raise MetaActivationError("meta_activation_brand_invalid")
        with self.engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        """SELECT pc.id, ps.payload_json->>'user_credential_reference'
                                      AS user_credential_reference
                           FROM platform_connections AS pc
                           JOIN social_projection_state AS ps
                             ON ps.projection_key='v2:meta:connection:' || pc.id::text
                           WHERE pc.brand_id=:brand_id AND pc.platform='facebook'
                             AND pc.status IN ('pending_verification', 'connected', 'disconnected')
                             AND length(ps.payload_json->>'user_credential_reference') > 0
                           ORDER BY pc.projected_at DESC NULLS LAST, pc.id DESC
                           LIMIT 1"""
                    ),
                    {"brand_id": brand_id},
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return None
        return MetaRefreshConnection(
            connection_id=int(row["id"]),
            brand_id=brand_id,
            user_credential_reference=str(row["user_credential_reference"]),
        )

    def refresh_discoveries(
        self,
        *,
        brand_id: int,
        connection_id: int,
        credentials: tuple[MetaCredentialBinding, ...],
    ) -> MetaConnectionResult:
        self._write_policy.assert_allows_mutation("meta_activation_refresh_discoveries")
        if (
            brand_id < 1
            or connection_id < 1
            or not credentials
            or len({(item.platform, item.external_id) for item in credentials})
            != len(credentials)
        ):
            raise MetaActivationError("meta_refresh_accounts_invalid")
        with self.engine.begin() as connection:
            connection_state = connection.execute(
                text(
                    """SELECT status FROM platform_connections
                       WHERE id=:connection_id AND brand_id=:brand_id
                         AND platform='facebook'
                         AND status IN ('pending_verification', 'connected', 'disconnected')
                       FOR UPDATE"""
                ),
                {"connection_id": connection_id, "brand_id": brand_id},
            ).scalar_one_or_none()
            if connection_state is None:
                raise MetaActivationError("meta_refresh_connection_unavailable")
            connection.execute(
                text(
                    """UPDATE brand_social_account_discoveries
                       SET status='unavailable', updated_at=now()
                       WHERE brand_id=:brand_id AND connection_id=:connection_id
                         AND status IN ('available', 'discovered')"""
                ),
                {"brand_id": brand_id, "connection_id": connection_id},
            )
            account_payload: list[dict[str, str]] = []
            for item in credentials:
                meta_account_id = _upsert_meta_account(connection, item)
                linked = bool(
                    connection.execute(
                        text(
                            """SELECT 1 FROM linked_social_accounts
                               WHERE brand_id=:brand_id AND platform=:platform
                                 AND external_id=:external_id
                                 AND status IN ('active', 'connected')
                               LIMIT 1"""
                        ),
                        {
                            "brand_id": brand_id,
                            "platform": item.platform.value,
                            "external_id": item.external_id,
                        },
                    ).scalar_one_or_none()
                )
                discovery_status = "linked" if linked else "available"
                connection.execute(
                    text(
                        """INSERT INTO brand_social_account_discoveries
                           (brand_id, connection_id, meta_account_id, platform,
                            external_id, display_name, status, last_discovered_at,
                            created_at, updated_at)
                           VALUES (:brand_id, :connection_id, :meta_account_id, :platform,
                                   :external_id, :display_name, :status, now(), now(), now())
                           ON CONFLICT (brand_id, platform, external_id) DO UPDATE
                           SET connection_id=EXCLUDED.connection_id,
                               meta_account_id=EXCLUDED.meta_account_id,
                               display_name=EXCLUDED.display_name,
                               status=EXCLUDED.status,
                               last_discovered_at=now(), updated_at=now()"""
                    ),
                    {
                        "brand_id": brand_id,
                        "connection_id": connection_id,
                        "meta_account_id": meta_account_id,
                        "platform": item.platform.value,
                        "external_id": item.external_id,
                        "display_name": item.display_name,
                        "status": discovery_status,
                    },
                )
                account_payload.append(
                    {
                        "platform": item.platform.value,
                        "external_id": item.external_id,
                        "credential_reference": item.credential_reference,
                    }
                )
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET payload_json=payload_json || jsonb_build_object(
                               'accounts', CAST(:accounts AS jsonb),
                               'last_refreshed_at', to_jsonb(now())
                           ),
                           projected_at=now(), updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {
                    "key": self._connection_key(connection_id),
                    "accounts": json.dumps(account_payload, separators=(",", ":")),
                },
            )
            connection.execute(
                text(
                    """UPDATE platform_connections
                       SET projected_at=now(), updated_at=now()
                       WHERE id=:connection_id"""
                ),
                {"connection_id": connection_id},
            )
        return MetaConnectionResult(
            connection_id=connection_id,
            brand_id=brand_id,
            state=str(connection_state),
            facebook_count=sum(
                item.platform is PlatformId.FACEBOOK for item in credentials
            ),
            instagram_count=sum(
                item.platform is PlatformId.INSTAGRAM for item in credentials
            ),
        )

    def link_accounts(
        self,
        *,
        brand_id: int,
        connection_id: int,
        selections: tuple[MetaLinkSelection, ...],
    ) -> MetaLinkResult:
        self._write_policy.assert_allows_mutation("meta_activation_link_accounts")
        with self.engine.begin() as connection:
            connection_row = (
                connection.execute(
                    text(
                        """SELECT tenant_id, status FROM platform_connections
                       WHERE id=:connection_id AND brand_id=:brand_id
                         AND platform='facebook'
                       FOR UPDATE"""
                    ),
                    {
                        "connection_id": connection_id,
                        "brand_id": brand_id,
                    },
                )
                .mappings()
                .one_or_none()
            )
            if connection_row is None or connection_row["status"] not in {
                "pending_verification",
                "connected",
                "disconnected",
            }:
                raise MetaActivationError("meta_connection_unavailable")

            selected_keys = {
                (selection.platform.value, selection.external_id) for selection in selections
            }
            existing_links = tuple(
                connection.execute(
                    text(
                        """SELECT platform, external_id, display_name, connection_id,
                                  meta_account_id, asset_id, status
                           FROM linked_social_accounts
                           WHERE brand_id=:brand_id
                             AND platform IN ('facebook', 'instagram')
                           FOR UPDATE"""
                    ),
                    {"brand_id": brand_id},
                ).mappings()
            )
            existing_by_key = {
                (str(item["platform"]), str(item["external_id"])): item
                for item in existing_links
            }
            for existing_link in existing_links:
                key = (
                    str(existing_link["platform"]),
                    str(existing_link["external_id"]),
                )
                if key in selected_keys:
                    continue
                connection.execute(
                    text(
                        """UPDATE linked_social_accounts
                           SET status='disconnected', nightly_enabled=false, updated_at=now()
                           WHERE brand_id=:brand_id AND platform=:platform
                             AND external_id=:external_id"""
                    ),
                    {
                        "brand_id": brand_id,
                        "platform": key[0],
                        "external_id": key[1],
                    },
                )
                if existing_link["asset_id"] is not None:
                    connection.execute(
                        text("UPDATE assets SET status='inactive', updated_at=now() WHERE id=:id"),
                        {"id": int(existing_link["asset_id"])},
                    )
                connection.execute(
                    text(
                        """UPDATE brand_social_account_discoveries
                           SET status='available', updated_at=now()
                           WHERE brand_id=:brand_id AND platform=:platform
                             AND external_id=:external_id"""
                    ),
                    {
                        "brand_id": brand_id,
                        "platform": key[0],
                        "external_id": key[1],
                    },
                )

            connection.execute(
                text(
                    """UPDATE brand_social_account_discoveries
                       SET status='available', updated_at=now()
                       WHERE brand_id=:brand_id AND connection_id=:connection_id
                         AND status IN ('available', 'discovered', 'linked')"""
                ),
                {"brand_id": brand_id, "connection_id": connection_id},
            )

            linked_count = 0
            for selection in selections:
                discovery = (
                    connection.execute(
                        text(
                            """SELECT id, meta_account_id,
                                  COALESCE(display_name, external_id) AS display_name
                           FROM brand_social_account_discoveries
                           WHERE brand_id=:brand_id AND connection_id=:connection_id
                             AND platform=:platform AND external_id=:external_id
                             AND status IN ('available', 'discovered', 'linked')
                           FOR UPDATE"""
                        ),
                        {
                            "brand_id": brand_id,
                            "connection_id": connection_id,
                            "platform": selection.platform.value,
                            "external_id": selection.external_id,
                        },
                    )
                    .mappings()
                    .one_or_none()
                )
                if discovery is None:
                    existing = existing_by_key.get(
                        (selection.platform.value, selection.external_id)
                    )
                    if (
                        existing is None
                        or existing["connection_id"] is None
                        or int(existing["connection_id"]) != connection_id
                        or str(existing["status"]) not in {"active", "connected"}
                    ):
                        raise MetaActivationError("meta_discovery_selection_invalid")
                    connection.execute(
                        text(
                            """UPDATE linked_social_accounts
                               SET status='connected', updated_at=now()
                               WHERE brand_id=:brand_id AND platform=:platform
                                 AND external_id=:external_id"""
                        ),
                        {
                            "brand_id": brand_id,
                            "platform": selection.platform.value,
                            "external_id": selection.external_id,
                        },
                    )
                    if existing["asset_id"] is not None:
                        connection.execute(
                            text(
                                "UPDATE assets SET status='active', updated_at=now() WHERE id=:id"
                            ),
                            {"id": int(existing["asset_id"])},
                        )
                    linked_count += 1
                    continue
                account_id = _upsert_asset(
                    connection,
                    tenant_id=int(connection_row["tenant_id"]),
                    brand_id=brand_id,
                    platform=selection.platform,
                    external_id=selection.external_id,
                    display_name=str(discovery["display_name"]),
                    meta_account_id=int(discovery["meta_account_id"]),
                )
                connection.execute(
                    text(
                        """INSERT INTO linked_social_accounts
                           (brand_id, platform, external_id, display_name,
                            connection_id, meta_account_id, asset_id, status,
                            health_status, backfill_status, created_at, updated_at)
                           VALUES (:brand_id, :platform, :external_id,
                                   :display_name, :connection_id, :meta_account_id,
                                   :account_id, 'connected', 'unknown', 'pending', now(), now())
                           ON CONFLICT (brand_id, platform, external_id) DO UPDATE
                           SET connection_id=EXCLUDED.connection_id,
                               meta_account_id=EXCLUDED.meta_account_id,
                               asset_id=EXCLUDED.asset_id, display_name=EXCLUDED.display_name,
                               status='connected', updated_at=now()"""
                    ),
                    {
                        "brand_id": brand_id,
                        "platform": selection.platform.value,
                        "external_id": selection.external_id,
                        "display_name": str(discovery["display_name"]),
                        "connection_id": connection_id,
                        "meta_account_id": int(discovery["meta_account_id"]),
                        "account_id": account_id,
                    },
                )
                connection.execute(
                    text(
                        """UPDATE brand_social_account_discoveries
                           SET status='linked', updated_at=now()
                           WHERE id=:discovery_id"""
                    ),
                    {"discovery_id": int(discovery["id"])},
                )
                linked_count += 1
            next_state = "connected" if linked_count else "disconnected"
            projection_status = "active" if linked_count else "inactive"
            connection.execute(
                text(
                    """UPDATE platform_connections
                       SET status=:status, projected_at=now(), updated_at=now()
                       WHERE id=:connection_id"""
                ),
                {"connection_id": connection_id, "status": next_state},
            )
            connection.execute(
                text(
                    """UPDATE platform_connections
                       SET status='superseded', updated_at=now()
                       WHERE brand_id=:brand_id AND platform='facebook'
                         AND id<>:connection_id
                         AND status IN ('pending_verification', 'connected')"""
                ),
                {"brand_id": brand_id, "connection_id": connection_id},
            )
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET status=:projection_status,
                           payload_json=payload_json || jsonb_build_object(
                               'state', CAST(:state AS text)
                           ),
                           updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {
                    "key": self._connection_key(connection_id),
                    "projection_status": projection_status,
                    "state": next_state,
                },
            )
        return MetaLinkResult(
            connection_id=connection_id,
            brand_id=brand_id,
            linked_count=linked_count,
            state=next_state,
        )

    @staticmethod
    def _intent_key(reference_hash: str) -> str:
        return f"v2:meta:activation-intent:{reference_hash}"

    @staticmethod
    def _connection_key(connection_id: int) -> str:
        return f"v2:meta:connection:{connection_id}"


def _upsert_meta_account(connection, item: MetaCredentialBinding) -> int:
    existing = connection.execute(
        text(
            """SELECT id FROM meta_accounts
               WHERE platform=:platform AND external_id=:external_id
               ORDER BY id LIMIT 1 FOR UPDATE"""
        ),
        {"platform": item.platform.value, "external_id": item.external_id},
    ).scalar_one_or_none()
    if existing is not None:
        connection.execute(
            text(
                """UPDATE meta_accounts
                   SET display_name=:display_name, status='active',
                       last_discovered_at=now(), updated_at=now()
                   WHERE id=:id"""
            ),
            {"id": int(existing), "display_name": item.display_name},
        )
        return int(existing)
    return int(
        connection.execute(
            text(
                """INSERT INTO meta_accounts
                   (platform, asset_type, external_id, display_name, status,
                    last_discovered_at, created_at, updated_at)
                   VALUES (:platform, :asset_type, :external_id, :display_name,
                           'active', now(), now(), now())
                   RETURNING id"""
            ),
            {
                "platform": item.platform.value,
                "asset_type": "page" if item.platform is PlatformId.FACEBOOK else "profile",
                "external_id": item.external_id,
                "display_name": item.display_name,
            },
        ).scalar_one()
    )


def _upsert_asset(
    connection,
    *,
    tenant_id: int,
    brand_id: int,
    platform: PlatformId,
    external_id: str,
    display_name: str,
    meta_account_id: int,
) -> int:
    existing = connection.execute(
        text(
            """SELECT id FROM assets
               WHERE brand_id=:brand_id AND platform=:platform
                 AND external_id=:external_id
               ORDER BY id LIMIT 1 FOR UPDATE"""
        ),
        {"brand_id": brand_id, "platform": platform.value, "external_id": external_id},
    ).scalar_one_or_none()
    if existing is not None:
        connection.execute(
            text(
                """UPDATE assets
                   SET display_name=:display_name, meta_account_id=:meta_account_id,
                       status='active', updated_at=now()
                   WHERE id=:id"""
            ),
            {
                "id": int(existing),
                "display_name": display_name,
                "meta_account_id": meta_account_id,
            },
        )
        return int(existing)
    return int(
        connection.execute(
            text(
                """INSERT INTO assets
                   (tenant_id, brand_id, platform, asset_type,
                    external_id, display_name, meta_account_id, status, created_at)
                   VALUES (:tenant_id, :brand_id, :platform,
                           :asset_type, :external_id, :display_name,
                           :meta_account_id, 'active', now())
                   RETURNING id"""
            ),
            {
                "tenant_id": tenant_id,
                "brand_id": brand_id,
                "platform": platform.value,
                "asset_type": "page" if platform is PlatformId.FACEBOOK else "profile",
                "external_id": external_id,
                "display_name": display_name,
                "meta_account_id": meta_account_id,
            },
        ).scalar_one()
    )


def _intent_payload(intent: ActivationIntent) -> dict[str, Any]:
    return {
        "brand_id": intent.context.brand_id,
        "consumed_at": (
            intent.consumed_at.astimezone(UTC).isoformat()
            if intent.consumed_at is not None
            else None
        ),
        "created_at": intent.created_at.astimezone(UTC).isoformat(),
        "expires_at": intent.expires_at.astimezone(UTC).isoformat(),
        "format_version": 1,
        "issuer": "social_media",
        "leased_at": intent.leased_at.astimezone(UTC).isoformat(),
        "reason": "meta_self_service_activation",
        "redirect_uri": intent.redirect_uri,
        "reference_hash": intent.reference_hash,
        "requested_scopes": list(intent.requested_scopes),
        "session_binding": intent.context.session_binding,
        "sso_consumed_at": intent.context.sso_consumed_at.astimezone(UTC).isoformat(),
        "sso_jti_hash": intent.context.sso_jti_hash,
        "user_id": intent.context.user_id,
    }


def _parse_intent(reference_hash: str, payload: Mapping[str, Any]) -> ActivationIntent:
    expected = {
        "brand_id",
        "consumed_at",
        "created_at",
        "expires_at",
        "format_version",
        "issuer",
        "leased_at",
        "reason",
        "redirect_uri",
        "reference_hash",
        "requested_scopes",
        "session_binding",
        "sso_consumed_at",
        "sso_jti_hash",
        "user_id",
    }
    if set(payload) != expected:
        raise MetaActivationError("meta_activation_intent_invalid")
    try:
        if (
            payload["format_version"] != 1
            or payload["issuer"] != "social_media"
            or payload["reason"] != "meta_self_service_activation"
            or payload["reference_hash"] != reference_hash
            or not isinstance(payload["requested_scopes"], list)
        ):
            raise ValueError
        context = ActivationContext(
            user_id=str(payload["user_id"]),
            brand_id=int(payload["brand_id"]),
            session_binding=str(payload["session_binding"]),
            sso_jti_hash=str(payload["sso_jti_hash"]),
            sso_consumed_at=datetime.fromisoformat(str(payload["sso_consumed_at"])),
        )
        consumed_raw = payload["consumed_at"]
        return ActivationIntent(
            reference_hash=reference_hash,
            context=context,
            requested_scopes=tuple(str(item) for item in payload["requested_scopes"]),
            redirect_uri=str(payload["redirect_uri"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            leased_at=datetime.fromisoformat(str(payload["leased_at"])),
            consumed_at=(
                datetime.fromisoformat(str(consumed_raw)) if consumed_raw is not None else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MetaActivationError("meta_activation_intent_invalid") from exc


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


__all__ = ["ProjectionMetaConnectionStore"]

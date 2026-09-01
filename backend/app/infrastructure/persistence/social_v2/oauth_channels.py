"""PostgreSQL persistence for X, LinkedIn, and YouTube OAuth connections."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, text

from app.application.ports import (
    OAUTH_CHANNEL_PLATFORMS,
    OAuthChannelError,
    OAuthConnectionResult,
    OAuthCredentialBinding,
    OAuthDiscovery,
    OAuthLinkResult,
    OAuthLinkSelection,
)
from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId


class ProjectionOAuthConnectionStore:
    def __init__(
        self,
        engine: Engine,
        write_policy: WritePolicy,
        platform: PlatformId,
    ) -> None:
        if platform not in OAUTH_CHANNEL_PLATFORMS:
            raise OAuthChannelError("oauth_store_platform_invalid")
        self.engine = engine
        self._write_policy = write_policy
        self._platform = platform

    def create_pending(
        self,
        *,
        brand_id: int,
        platform: PlatformId,
        provider_subject_id: str,
        credentials: tuple[OAuthCredentialBinding, ...],
        expires_at: datetime,
    ) -> OAuthConnectionResult:
        self._write_policy.assert_allows_mutation(self._command("connection_create"))
        self._require_platform(platform)
        if (
            brand_id < 1
            or not provider_subject_id
            or not credentials
            or expires_at.tzinfo is None
            or any(item.platform is not platform for item in credentials)
            or len({item.external_id for item in credentials}) != len(credentials)
        ):
            raise OAuthChannelError("oauth_connection_invalid")
        with self.engine.begin() as connection:
            tenant_id = connection.execute(
                text("SELECT tenant_id FROM brands WHERE id=:brand_id FOR UPDATE"),
                {"brand_id": brand_id},
            ).scalar_one_or_none()
            if tenant_id is None:
                raise OAuthChannelError("oauth_brand_unavailable")
            connection_id = int(
                connection.execute(
                    text(
                        """INSERT INTO platform_connections
                           (tenant_id, brand_id, platform, status, expires_at,
                            projected_at, projection_source)
                           VALUES (:tenant_id, :brand_id, :platform,
                                   'pending_verification', :expires_at, now(),
                                   'v2_oauth_channel')
                           RETURNING id"""
                    ),
                    {
                        "tenant_id": int(tenant_id),
                        "brand_id": brand_id,
                        "platform": platform.value,
                        "expires_at": expires_at,
                    },
                ).scalar_one()
            )
            payload = {
                "accounts": [
                    {
                        "credential_reference": item.credential_reference,
                        "display_name": item.display_name,
                        "external_id": item.external_id,
                        "platform": item.platform.value,
                    }
                    for item in credentials
                ],
                "brand_id": brand_id,
                "format_version": 1,
                "platform": platform.value,
                "provider_subject_id": provider_subject_id,
                "state": "pending_verification",
            }
            connection.execute(
                text(
                    """INSERT INTO social_projection_state
                       (projection_key, brand_id, status, projection_source,
                        projected_at, payload_json, updated_at)
                       VALUES (:key, :brand_id, 'pending', 'v2_oauth_channel',
                               now(), CAST(:payload AS jsonb), now())"""
                ),
                {
                    "key": self._connection_key(connection_id),
                    "brand_id": brand_id,
                    "payload": _json(payload),
                },
            )
        return OAuthConnectionResult(
            connection_id=connection_id,
            brand_id=brand_id,
            platform=platform,
            state="pending_verification",
            discovered_count=len(credentials),
        )

    def list_discoveries(
        self, *, brand_id: int, platform: PlatformId
    ) -> tuple[OAuthDiscovery, ...]:
        self._require_platform(platform)
        if brand_id < 1:
            raise OAuthChannelError("oauth_brand_unavailable")
        with self.engine.connect() as connection:
            rows = connection.execute(
                text(
                    """SELECT pc.id AS connection_id, ps.payload_json
                       FROM platform_connections AS pc
                       JOIN social_projection_state AS ps
                         ON ps.projection_key=(
                           'v2:oauth:' || pc.platform || ':connection:' || pc.id::text
                         )
                       WHERE pc.brand_id=:brand_id AND pc.platform=:platform
                         AND pc.status IN (
                           'pending_verification', 'connected', 'disconnected'
                         )
                       ORDER BY pc.id DESC"""
                ),
                {"brand_id": brand_id, "platform": platform.value},
            ).mappings()
            linked = set(
                connection.execute(
                    text(
                        """SELECT external_id FROM linked_social_accounts
                           WHERE brand_id=:brand_id AND platform=:platform
                             AND status IN ('active', 'connected')"""
                    ),
                    {"brand_id": brand_id, "platform": platform.value},
                ).scalars()
            )
            discoveries: list[OAuthDiscovery] = []
            seen: set[str] = set()
            for row in rows:
                payload = _connection_payload(row["payload_json"], platform)
                for account in _accounts(payload, platform):
                    external_id = str(account["external_id"])
                    if external_id in seen:
                        continue
                    seen.add(external_id)
                    discoveries.append(
                        OAuthDiscovery(
                            connection_id=int(row["connection_id"]),
                            platform=platform,
                            external_id=external_id,
                            display_name=str(account["display_name"]),
                            status="linked" if external_id in linked else "available",
                        )
                    )
        return tuple(
            sorted(discoveries, key=lambda item: (item.display_name.casefold(), item.external_id))
        )

    def link_accounts(
        self,
        *,
        brand_id: int,
        platform: PlatformId,
        connection_id: int,
        selections: tuple[OAuthLinkSelection, ...],
    ) -> OAuthLinkResult:
        self._write_policy.assert_allows_mutation(self._command("link"))
        self._require_platform(platform)
        selected_ids = {item.external_id for item in selections}
        if brand_id < 1 or connection_id < 1 or len(selected_ids) != len(selections):
            raise OAuthChannelError("oauth_link_selection_invalid")
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """SELECT pc.tenant_id, pc.status, ps.payload_json
                       FROM platform_connections AS pc
                       JOIN social_projection_state AS ps
                         ON ps.projection_key=:key
                       WHERE pc.id=:connection_id AND pc.brand_id=:brand_id
                         AND pc.platform=:platform
                         AND pc.status IN ('pending_verification', 'connected')
                       FOR UPDATE"""
                ),
                {
                    "key": self._connection_key(connection_id),
                    "connection_id": connection_id,
                    "brand_id": brand_id,
                    "platform": platform.value,
                },
            ).mappings().one_or_none()
            if row is None:
                raise OAuthChannelError("oauth_connection_not_found")
            payload = _connection_payload(row["payload_json"], platform)
            accounts = {str(item["external_id"]): item for item in _accounts(payload, platform)}
            if not selected_ids or not selected_ids.issubset(accounts):
                raise OAuthChannelError("oauth_link_selection_invalid")
            connection.execute(
                text(
                    """WITH disabled AS (
                           UPDATE linked_social_accounts
                           SET status='disconnected', health_status='unknown',
                               nightly_enabled=false, updated_at=now()
                           WHERE brand_id=:brand_id AND platform=:platform
                             AND connection_id=:connection_id
                             AND NOT (external_id = ANY(:selected_ids))
                             AND status IN ('active', 'connected')
                           RETURNING asset_id
                       )
                       UPDATE assets SET status='inactive', updated_at=now()
                       WHERE id IN (SELECT asset_id FROM disabled WHERE asset_id IS NOT NULL)"""
                ),
                {
                    "brand_id": brand_id,
                    "platform": platform.value,
                    "connection_id": connection_id,
                    "selected_ids": sorted(selected_ids),
                },
            )
            for external_id in sorted(selected_ids):
                account = accounts[external_id]
                asset_id = _upsert_asset(
                    connection,
                    tenant_id=int(row["tenant_id"]),
                    brand_id=brand_id,
                    platform=platform,
                    external_id=external_id,
                    display_name=str(account["display_name"]),
                )
                connection.execute(
                    text(
                        """INSERT INTO linked_social_accounts
                           (brand_id, platform, external_id, display_name,
                            connection_id, asset_id, status, health_status,
                            backfill_status, nightly_enabled, created_at, updated_at)
                           VALUES (:brand_id, :platform, :external_id, :display_name,
                                   :connection_id, :asset_id, 'connected', 'unknown',
                                   'pending', true, now(), now())
                           ON CONFLICT (brand_id, platform, external_id) DO UPDATE
                           SET display_name=EXCLUDED.display_name,
                               connection_id=EXCLUDED.connection_id,
                               asset_id=EXCLUDED.asset_id, status='connected',
                               health_status='unknown', backfill_status='pending',
                               nightly_enabled=true, updated_at=now()"""
                    ),
                    {
                        "brand_id": brand_id,
                        "platform": platform.value,
                        "external_id": external_id,
                        "display_name": str(account["display_name"]),
                        "connection_id": connection_id,
                        "asset_id": asset_id,
                    },
                )
            connection.execute(
                text(
                    """UPDATE platform_connections
                       SET status='connected', updated_at=now()
                       WHERE id=:connection_id"""
                ),
                {"connection_id": connection_id},
            )
            payload = {**payload, "state": "connected", "linked_ids": sorted(selected_ids)}
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET status='active', payload_json=CAST(:payload AS jsonb),
                           updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {"key": self._connection_key(connection_id), "payload": _json(payload)},
            )
        return OAuthLinkResult(
            connection_id=connection_id,
            brand_id=brand_id,
            platform=platform,
            linked_count=len(selections),
            state="connected",
        )

    def disconnect(
        self,
        *,
        brand_id: int,
        platform: PlatformId,
        external_id: str,
    ) -> OAuthLinkResult | None:
        self._write_policy.assert_allows_mutation(self._command("disconnect"))
        self._require_platform(platform)
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """SELECT la.id, la.connection_id, la.asset_id, ps.payload_json
                       FROM linked_social_accounts AS la
                       JOIN social_projection_state AS ps
                         ON ps.projection_key=(
                           'v2:oauth:' || la.platform || ':connection:'
                           || la.connection_id::text
                         )
                       WHERE la.brand_id=:brand_id AND la.platform=:platform
                         AND la.external_id=:external_id
                         AND la.status IN ('active', 'connected')
                       FOR UPDATE"""
                ),
                {
                    "brand_id": brand_id,
                    "platform": platform.value,
                    "external_id": external_id,
                },
            ).mappings().one_or_none()
            if row is None or row["connection_id"] is None:
                return None
            connection_id = int(row["connection_id"])
            connection.execute(
                text(
                    """UPDATE linked_social_accounts
                       SET status='disconnected', health_status='unknown',
                           nightly_enabled=false, updated_at=now()
                       WHERE id=:link_id"""
                ),
                {"link_id": int(row["id"])},
            )
            if row["asset_id"] is not None:
                connection.execute(
                    text("UPDATE assets SET status='inactive', updated_at=now() WHERE id=:id"),
                    {"id": int(row["asset_id"])},
                )
            remaining = int(
                connection.execute(
                    text(
                        """SELECT count(*) FROM linked_social_accounts
                           WHERE connection_id=:connection_id
                             AND status IN ('active', 'connected')"""
                    ),
                    {"connection_id": connection_id},
                ).scalar_one()
            )
            connection_state = "disconnected" if remaining == 0 else "connected"
            projection_status = "inactive" if remaining == 0 else "active"
            connection.execute(
                text(
                    """UPDATE platform_connections SET status=:status, updated_at=now()
                       WHERE id=:connection_id"""
                ),
                {"connection_id": connection_id, "status": connection_state},
            )
            payload = _connection_payload(row["payload_json"], platform)
            linked_ids = payload.get("linked_ids", [])
            if not isinstance(linked_ids, list):
                raise OAuthChannelError("oauth_connection_payload_invalid")
            payload = {
                **payload,
                "state": connection_state,
                "linked_ids": [value for value in linked_ids if value != external_id],
            }
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET status=:status, payload_json=CAST(:payload AS jsonb),
                           updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {
                    "key": self._connection_key(connection_id),
                    "status": projection_status,
                    "payload": _json(payload),
                },
            )
        return OAuthLinkResult(
            connection_id=connection_id,
            brand_id=brand_id,
            platform=platform,
            linked_count=remaining,
            state=connection_state,
        )

    def _require_platform(self, platform: PlatformId) -> None:
        if platform is not self._platform:
            raise OAuthChannelError("oauth_store_platform_mismatch")

    def _connection_key(self, connection_id: int) -> str:
        return f"v2:oauth:{self._platform.value}:connection:{connection_id}"

    def _command(self, operation: str) -> str:
        return f"{self._platform.value}_oauth_store_{operation}"


def _upsert_asset(
    connection,
    *,
    tenant_id: int,
    brand_id: int,
    platform: PlatformId,
    external_id: str,
    display_name: str,
) -> int:
    return int(
        connection.execute(
            text(
                """INSERT INTO assets
                   (tenant_id, brand_id, platform, asset_type, external_id,
                    display_name, status, created_at, updated_at)
                   VALUES (:tenant_id, :brand_id, :platform, 'channel', :external_id,
                           :display_name, 'active', now(), now())
                   ON CONFLICT (brand_id, platform, external_id) DO UPDATE
                   SET display_name=EXCLUDED.display_name, status='active', updated_at=now()
                   RETURNING id"""
            ),
            {
                "tenant_id": tenant_id,
                "brand_id": brand_id,
                "platform": platform.value,
                "external_id": external_id,
                "display_name": display_name,
            },
        ).scalar_one()
    )


def _connection_payload(value: object, platform: PlatformId) -> dict[str, Any]:
    expected = {
        "accounts", "brand_id", "format_version", "platform",
        "provider_subject_id", "state",
    }
    if not isinstance(value, Mapping) or not expected.issubset(value):
        raise OAuthChannelError("oauth_connection_payload_invalid")
    if value.get("format_version") != 1 or value.get("platform") != platform.value:
        raise OAuthChannelError("oauth_connection_payload_invalid")
    return dict(value)


def _accounts(
    payload: Mapping[str, Any], platform: PlatformId
) -> tuple[Mapping[str, Any], ...]:
    raw = payload.get("accounts")
    if not isinstance(raw, list):
        raise OAuthChannelError("oauth_connection_payload_invalid")
    accounts: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    required = {"credential_reference", "display_name", "external_id", "platform"}
    for item in raw:
        if (
            not isinstance(item, Mapping)
            or set(item) != required
            or item.get("platform") != platform.value
            or not all(isinstance(item.get(key), str) and item.get(key) for key in required)
            or str(item["external_id"]) in seen
        ):
            raise OAuthChannelError("oauth_connection_payload_invalid")
        seen.add(str(item["external_id"]))
        accounts.append(item)
    if not accounts:
        raise OAuthChannelError("oauth_connection_payload_invalid")
    return tuple(accounts)


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


__all__ = ["ProjectionOAuthConnectionStore"]

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
    MetaConnectionResult,
    MetaCredentialBinding,
    MetaDiscovery,
    MetaLinkResult,
    MetaLinkSelection,
)
from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId


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
                    """SELECT connection_id, platform, external_id,
                              COALESCE(display_name, external_id) AS display_name, status
                       FROM brand_social_account_discoveries
                       WHERE brand_id=:brand_id AND status IN ('discovered', 'linked')
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
            }:
                raise MetaActivationError("meta_connection_unavailable")
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
                             AND status IN ('discovered', 'linked')
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
                    raise MetaActivationError("meta_discovery_selection_invalid")
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
            connection.execute(
                text(
                    """UPDATE platform_connections
                       SET status='connected', projected_at=now()
                       WHERE id=:connection_id"""
                ),
                {"connection_id": connection_id},
            )
            connection.execute(
                text(
                    """UPDATE social_projection_state
                       SET status='active',
                           payload_json=payload_json || jsonb_build_object('state', 'connected'),
                           updated_at=now()
                       WHERE projection_key=:key"""
                ),
                {"key": self._connection_key(connection_id)},
            )
        return MetaLinkResult(
            connection_id=connection_id,
            brand_id=brand_id,
            linked_count=linked_count,
            state="connected",
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
                       status='active'
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

"""V2-owned PostgreSQL intent and Brand-link persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text

from app.application.ports import (
    ActivationContext,
    ActivationIntent,
    ActivationLink,
    TikTokActivationError,
)
from app.core.write_policy import WritePolicy


class ProjectionTikTokActivationStore:
    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        self.engine = engine
        self._write_policy = write_policy

    def create_and_lease(self, intent: ActivationIntent) -> bool:
        self._write_policy.assert_allows_mutation("tiktok_activation_intent_create")
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
        self._write_policy.assert_allows_mutation("tiktok_activation_intent_consume")
        if consumed_at.tzinfo is None:
            raise TikTokActivationError("activation_intent_invalid")
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
        business_id: str,
        credential_reference: str,
        access_expires_at: datetime,
    ) -> ActivationLink:
        self._write_policy.assert_allows_mutation("tiktok_activation_link_create")
        if brand_id < 1 or not business_id or access_expires_at.tzinfo is None:
            raise TikTokActivationError("activation_link_invalid")
        with self.engine.begin() as connection:
            tenant_id = connection.execute(
                text("SELECT tenant_id FROM brands WHERE id=:brand_id FOR UPDATE"),
                {"brand_id": brand_id},
            ).scalar_one_or_none()
            if tenant_id is None:
                raise TikTokActivationError("activation_brand_unavailable")
            existing = connection.execute(
                text(
                    """SELECT id, connection_id, status
                       FROM linked_social_accounts
                       WHERE brand_id=:brand_id AND platform='tiktok'
                         AND external_id=:business_id
                       FOR UPDATE"""
                ),
                {"brand_id": brand_id, "business_id": business_id},
            ).mappings().one_or_none()
            if existing is not None:
                if (
                    existing["status"] != "pending_verification"
                    or existing["connection_id"] is None
                ):
                    raise TikTokActivationError("activation_link_conflict")
                connection_id = int(existing["connection_id"])
                link_id = int(existing["id"])
            else:
                connection_id = int(
                    connection.execute(
                        text(
                            """INSERT INTO platform_connections
                               (tenant_id, brand_id, platform, status, expires_at,
                                projected_at, projection_source)
                               VALUES (:tenant_id, :brand_id, 'tiktok',
                                       'pending_verification', :expires_at, now(),
                                       'v2_owner_activation')
                               RETURNING id"""
                        ),
                        {
                            "tenant_id": tenant_id,
                            "brand_id": brand_id,
                            "expires_at": access_expires_at,
                        },
                    ).scalar_one()
                )
                link_id = int(
                    connection.execute(
                        text(
                            """INSERT INTO linked_social_accounts
                               (brand_id, platform, external_id, connection_id, status,
                                health_status, backfill_status, nightly_enabled,
                                created_at, updated_at)
                               VALUES (:brand_id, 'tiktok', :business_id, :connection_id,
                                       'pending_verification', 'unknown', 'pending', false,
                                       now(), now())
                               RETURNING id"""
                        ),
                        {
                            "brand_id": brand_id,
                            "business_id": business_id,
                            "connection_id": connection_id,
                        },
                    ).scalar_one()
                )
            connection.execute(
                text(
                    """INSERT INTO social_projection_state
                       (projection_key, payload_json, updated_at)
                       VALUES (:key, CAST(:payload AS jsonb), now())
                       ON CONFLICT (projection_key) DO UPDATE
                       SET payload_json=EXCLUDED.payload_json, updated_at=now()"""
                ),
                {
                    "key": f"v2:tiktok:connection-credential:{connection_id}",
                    "payload": _json(
                        {
                            "brand_id": brand_id,
                            "business_id": business_id,
                            "credential_reference": credential_reference,
                            "format_version": 1,
                            "state": "pending_verification",
                        }
                    ),
                },
            )
        return ActivationLink(
            connection_id=connection_id,
            link_id=link_id,
            brand_id=brand_id,
            business_id=business_id,
            state="pending_verification",
        )

    @staticmethod
    def _intent_key(reference_hash: str) -> str:
        return f"v2:tiktok:activation-intent:{reference_hash}"


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
        "reason": "owner_tiktok_activation",
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
    try:
        if (
            set(payload) != expected
            or payload["format_version"] != 1
            or payload["issuer"] != "social_media"
            or payload["reason"] != "owner_tiktok_activation"
        ):
            raise ValueError
        if payload["reference_hash"] != reference_hash:
            raise ValueError
        scopes = payload["requested_scopes"]
        if not isinstance(scopes, list) or not all(isinstance(item, str) for item in scopes):
            raise ValueError
        consumed_raw = payload["consumed_at"]
        return ActivationIntent(
            reference_hash=reference_hash,
            context=ActivationContext(
                user_id=str(payload["user_id"]),
                brand_id=int(payload["brand_id"]),
                session_binding=str(payload["session_binding"]),
                sso_jti_hash=str(payload["sso_jti_hash"]),
                sso_consumed_at=datetime.fromisoformat(str(payload["sso_consumed_at"])),
            ),
            requested_scopes=tuple(scopes),
            redirect_uri=str(payload["redirect_uri"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            leased_at=datetime.fromisoformat(str(payload["leased_at"])),
            consumed_at=(
                datetime.fromisoformat(str(consumed_raw)) if consumed_raw is not None else None
            ),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise TikTokActivationError("activation_intent_payload_invalid") from exc


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


__all__ = ["ProjectionTikTokActivationStore"]

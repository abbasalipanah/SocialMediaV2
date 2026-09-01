"""PostgreSQL one-time intent persistence for OAuth channel integrations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text

from app.application.ports import (
    OAUTH_CHANNEL_PLATFORMS,
    ActivationContext,
    ActivationIntent,
    OAuthChannelError,
)
from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId


class ProjectionOAuthIntentStore:
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

    def create_and_lease(self, intent: ActivationIntent) -> bool:
        self._write_policy.assert_allows_mutation(self._command("create"))
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
                    "payload": _json(_intent_payload(intent, self._platform)),
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
        self._write_policy.assert_allows_mutation(self._command("consume"))
        if consumed_at.tzinfo is None:
            raise OAuthChannelError("oauth_intent_invalid")
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
            intent = _parse_intent(reference_hash, payload, self._platform)
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
                    "payload": _json(_intent_payload(updated, self._platform)),
                },
            )
            return updated

    def _intent_key(self, reference_hash: str) -> str:
        return f"v2:oauth:{self._platform.value}:intent:{reference_hash}"

    def _command(self, operation: str) -> str:
        return f"{self._platform.value}_oauth_intent_{operation}"


def _intent_payload(intent: ActivationIntent, platform: PlatformId) -> dict[str, Any]:
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
        "leased_at": intent.leased_at.astimezone(UTC).isoformat(),
        "platform": platform.value,
        "redirect_uri": intent.redirect_uri,
        "reference_hash": intent.reference_hash,
        "requested_scopes": list(intent.requested_scopes),
        "session_binding": intent.context.session_binding,
        "sso_consumed_at": intent.context.sso_consumed_at.astimezone(UTC).isoformat(),
        "sso_jti_hash": intent.context.sso_jti_hash,
        "user_id": intent.context.user_id,
    }


def _parse_intent(
    reference_hash: str,
    payload: Mapping[str, Any],
    platform: PlatformId,
) -> ActivationIntent:
    expected = {
        "brand_id", "consumed_at", "created_at", "expires_at", "format_version",
        "leased_at", "platform", "redirect_uri", "reference_hash",
        "requested_scopes", "session_binding", "sso_consumed_at", "sso_jti_hash", "user_id",
    }
    if set(payload) != expected:
        raise OAuthChannelError("oauth_intent_invalid")
    try:
        if (
            payload["format_version"] != 1
            or payload["platform"] != platform.value
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
        consumed = payload["consumed_at"]
        return ActivationIntent(
            reference_hash=reference_hash,
            context=context,
            requested_scopes=tuple(str(item) for item in payload["requested_scopes"]),
            redirect_uri=str(payload["redirect_uri"]),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            leased_at=datetime.fromisoformat(str(payload["leased_at"])),
            consumed_at=(datetime.fromisoformat(str(consumed)) if consumed is not None else None),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise OAuthChannelError("oauth_intent_invalid") from exc


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


__all__ = ["ProjectionOAuthIntentStore"]

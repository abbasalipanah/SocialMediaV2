"""Namespaced projection-state provider checkpoint store."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, text

from app.application.ports.checkpoints import CheckpointKey, ProviderCheckpoint
from app.core.time import utc_now
from app.core.write_policy import WritePolicy
from app.domain.platforms import CapabilityId, PlatformId


class ProjectionCheckpointStore:
    def __init__(
        self,
        engine: Engine,
        write_policy: WritePolicy,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.engine = engine
        self._write_policy = write_policy
        self._clock = clock

    def get(self, key: CheckpointKey) -> ProviderCheckpoint | None:
        with self.engine.connect() as connection:
            payload = connection.execute(
                text(
                    """SELECT payload_json FROM social_projection_state
                       WHERE projection_key=:key"""
                ),
                {"key": self._key(key)},
            ).scalar_one_or_none()
        if payload is None:
            return None
        return _parse_checkpoint(key, payload)

    def put(
        self,
        checkpoint: ProviderCheckpoint,
        *,
        expected_version: int | None,
    ) -> bool:
        self._write_policy.assert_allows_mutation("checkpoint.put")
        if expected_version is None:
            if checkpoint.version != 1:
                raise ValueError("checkpoint_initial_version_invalid")
            statement = text(
                """INSERT INTO social_projection_state
                   (projection_key, payload_json, updated_at)
                   VALUES (:key, CAST(:payload AS jsonb), now())
                   ON CONFLICT (projection_key) DO NOTHING
                   RETURNING projection_key"""
            )
        else:
            if expected_version < 1 or checkpoint.version != expected_version + 1:
                raise ValueError("checkpoint_version_transition_invalid")
            statement = text(
                """INSERT INTO social_projection_state
                   (projection_key, payload_json, updated_at)
                   VALUES (:key, CAST(:payload AS jsonb), now())
                   ON CONFLICT (projection_key) DO UPDATE
                   SET payload_json=EXCLUDED.payload_json, updated_at=now()
                   WHERE (social_projection_state.payload_json->>'version')::bigint
                         = :expected_version
                   RETURNING projection_key"""
            )
        with self.engine.begin() as connection:
            applied = connection.execute(
                statement,
                {
                    "key": self._key(checkpoint.key),
                    "payload": _json(_checkpoint_payload(checkpoint)),
                    "expected_version": expected_version,
                },
            ).scalar_one_or_none()
        return applied is not None

    def claim_once(
        self,
        key: CheckpointKey,
        operation_id: str,
        expires_at: datetime,
    ) -> bool:
        self._write_policy.assert_allows_mutation("checkpoint.claim_once")
        if not operation_id or len(operation_id.encode("utf-8")) > 512:
            raise ValueError("checkpoint_operation_invalid")
        if expires_at.tzinfo is None or expires_at <= self._clock():
            raise ValueError("checkpoint_expiry_invalid")
        claim_hash = _claim_hash(key, operation_id)
        with self.engine.begin() as connection:
            applied = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                       (projection_key, payload_json, updated_at)
                       VALUES (:key, CAST(:payload AS jsonb), now())
                       ON CONFLICT (projection_key) DO UPDATE
                       SET payload_json=EXCLUDED.payload_json, updated_at=now()
                       WHERE social_projection_state.payload_json->>'expires_at' IS NOT NULL
                         AND (social_projection_state.payload_json->>'expires_at')::timestamptz
                             <= now()
                       RETURNING projection_key"""
                ),
                {
                    "key": f"v2:checkpoint-once:{claim_hash}",
                    "payload": _json(
                        {
                            "format_version": 1,
                            "expires_at": expires_at.astimezone(UTC).isoformat(),
                        }
                    ),
                },
            ).scalar_one_or_none()
        return applied is not None

    @staticmethod
    def _key(key: CheckpointKey) -> str:
        return f"v2:checkpoint:{key.platform.value}:{key.capability.value}:{key.account_id}"


def _checkpoint_payload(checkpoint: ProviderCheckpoint) -> dict[str, Any]:
    return {
        "format_version": 1,
        "platform": checkpoint.key.platform.value,
        "capability": checkpoint.key.capability.value,
        "account_id": checkpoint.key.account_id,
        "version": checkpoint.version,
        "cursor": checkpoint.cursor,
        "watermark": checkpoint.watermark,
        "observed_through": (
            checkpoint.observed_through.astimezone(UTC).isoformat()
            if checkpoint.observed_through is not None
            else None
        ),
    }


def _parse_checkpoint(
    expected_key: CheckpointKey,
    payload: Mapping[str, Any],
) -> ProviderCheckpoint:
    try:
        if int(payload["format_version"]) != 1:
            raise ValueError
        stored_key = CheckpointKey(
            platform=PlatformId(str(payload["platform"])),
            capability=CapabilityId(str(payload["capability"])),
            account_id=str(payload["account_id"]),
        )
        if stored_key != expected_key:
            raise ValueError
        observed_raw = payload.get("observed_through")
        observed = datetime.fromisoformat(observed_raw) if observed_raw is not None else None
        if observed is not None and observed.tzinfo is None:
            raise ValueError
        return ProviderCheckpoint(
            key=stored_key,
            version=int(payload["version"]),
            cursor=str(payload["cursor"]) if payload.get("cursor") is not None else None,
            watermark=(
                str(payload["watermark"]) if payload.get("watermark") is not None else None
            ),
            observed_through=observed.astimezone(UTC) if observed is not None else None,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("checkpoint_payload_invalid") from exc


def _claim_hash(key: CheckpointKey, operation_id: str) -> str:
    parts = (
        key.platform.value,
        key.capability.value,
        key.account_id,
        operation_id,
    )
    encoded = (part.encode("utf-8") for part in parts)
    canonical = b"".join(len(part).to_bytes(4, "big") + part for part in encoded)
    return hashlib.sha256(canonical).hexdigest()


def _json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


__all__ = ["ProjectionCheckpointStore"]

"""Schema-compatible PostgreSQL adapter for namespaced projection state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, create_engine, text


class ProjectionStateStore:
    def __init__(self, database_url: str) -> None:
        self.engine: Engine = create_engine(database_url, pool_pre_ping=True)

    def create_from_jti(
        self,
        *,
        jti_hash: str,
        session_hash: str,
        payload: Mapping[str, Any],
        expires_at: datetime,
    ) -> bool:
        with self.engine.begin() as connection:
            claimed = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload, expires_at, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), :expires_at, now())
                    ON CONFLICT (projection_key) DO NOTHING
                    RETURNING projection_key"""
                ),
                {"key": f"v2:sso-jti:{jti_hash}", "payload": "{}", "expires_at": expires_at},
            ).scalar_one_or_none()
            if claimed is None:
                return False
            connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload, expires_at, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), :expires_at, now())"""
                ),
                {
                    "key": f"v2:session:{session_hash}",
                    "payload": _json(payload),
                    "expires_at": expires_at,
                },
            )
            return True

    def get_session(self, session_hash: str) -> Mapping[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """SELECT payload FROM social_projection_state
                    WHERE projection_key=:key AND (expires_at IS NULL OR expires_at > now())"""
                ),
                {"key": f"v2:session:{session_hash}"},
            ).scalar_one_or_none()
        return row

    def revoke_session(self, session_hash: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """UPDATE social_projection_state
                    SET payload = payload || jsonb_build_object('revoked', true), updated_at=now()
                    WHERE projection_key=:key"""
                ),
                {"key": f"v2:session:{session_hash}"},
            )

    def revoke_authority_sessions(self, *, user_id: str | None, brand_id: str | None) -> int:
        if not user_id and not brand_id:
            return 0
        clauses = ["projection_key LIKE 'v2:session:%'"]
        parameters: dict[str, Any] = {}
        if user_id:
            clauses.append("payload->>'user_id'=:user_id")
            parameters["user_id"] = user_id
        if brand_id:
            clauses.append("payload->>'brand_id'=:brand_id")
            parameters["brand_id"] = brand_id
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    f"""UPDATE social_projection_state
                    SET payload = payload || jsonb_build_object('revoked', true), updated_at=now()
                    WHERE {" AND ".join(clauses)}"""
                ),
                parameters,
            )
            return result.rowcount

    def apply_event(
        self,
        *,
        nonce_hash: str,
        nonce_expires_at: datetime,
        event_id: str,
        event_type: str,
        entity_key: str,
        version: int,
        payload: Mapping[str, Any],
    ) -> str:
        with self.engine.begin() as connection:
            nonce = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload, expires_at, updated_at)
                    VALUES (:key, '{}'::jsonb, :expires_at, now())
                    ON CONFLICT (projection_key) DO UPDATE
                    SET payload='{}'::jsonb, expires_at=EXCLUDED.expires_at, updated_at=now()
                    WHERE social_projection_state.expires_at <= now()
                    RETURNING projection_key"""
                ),
                {"key": f"v2:hmac-nonce:{nonce_hash}", "expires_at": nonce_expires_at},
            ).scalar_one_or_none()
            if nonce is None:
                return "nonce_replayed"
            event = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), now())
                    ON CONFLICT (projection_key) DO NOTHING RETURNING projection_key"""
                ),
                {
                    "key": f"v2:event:{event_id}",
                    "payload": _json({"event_type": event_type, "version": version}),
                },
            ).scalar_one_or_none()
            if event is None:
                return "duplicate_ignored"
            result = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), now())
                    ON CONFLICT (projection_key) DO UPDATE
                    SET payload=EXCLUDED.payload, updated_at=now()
                    WHERE COALESCE((social_projection_state.payload->>'version')::bigint, -1)
                          < :version"""
                ),
                {"key": entity_key, "payload": _json(payload), "version": version},
            )
            return "applied" if result.rowcount else "stale_ignored"

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None:
        with self.engine.begin() as connection:
            return connection.execute(
                text("SELECT payload FROM social_projection_state WHERE projection_key=:key"),
                {"key": entity_key},
            ).scalar_one_or_none()


def _json(value: Mapping[str, Any]) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)

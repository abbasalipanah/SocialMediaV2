"""Schema-compatible PostgreSQL adapter for namespaced projection state."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from app.application.ports import ProjectionReplacement, ProjectionWrite


class ProjectionStateStore:
    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None) -> None:
        if engine is None and not database_url:
            raise ValueError("projection_database_required")
        self.engine = engine or create_engine(database_url, pool_pre_ping=True)

    def create_from_jti(
        self,
        *,
        jti_hash: str,
        session_hash: str,
        payload: Mapping[str, Any],
        expires_at: datetime,
    ) -> bool:
        expiry_payload = _json({"expires_at": expires_at.isoformat()})
        session_payload = _json({**payload, "expires_at": expires_at.isoformat()})
        with self.engine.begin() as connection:
            claimed = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload_json, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), now())
                    ON CONFLICT (projection_key) DO NOTHING
                    RETURNING projection_key"""
                ),
                {"key": f"v2:sso-jti:{jti_hash}", "payload": expiry_payload},
            ).scalar_one_or_none()
            if claimed is None:
                return False
            connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload_json, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), now())"""
                ),
                {
                    "key": f"v2:session:{session_hash}",
                    "payload": session_payload,
                },
            )
            return True

    def get_session(self, session_hash: str) -> Mapping[str, Any] | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """SELECT payload_json FROM social_projection_state
                    WHERE projection_key=:key
                      AND payload_json->>'expires_at' IS NOT NULL
                      AND (payload_json->>'expires_at')::timestamptz > now()"""
                ),
                {"key": f"v2:session:{session_hash}"},
            ).scalar_one_or_none()
        return row

    def revoke_session(self, session_hash: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """UPDATE social_projection_state
                    SET payload_json = payload_json || jsonb_build_object('revoked', true),
                        updated_at=now()
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
            clauses.append("payload_json->>'user_id'=:user_id")
            parameters["user_id"] = user_id
        if brand_id:
            clauses.append("payload_json->>'brand_id'=:brand_id")
            parameters["brand_id"] = brand_id
        with self.engine.begin() as connection:
            result = connection.execute(
                text(
                    f"""UPDATE social_projection_state
                    SET payload_json = payload_json || jsonb_build_object('revoked', true),
                        updated_at=now()
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
        projection_writes: tuple[ProjectionWrite, ...] = (),
        replacement: ProjectionReplacement | None = None,
    ) -> str:
        nonce_payload = _json({"expires_at": nonce_expires_at.isoformat()})
        with self.engine.begin() as connection:
            nonce = connection.execute(
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
                {"key": f"v2:hmac-nonce:{nonce_hash}", "payload": nonce_payload},
            ).scalar_one_or_none()
            if nonce is None:
                return "nonce_replayed"
            event = connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload_json, updated_at)
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
                    (projection_key, payload_json, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), now())
                    ON CONFLICT (projection_key) DO UPDATE
                    SET payload_json=EXCLUDED.payload_json, updated_at=now()
                    WHERE COALESCE(
                              (social_projection_state.payload_json->>'version')::bigint,
                              -1
                          )
                          < :version"""
                ),
                {"key": entity_key, "payload": _json(payload), "version": version},
            )
            if not result.rowcount:
                return "stale_ignored"
            for projection_write in projection_writes:
                _upsert_projection(connection, projection_write, version)
            if replacement is not None:
                _replace_projections(connection, replacement)
            return "applied"

    def get_projection(self, entity_key: str) -> Mapping[str, Any] | None:
        with self.engine.begin() as connection:
            return connection.execute(
                text(
                    "SELECT payload_json FROM social_projection_state WHERE projection_key=:key"
                ),
                {"key": entity_key},
            ).scalar_one_or_none()

    def list_projections(self, projection_key_prefix: str) -> list[Mapping[str, Any]]:
        with self.engine.begin() as connection:
            return list(
                connection.execute(
                    text(
                        """SELECT payload_json FROM social_projection_state
                        WHERE projection_key LIKE :prefix
                        ORDER BY projection_key"""
                    ),
                    {"prefix": f"{projection_key_prefix}%"},
                ).scalars()
            )


def _upsert_projection(
    connection: Connection, projection_write: ProjectionWrite, version: int
) -> None:
    payload = {**projection_write.payload, "version": version}
    if projection_write.insert_only:
        connection.execute(
            text(
                """INSERT INTO social_projection_state
                (projection_key, payload_json, updated_at)
                VALUES (:key, CAST(:payload AS jsonb), now())
                ON CONFLICT (projection_key) DO NOTHING"""
            ),
            {"key": projection_write.projection_key, "payload": _json(payload)},
        )
        return
    connection.execute(
        text(
            """INSERT INTO social_projection_state
            (projection_key, payload_json, updated_at)
            VALUES (:key, CAST(:payload AS jsonb), now())
            ON CONFLICT (projection_key) DO UPDATE
            SET payload_json=EXCLUDED.payload_json, updated_at=now()
            WHERE COALESCE(
                      (social_projection_state.payload_json->>'version')::bigint,
                      -1
                  )
                  < :version"""
        ),
        {
            "key": projection_write.projection_key,
            "payload": _json(payload),
            "version": version,
        },
    )


def _replace_projections(connection: Connection, replacement: ProjectionReplacement) -> None:
    desired_keys = {write.projection_key for write in replacement.writes}
    if len(desired_keys) != len(replacement.writes) or any(
        not key.startswith(replacement.projection_key_prefix) for key in desired_keys
    ):
        raise ValueError("invalid_projection_replacement")

    existing = connection.execute(
        text(
            """SELECT projection_key, payload_json FROM social_projection_state
            WHERE projection_key LIKE :prefix
            FOR UPDATE"""
        ),
        {"prefix": f"{replacement.projection_key_prefix}%"},
    ).mappings()
    for row in existing:
        projection_key = str(row["projection_key"])
        if projection_key in desired_keys:
            continue
        payload = dict(row["payload_json"])
        try:
            current_version = int(payload.get("version", -1))
        except (TypeError, ValueError):
            current_version = -1
        if current_version >= replacement.version:
            continue
        payload.update(
            {
                "active": False,
                "event_type": replacement.event_type,
                "snapshot_removed": True,
                "version": replacement.version,
            }
        )
        connection.execute(
            text(
                """UPDATE social_projection_state
                SET payload_json=CAST(:payload AS jsonb), updated_at=now()
                WHERE projection_key=:key"""
            ),
            {"key": projection_key, "payload": _json(payload)},
        )

    for projection_write in replacement.writes:
        _upsert_projection(connection, projection_write, replacement.version)


def _json(value: Mapping[str, Any]) -> str:
    import json

    return json.dumps(value, separators=(",", ":"), sort_keys=True)

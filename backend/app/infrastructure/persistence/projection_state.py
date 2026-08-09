"""V2-owned PostgreSQL adapter for replay-safe local SSO sessions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import Engine, create_engine, text


class ProjectionStateStore:
    """Persist only local session state in the V2-owned state table."""

    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None) -> None:
        if engine is None and not database_url:
            raise ValueError("session_database_required")
        if engine is None:
            assert database_url is not None
            engine = create_engine(database_url, pool_pre_ping=True)
        self.engine = engine

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
            _sync_session_brands(connection, payload)
            connection.execute(
                text(
                    """INSERT INTO social_projection_state
                    (projection_key, payload_json, updated_at)
                    VALUES (:key, CAST(:payload AS jsonb), now())"""
                ),
                {"key": f"v2:session:{session_hash}", "payload": session_payload},
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


def _json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _sync_session_brands(connection, payload: Mapping[str, Any]) -> None:
    """Copy the signed SSO Brand catalog into V2's own database."""

    scope = payload.get("brand_scope")
    if not isinstance(scope, Mapping):
        return
    brands = scope.get("brands")
    if not isinstance(brands, list):
        return
    normalized: list[tuple[int, str | None, int | None]] = []
    for item in brands:
        if not isinstance(item, Mapping):
            raise ValueError("session_brand_scope_invalid")
        try:
            brand_id = int(str(item["brand_id"]))
            parent_raw = item.get("parent_brand_id")
            parent_id = int(str(parent_raw)) if parent_raw is not None else None
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("session_brand_id_not_numeric") from exc
        if brand_id < 1 or (parent_id is not None and parent_id < 1):
            raise ValueError("session_brand_id_not_numeric")
        name_raw = item.get("name")
        name = str(name_raw).strip() or None if name_raw is not None else None
        normalized.append((brand_id, name, parent_id))

    for brand_id, name, _ in normalized:
        connection.execute(
            text(
                """INSERT INTO brands
                (id, tenant_id, name, parent_brand_id, active, created_at, updated_at)
                VALUES (:brand_id, 1, :name, NULL, true, now(), now())
                ON CONFLICT (id) DO UPDATE
                SET name=COALESCE(EXCLUDED.name, brands.name), active=true, updated_at=now()"""
            ),
            {"brand_id": brand_id, "name": name},
        )
    for brand_id, _, parent_id in normalized:
        connection.execute(
            text(
                """UPDATE brands SET parent_brand_id=:parent_id, updated_at=now()
                WHERE id=:brand_id"""
            ),
            {"brand_id": brand_id, "parent_id": parent_id},
        )

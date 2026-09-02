"""Guarded reconciliation for accounts whose provider access is no longer usable."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Engine, text

from app.core.write_policy import WritePolicy
from app.domain.platforms import PlatformId

RECONCILIATION_REASONS = frozenset(
    {
        "access_disconnected",
        "credentials_revoked",
        "reauthorization_required",
    }
)
RECONCILABLE_PLATFORMS = frozenset(
    {PlatformId.FACEBOOK, PlatformId.INSTAGRAM, PlatformId.TIKTOK}
)
_ACTIVE_LINK_STATUSES = frozenset({"active", "connected"})
_SUPPORTED_LINK_STATUSES = _ACTIVE_LINK_STATUSES | {"disconnected"}
_LOCK_ID = 724_662_219


class AccessReconciliationError(RuntimeError):
    """A target identity or persisted state changed before reconciliation."""


@dataclass(frozen=True)
class ExactAccountRef:
    link_id: int
    brand_id: int
    platform: PlatformId
    external_id: str

    def __post_init__(self) -> None:
        if (
            self.link_id < 1
            or self.brand_id < 1
            or self.platform not in RECONCILABLE_PLATFORMS
            or not self.external_id.strip()
        ):
            raise ValueError("account_reference_invalid")


@dataclass(frozen=True)
class AccessReconciliationResult:
    link_id: int
    brand_id: int
    platform: PlatformId
    external_id: str
    previous_link_status: str
    previous_health_status: str
    next_link_status: str
    next_health_status: str
    connection_id: int
    next_connection_status: str
    credentials_revoked: bool
    applied: bool


class AccountAccessReconciliationStore:
    """Remove exact inaccessible accounts from collection without deleting history."""

    def __init__(self, engine: Engine, write_policy: WritePolicy) -> None:
        self.engine = engine
        self._write_policy = write_policy

    def reconcile(
        self,
        targets: tuple[ExactAccountRef, ...],
        *,
        reason: str,
        apply: bool,
        revoke_tiktok_credentials: bool = False,
    ) -> tuple[AccessReconciliationResult, ...]:
        if not targets or len(targets) > 100:
            raise AccessReconciliationError("account_target_count_invalid")
        if reason not in RECONCILIATION_REASONS:
            raise AccessReconciliationError("reconciliation_reason_invalid")
        if len({target.link_id for target in targets}) != len(targets):
            raise AccessReconciliationError("account_target_duplicate")
        if revoke_tiktok_credentials and not any(
            target.platform is PlatformId.TIKTOK for target in targets
        ):
            raise AccessReconciliationError("tiktok_credential_target_missing")
        if apply:
            self._write_policy.assert_allows_mutation("account_access_reconcile")

        context = self.engine.begin() if apply else self.engine.connect()
        with context as connection:
            if apply:
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": _LOCK_ID},
                )
            rows = tuple(
                connection.execute(
                    text(
                        f"""SELECT la.id AS link_id, la.brand_id, la.platform,
                                   la.external_id, la.status AS link_status,
                                   la.health_status, la.connection_id, la.asset_id,
                                   pc.platform AS connection_platform,
                                   a.brand_id AS asset_brand_id,
                                   a.platform AS asset_platform,
                                   a.external_id AS asset_external_id
                            FROM linked_social_accounts AS la
                            JOIN platform_connections AS pc ON pc.id=la.connection_id
                            LEFT JOIN assets AS a ON a.id=la.asset_id
                            WHERE la.id=ANY(:link_ids)
                            ORDER BY la.id
                            {"FOR UPDATE OF la, pc" if apply else ""}"""
                    ),
                    {"link_ids": [target.link_id for target in targets]},
                ).mappings()
            )
            rows_by_id = {int(row["link_id"]): row for row in rows}
            if len(rows_by_id) != len(targets):
                raise AccessReconciliationError("account_target_missing")

            for target in targets:
                row = rows_by_id[target.link_id]
                asset_identity_changed = row["asset_id"] is not None and (
                    int(row["asset_brand_id"]) != target.brand_id
                    or str(row["asset_platform"]) != target.platform.value
                    or str(row["asset_external_id"]) != target.external_id
                )
                if (
                    int(row["brand_id"]) != target.brand_id
                    or str(row["platform"]) != target.platform.value
                    or str(row["external_id"]) != target.external_id
                    or asset_identity_changed
                ):
                    raise AccessReconciliationError(
                        f"account_target_identity_changed:{target.link_id}"
                    )
                if str(row["link_status"]) not in _SUPPORTED_LINK_STATUSES:
                    raise AccessReconciliationError(
                        f"account_target_state_unsupported:{target.link_id}"
                    )
                if (
                    str(row["link_status"]) in _ACTIVE_LINK_STATUSES
                    and row["asset_id"] is None
                ):
                    raise AccessReconciliationError(
                        f"active_account_asset_missing:{target.link_id}"
                    )

            target_ids = {target.link_id for target in targets}
            connection_ids = sorted({int(row["connection_id"]) for row in rows})
            sibling_rows = tuple(
                connection.execute(
                    text(
                        """SELECT id, connection_id, status
                           FROM linked_social_accounts
                           WHERE connection_id=ANY(:connection_ids)"""
                    ),
                    {"connection_ids": connection_ids},
                ).mappings()
            )
            remaining_active = {
                connection_id: sum(
                    int(sibling["id"]) not in target_ids
                    and str(sibling["status"]) in _ACTIVE_LINK_STATUSES
                    for sibling in sibling_rows
                    if int(sibling["connection_id"]) == connection_id
                )
                for connection_id in connection_ids
            }

            revoked_connection_ids: set[int] = set()
            credential_keys: tuple[str, ...] = ()
            if revoke_tiktok_credentials:
                revoked_connection_ids = {
                    int(rows_by_id[target.link_id]["connection_id"])
                    for target in targets
                    if target.platform is PlatformId.TIKTOK
                }
                if any(
                    remaining_active[connection_id]
                    for connection_id in revoked_connection_ids
                ):
                    raise AccessReconciliationError(
                        "tiktok_credential_connection_still_active"
                    )
                tiktok_projection_keys = tuple(
                    f"v2:tiktok:connection-credential:{connection_id}"
                    for connection_id in sorted(revoked_connection_ids)
                )
                tiktok_projection_rows = tuple(
                    connection.execute(
                        text(
                            f"""SELECT projection_key,
                                       payload_json->>'credential_reference'
                                         AS credential_reference
                                FROM social_projection_state
                                WHERE projection_key=ANY(:keys)
                                {"FOR UPDATE" if apply else ""}"""
                        ),
                        {"keys": list(tiktok_projection_keys)},
                    ).mappings()
                )
                if len(tiktok_projection_rows) != len(tiktok_projection_keys) or any(
                    not str(row["credential_reference"] or "")
                    for row in tiktok_projection_rows
                ):
                    raise AccessReconciliationError("tiktok_credential_reference_missing")
                credential_references = tuple(
                    str(row["credential_reference"]) for row in tiktok_projection_rows
                )
                if len(set(credential_references)) != len(credential_references):
                    raise AccessReconciliationError("tiktok_credential_reference_shared")
                reference_owners = set(
                    connection.execute(
                        text(
                            """SELECT projection_key
                               FROM social_projection_state
                               WHERE projection_key LIKE
                                     'v2:tiktok:connection-credential:%'
                                 AND payload_json->>'credential_reference'=ANY(:references)"""
                        ),
                        {"references": list(credential_references)},
                    ).scalars()
                )
                if reference_owners != set(tiktok_projection_keys):
                    raise AccessReconciliationError("tiktok_credential_reference_shared")
                credential_keys = tuple(
                    key
                    for reference in credential_references
                    for key in (
                        f"v2:credential:tiktok:{reference}:access",
                        f"v2:credential:tiktok:{reference}:refresh",
                    )
                )
                credential_rows = tuple(
                    connection.execute(
                        text(
                            f"""SELECT projection_key
                                FROM social_projection_state
                                WHERE projection_key=ANY(:keys)
                                {"FOR UPDATE" if apply else ""}"""
                        ),
                        {"keys": list(credential_keys)},
                    ).scalars()
                )
                if set(credential_rows) != set(credential_keys):
                    raise AccessReconciliationError("tiktok_credential_family_incomplete")

            if apply:
                link_ids = sorted(target_ids)
                asset_ids = sorted(
                    int(row["asset_id"]) for row in rows if row["asset_id"] is not None
                )
                connection.execute(
                    text(
                        """UPDATE linked_social_accounts
                           SET status='disconnected', health_status=:reason,
                               nightly_enabled=false, updated_at=now()
                           WHERE id=ANY(:link_ids)"""
                    ),
                    {"link_ids": link_ids, "reason": reason},
                )
                if asset_ids:
                    connection.execute(
                        text(
                            """UPDATE assets SET status='inactive', updated_at=now()
                               WHERE id=ANY(:asset_ids)"""
                        ),
                        {"asset_ids": asset_ids},
                    )
                connection.execute(
                    text(
                        """UPDATE brand_social_account_discoveries AS discovery
                           SET status='available', updated_at=now()
                           FROM linked_social_accounts AS account
                           WHERE account.id=ANY(:link_ids)
                             AND discovery.brand_id=account.brand_id
                             AND discovery.platform=account.platform
                             AND discovery.external_id=account.external_id"""
                    ),
                    {"link_ids": link_ids},
                )
                if asset_ids:
                    connection.execute(
                        text(
                            """UPDATE asset_sync_state
                               SET last_error=:reason, updated_at=now()
                               WHERE asset_id=ANY(:asset_ids)"""
                        ),
                        {"asset_ids": asset_ids, "reason": reason},
                    )
                if revoked_connection_ids:
                    connection.execute(
                        text(
                            """UPDATE social_projection_state
                               SET payload_json=payload_json ||
                                   jsonb_build_object('revoked', true),
                                   updated_at=now()
                               WHERE projection_key=ANY(:keys)"""
                        ),
                        {"keys": list(credential_keys)},
                    )

                connection_platforms = {
                    int(row["connection_id"]): str(row["connection_platform"])
                    for row in rows
                }
                for connection_id in connection_ids:
                    next_status = (
                        "connected" if remaining_active[connection_id] else "disconnected"
                    )
                    projection_status = (
                        "active" if remaining_active[connection_id] else "inactive"
                    )
                    connection.execute(
                        text(
                            """UPDATE platform_connections
                               SET status=:status, updated_at=now()
                               WHERE id=:connection_id"""
                        ),
                        {"connection_id": connection_id, "status": next_status},
                    )
                    projection_prefix = (
                        "v2:tiktok:connection-credential:"
                        if connection_platforms[connection_id] == PlatformId.TIKTOK.value
                        else "v2:meta:connection:"
                    )
                    projection_update = connection.execute(
                        text(
                            """UPDATE social_projection_state
                               SET status=:projection_status,
                                   payload_json=payload_json ||
                                     jsonb_build_object('state', CAST(:state AS text)),
                                   updated_at=now()
                               WHERE projection_key=:key"""
                        ),
                        {
                            "key": f"{projection_prefix}{connection_id}",
                            "projection_status": projection_status,
                            "state": next_status,
                        },
                    )
                    if projection_update.rowcount != 1:
                        raise AccessReconciliationError(
                            f"connection_projection_missing:{connection_id}"
                        )

            return tuple(
                AccessReconciliationResult(
                    link_id=target.link_id,
                    brand_id=target.brand_id,
                    platform=target.platform,
                    external_id=target.external_id,
                    previous_link_status=str(rows_by_id[target.link_id]["link_status"]),
                    previous_health_status=str(
                        rows_by_id[target.link_id]["health_status"]
                    ),
                    next_link_status="disconnected",
                    next_health_status=reason,
                    connection_id=int(rows_by_id[target.link_id]["connection_id"]),
                    next_connection_status=(
                        "connected"
                        if remaining_active[
                            int(rows_by_id[target.link_id]["connection_id"])
                        ]
                        else "disconnected"
                    ),
                    credentials_revoked=(
                        int(rows_by_id[target.link_id]["connection_id"])
                        in revoked_connection_ids
                    ),
                    applied=apply,
                )
                for target in sorted(targets, key=lambda item: item.link_id)
            )


def parse_exact_account_ref(value: str) -> ExactAccountRef:
    try:
        link_raw, brand_raw, platform_raw, external_id = value.split(":", 3)
        return ExactAccountRef(
            link_id=int(link_raw),
            brand_id=int(brand_raw),
            platform=PlatformId(platform_raw),
            external_id=external_id,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("account_reference_invalid") from exc


__all__ = [
    "AccessReconciliationError",
    "AccessReconciliationResult",
    "AccountAccessReconciliationStore",
    "ExactAccountRef",
    "RECONCILABLE_PLATFORMS",
    "RECONCILIATION_REASONS",
    "parse_exact_account_ref",
]

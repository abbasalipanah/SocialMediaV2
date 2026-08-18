"""Rotate one allowlisted TikTok credential family into V2 with encrypted recovery staging."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.ports.credentials import CredentialRef, SecretToken, TokenKind  # noqa: E402
from app.core import WritePolicy, load_settings  # noqa: E402
from app.domain.platforms import PlatformId  # noqa: E402
from app.infrastructure.credentials import (  # noqa: E402
    AesGcmTokenVault,
    ProjectionCredentialStore,
)
from app.infrastructure.providers.tiktok.accounts import (  # noqa: E402
    TikTokAccountsWireMapper,
    TikTokHttpTransport,
    parse_token,
    parse_token_info,
)

ALLOWED_LINK_IDS = frozenset({99, 100})
V1_PROVIDER_TIMERS = (
    "facebook-audience-canary.timer",
    "facebook-daily.timer",
    "facebook-followers-hourly.timer",
    "facebook-media-refresh-morning.timer",
    "facebook-media-refresh-night.timer",
    "facebook-monthly.timer",
    "facebook-weekly.timer",
    "instagram-daily.timer",
    "instagram-followers-hourly.timer",
    "instagram-media-refresh-morning.timer",
    "instagram-media-refresh-night.timer",
    "instagram-monthly.timer",
    "instagram-story.timer",
    "instagram-weekly.timer",
    "social-backfill-jobs.timer",
    "social-cover-repair.timer",
    "social-d1-coverage-check.timer",
    "social-daily-orchestration.timer",
    "social-rolling-refresh-monthly-close.timer",
    "social-rolling-refresh-nightly.timer",
    "social-rolling-refresh-weekly.timer",
    "tiktok-backfill-jobs.timer",
    "tiktok-organic-sync.timer",
)


class OwnershipTransferError(RuntimeError):
    """Sanitized transfer precondition or provider-contract failure."""


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument(
        "--link-id",
        type=int,
        choices=tuple(sorted(ALLOWED_LINK_IDS)),
        required=True,
    )
    return parser.parse_args()


def _load_env(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def _assert_closed_gates(settings: Any) -> None:
    if (
        settings.worker_schedule_enabled
        or settings.meta.collection_enabled
        or settings.meta.account_enabled
        or settings.meta_activation.gate_enabled
        or settings.tiktok.collection_enabled
        or settings.tiktok.account_enabled
        or settings.tiktok_activation.gate_enabled
        or settings.tiktok.advertiser_enabled
    ):
        raise OwnershipTransferError("provider_and_schedule_gates_must_be_disabled")
    for unit in V1_PROVIDER_TIMERS:
        result = subprocess.run(
            ("systemctl", "is-active", "--quiet", unit),
            check=False,
            capture_output=True,
        )
        if result.returncode == 0:
            raise OwnershipTransferError(f"v1_provider_timer_active:{unit}")


def _target(engine: Engine, link_id: int) -> dict[str, Any]:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """SELECT id,connection_id,brand_id,external_id,status,health_status
                       FROM linked_social_accounts
                       WHERE id=:link_id AND platform='tiktok'"""
                ),
                {"link_id": link_id},
            )
            .mappings()
            .one_or_none()
        )
        if (
            row is None
            or str(row["status"]) not in {"active", "connected"}
            or str(row["health_status"]) != "healthy"
        ):
            raise OwnershipTransferError("allowlisted_tiktok_link_unavailable")
        projection = connection.execute(
            text(
                """SELECT payload_json FROM social_projection_state
                   WHERE projection_key=:key"""
            ),
            {"key": f"v2:tiktok:connection-credential:{row['connection_id']}"},
        ).scalar_one_or_none()
    if not isinstance(projection, dict):
        raise OwnershipTransferError("tiktok_connection_projection_missing")
    if str(projection.get("business_id")) != str(row["external_id"]):
        raise OwnershipTransferError("tiktok_connection_identity_mismatch")
    reference = str(projection.get("credential_reference") or "")
    if not reference:
        raise OwnershipTransferError("tiktok_credential_reference_missing")
    return {
        "link_id": int(row["id"]),
        "connection_id": int(row["connection_id"]),
        "brand_id": int(row["brand_id"]),
        "business_id": str(row["external_id"]),
        "reference": reference,
    }


def _refs(reference: str, link_id: int) -> tuple[CredentialRef, ...]:
    staging = f"{reference}.ownership{link_id}"
    return (
        CredentialRef(PlatformId.TIKTOK, reference, TokenKind.ACCESS),
        CredentialRef(PlatformId.TIKTOK, reference, TokenKind.REFRESH),
        CredentialRef(PlatformId.TIKTOK, staging, TokenKind.ACCESS),
        CredentialRef(PlatformId.TIKTOK, staging, TokenKind.REFRESH),
    )


def _scopes_valid(settings: Any, scopes: tuple[str, ...]) -> bool:
    granted = set(scopes)
    required = set(settings.tiktok.required_scopes)
    allowed = required | set(settings.tiktok.optional_scopes)
    return required.issubset(granted) and granted.issubset(allowed)


def _audit(engine: Engine, target: dict[str, Any], state: str, resumed: bool) -> None:
    payload = json.dumps(
        {
            "format_version": 1,
            "state": state,
            "link_id": target["link_id"],
            "connection_id": target["connection_id"],
            "resumed_from_encrypted_staging": resumed,
            "updated_at": datetime.now(UTC).isoformat(),
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    with engine.begin() as connection:
        connection.execute(
            text(
                """INSERT INTO social_projection_state
                   (projection_key,brand_id,status,projection_source,payload_json,updated_at)
                   VALUES (:key,:brand_id,'active','tiktok_ownership_transfer',
                           CAST(:payload AS jsonb),now())
                   ON CONFLICT (projection_key) DO UPDATE
                   SET status='active',projection_source='tiktok_ownership_transfer',
                       payload_json=EXCLUDED.payload_json,updated_at=now()"""
            ),
            {
                "key": f"v2:tiktok:ownership-transfer:{target['connection_id']}",
                "brand_id": target["brand_id"],
                "payload": payload,
            },
        )


def _delete_staging(engine: Engine, references: tuple[CredentialRef, CredentialRef]) -> None:
    keys = [
        f"v2:credential:{item.platform.value}:{item.connection_id}:{item.token_kind.value}"
        for item in references
    ]
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM social_projection_state WHERE projection_key=ANY(:keys)"),
            {"keys": keys},
        )


def main() -> None:
    args = _arguments()
    _load_env(args.env)
    settings = load_settings()
    _assert_closed_gates(settings)
    if not settings.db.url:
        raise OwnershipTransferError("candidate_database_missing")
    engine = create_engine(settings.db.url, pool_pre_ping=True, hide_parameters=True)
    try:
        policy = WritePolicy.from_settings(settings)
        policy.assert_allows_mutation("tiktok_ownership_transfer")
        vault = AesGcmTokenVault.from_json(
            active_key_id=settings.meta_activation.credential_active_key_id,
            keyring_json=settings.meta_activation.credential_keyring_json,
        )
        credentials = ProjectionCredentialStore(engine, policy, vault)
        target = _target(engine, args.link_id)
        access_ref, refresh_ref, staged_access_ref, staged_refresh_ref = _refs(
            target["reference"], args.link_id
        )
        staged_access = credentials.get(staged_access_ref)
        staged_refresh = credentials.get(staged_refresh_ref)
        resumed = staged_access is not None and staged_refresh is not None
        if (staged_access is None) != (staged_refresh is None):
            raise OwnershipTransferError("encrypted_staging_pair_incomplete")

        mapper = TikTokAccountsWireMapper(settings.tiktok)
        provider_refresh_requests = 0
        if resumed:
            assert staged_access is not None and staged_refresh is not None
            access = staged_access
            refresh = staged_refresh
            grant_scopes: tuple[str, ...] | None = None
            transport = TikTokHttpTransport(
                post_urls=(settings.tiktok.token_info_url,),
                get_urls=(),
                timeout_seconds=settings.tiktok_activation.provider_timeout_seconds,
                max_retries=0,
                request_budget=1,
            )
        else:
            current_refresh = credentials.get(refresh_ref)
            if current_refresh is None:
                raise OwnershipTransferError("canonical_refresh_credential_unavailable")
            transport = TikTokHttpTransport(
                post_urls=(settings.tiktok.refresh_url, settings.tiktok.token_info_url),
                get_urls=(),
                timeout_seconds=settings.tiktok_activation.provider_timeout_seconds,
                max_retries=0,
                request_budget=2,
            )
            grant = parse_token(
                transport.post(
                    settings.tiktok.refresh_url,
                    data=mapper.refresh_fields(refresh_token=current_refresh.value),
                )
            )
            provider_refresh_requests = 1
            now = datetime.now(UTC)
            access = SecretToken(
                grant.access_token,
                expires_at=now + timedelta(seconds=grant.expires_in),
            )
            refresh = SecretToken(
                grant.refresh_token,
                expires_at=now + timedelta(seconds=grant.refresh_expires_in),
            )
            grant_scopes = grant.scopes
            credentials.put_many(
                ((staged_access_ref, access), (staged_refresh_ref, refresh))
            )
            _audit(engine, target, "encrypted_staged", resumed=False)
            if not _scopes_valid(settings, grant.scopes):
                raise OwnershipTransferError("refreshed_scope_contract_rejected")

        info = parse_token_info(
            transport.post(
                settings.tiktok.token_info_url,
                data=mapper.token_info_fields(access_token=access.value),
            )
        )
        if (
            info.business_id != target["business_id"]
            or not _scopes_valid(settings, info.scopes)
            or (grant_scopes is not None and set(info.scopes) != set(grant_scopes))
        ):
            raise OwnershipTransferError("refreshed_identity_or_scope_rejected")

        credentials.put_many(((access_ref, access), (refresh_ref, refresh)))
        stored_access = credentials.get(access_ref)
        stored_refresh = credentials.get(refresh_ref)
        if (
            stored_access is None
            or stored_refresh is None
            or not hmac.compare_digest(stored_access.value, access.value)
            or not hmac.compare_digest(stored_refresh.value, refresh.value)
        ):
            raise OwnershipTransferError("canonical_credential_verification_failed")
        _delete_staging(engine, (staged_access_ref, staged_refresh_ref))
        _audit(engine, target, "promoted", resumed=resumed)
        print(f"tiktok_ownership_link={target['link_id']}")
        print(f"tiktok_ownership_connection={target['connection_id']}")
        print(f"provider_refresh_requests={provider_refresh_requests}")
        print("provider_token_info_requests=1")
        print("credential_pair_atomic=true")
        print("encrypted_staging_cleared=true")
        print("tiktok_ownership_transfer=verified")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

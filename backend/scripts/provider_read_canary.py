"""Run bounded, refresh-free provider identity reads for explicit V2 link IDs.

The command refuses to run unless every live collection/schedule gate is closed.
It performs one GET per allowlisted link, never calls a token/refresh/revoke
endpoint, and verifies that the encrypted credential projection is unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.application.ports.credentials import CredentialRef, TokenKind  # noqa: E402
from app.application.ports.platforms import (  # noqa: E402
    ProviderAccount,
    ProviderCredential,
)
from app.core import WritePolicy, load_settings  # noqa: E402
from app.domain.platforms import PlatformId  # noqa: E402
from app.infrastructure.credentials import (  # noqa: E402
    AesGcmTokenVault,
    ProjectionCredentialStore,
)
from app.infrastructure.providers.meta.facebook.profile import (  # noqa: E402
    FacebookProfileReader,
)
from app.infrastructure.providers.meta.instagram.profile import (  # noqa: E402
    InstagramProfileReader,
)
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard  # noqa: E402
from app.infrastructure.providers.meta.transport import MetaTransport  # noqa: E402
from app.infrastructure.providers.tiktok.accounts import (  # noqa: E402
    TikTokAccountsActivationProvider,
    TikTokHttpTransport,
)


class CanaryError(RuntimeError):
    """A sanitized provider-read precondition or identity failure."""


class _GetOnlyTikTokTransport:
    def __init__(self, *, get_url: str, rejected_post_url: str, timeout_seconds: float) -> None:
        self._transport = TikTokHttpTransport(
            post_urls=(rejected_post_url,),
            get_urls=(get_url,),
            timeout_seconds=timeout_seconds,
            max_retries=0,
            request_budget=1,
        )

    @property
    def remaining_requests(self) -> int:
        return self._transport.remaining_requests

    def get(self, url: str, *, headers, params=None):
        return self._transport.get(url, headers=headers, params=params)

    def post(self, url: str, *, data) -> dict[str, object]:
        del url, data
        raise CanaryError("provider_post_disabled")


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path, required=True)
    parser.add_argument("--link-id", type=int, action="append", required=True)
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


def _credential_fingerprint(engine: Engine) -> tuple[str, int]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """SELECT projection_key,payload_json::text
                   FROM social_projection_state
                   WHERE projection_key LIKE 'v2:credential:%'
                      OR projection_key LIKE 'v2:credential-nonce:%'
                   ORDER BY projection_key"""
            )
        ).all()
    digest = hashlib.sha256()
    for key, payload in rows:
        digest.update(str(key).encode())
        digest.update(b"\0")
        digest.update(str(payload).encode())
        digest.update(b"\n")
    return digest.hexdigest(), len(rows)


def _target(engine: Engine, link_id: int) -> dict[str, Any]:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    """SELECT id,connection_id,platform,external_id
                       FROM linked_social_accounts
                       WHERE id=:link_id AND connection_id IS NOT NULL"""
                ),
                {"link_id": link_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise CanaryError(f"allowlisted_link_not_found:{link_id}")
        platform = PlatformId(str(row["platform"]))
        connection_id = int(row["connection_id"])
        projection_key = (
            f"v2:tiktok:connection-credential:{connection_id}"
            if platform is PlatformId.TIKTOK
            else f"v2:meta:connection:{connection_id}"
        )
        projection = connection.execute(
            text(
                """SELECT payload_json FROM social_projection_state
                   WHERE projection_key=:projection_key"""
            ),
            {"projection_key": projection_key},
        ).scalar_one_or_none()
    if not isinstance(projection, dict):
        raise CanaryError(f"connection_projection_missing:{link_id}")
    external_id = str(row["external_id"])
    if platform is PlatformId.TIKTOK:
        if str(projection.get("business_id")) != external_id:
            raise CanaryError(f"connection_identity_mismatch:{link_id}")
        reference = str(projection.get("credential_reference") or "")
    else:
        matching = [
            account
            for account in projection.get("accounts", [])
            if isinstance(account, dict)
            and account.get("platform") == platform.value
            and str(account.get("external_id")) == external_id
        ]
        if len(matching) != 1:
            raise CanaryError(f"connection_account_projection_mismatch:{link_id}")
        reference = str(matching[0].get("credential_reference") or "")
    if not reference:
        raise CanaryError(f"credential_reference_missing:{link_id}")
    return {
        "link_id": link_id,
        "platform": platform,
        "external_id": external_id,
        "credential_reference": reference,
    }


def main() -> None:
    args = _arguments()
    if len(args.link_id) != 3 or len(set(args.link_id)) != 3:
        raise CanaryError("exactly_three_unique_link_ids_required")
    _load_env(args.env)
    settings = load_settings()
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
        raise CanaryError("provider_and_schedule_gates_must_be_disabled")
    if not settings.db.url:
        raise CanaryError("candidate_database_missing")

    engine = create_engine(settings.db.url, pool_pre_ping=True, hide_parameters=True)
    try:
        vault = AesGcmTokenVault.from_json(
            active_key_id=settings.meta_activation.credential_active_key_id,
            keyring_json=settings.meta_activation.credential_keyring_json,
        )
        credentials = ProjectionCredentialStore(
            engine,
            WritePolicy.from_settings(settings),
            vault,
        )
        targets = [_target(engine, link_id) for link_id in args.link_id]
        if {target["platform"] for target in targets} != set(PlatformId):
            raise CanaryError("one_link_per_platform_required")
        before_hash, before_count = _credential_fingerprint(engine)
        results: list[str] = []
        failures: list[str] = []
        provider_get_requests = 0
        for target in targets:
            platform = target["platform"]
            try:
                token = credentials.get(
                    CredentialRef(
                        platform=platform,
                        connection_id=target["credential_reference"],
                        token_kind=TokenKind.ACCESS,
                    )
                )
                if token is None:
                    raise CanaryError(f"access_credential_unavailable:{target['link_id']}")
                if platform is PlatformId.TIKTOK:
                    if token.expires_at is None or token.expires_at <= datetime.now(
                        UTC
                    ) + timedelta(minutes=5):
                        raise CanaryError("tiktok_refresh_free_window_unavailable")
                    transport = _GetOnlyTikTokTransport(
                        get_url=settings.tiktok.token_info_url,
                        rejected_post_url=settings.tiktok.refresh_url,
                        timeout_seconds=settings.tiktok_activation.provider_timeout_seconds,
                    )
                    provider_get_requests += 1
                    grant = TikTokAccountsActivationProvider(
                        config=settings.tiktok,
                        transport=transport,
                    ).inspect(access_token=token.value)
                    required = set(settings.tiktok.required_scopes)
                    allowed = required | set(settings.tiktok.optional_scopes)
                    if (
                        grant.business_id != target["external_id"]
                        or not required.issubset(grant.scopes)
                        or not set(grant.scopes).issubset(allowed)
                        or transport.remaining_requests != 0
                    ):
                        raise CanaryError("tiktok_token_identity_or_scope_mismatch")
                    results.append(f"tiktok:{target['link_id']}:token_info")
                    continue

                provider_credential = ProviderCredential(access_token=token.value)
                meta = MetaTransport(
                    credential=provider_credential,
                    rate_guard=MetaRateGuard(sleeper=lambda _: None),
                    base_url=settings.meta.graph_base_url,
                    api_version=settings.meta.graph_version,
                    timeout_seconds=settings.meta_activation.provider_timeout_seconds,
                    max_retries=0,
                    egress_enabled=True,
                )
                try:
                    account = ProviderAccount(
                        platform=platform,
                        account_id=target["external_id"],
                        credential=provider_credential,
                    )
                    reader = (
                        FacebookProfileReader(meta)
                        if platform is PlatformId.FACEBOOK
                        else InstagramProfileReader(meta)
                    )
                    provider_get_requests += 1
                    if reader.fetch_profile(account).account_id != target["external_id"]:
                        raise CanaryError("meta_profile_identity_mismatch")
                finally:
                    meta.close()
                results.append(f"{platform.value}:{target['link_id']}:profile")
            except Exception as exc:
                failures.append(
                    f"{platform.value}:{target['link_id']}:{type(exc).__name__}"
                )

        after_hash, after_count = _credential_fingerprint(engine)
        if (before_hash, before_count) != (after_hash, after_count):
            raise CanaryError("credential_projection_changed")
    finally:
        engine.dispose()

    print("refresh_free_real_read_canaries=" + ",".join(sorted(results)))
    print("refresh_free_real_read_failures=" + ",".join(sorted(failures)))
    print(f"provider_get_requests={provider_get_requests}")
    print("provider_post_requests=0")
    print("provider_refresh_requests=0")
    print(f"credential_projection_rows={before_count}")
    print("credential_fingerprint_unchanged=true")
    print("provider_collection_and_schedule_gates=disabled")
    if failures:
        raise CanaryError("one_or_more_provider_reads_failed")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"provider_read_canary=failed:{type(exc).__name__}")
        raise SystemExit(1) from None

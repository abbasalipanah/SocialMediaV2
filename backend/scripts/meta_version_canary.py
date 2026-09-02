"""Read-only Meta Graph contract canary for an explicit API version.

The command performs no token refresh and no database write. It verifies one
Facebook Page, one Instagram account, their daily/audience/content surfaces,
and every configured Instagram content/Story insight metric. Only sanitized
metric names and provider error codes are printed.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text

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
from app.infrastructure.persistence.social_v2 import SocialCollectionTargetStore  # noqa: E402
from app.infrastructure.providers.meta.audience import MetaAudienceReader  # noqa: E402
from app.infrastructure.providers.meta.facebook.content import (  # noqa: E402
    FacebookContentReader,
)
from app.infrastructure.providers.meta.facebook.daily_metrics import (  # noqa: E402
    FacebookDailyMetricsReader,
)
from app.infrastructure.providers.meta.facebook.profile import (  # noqa: E402
    FacebookProfileReader,
)
from app.infrastructure.providers.meta.instagram.content import (  # noqa: E402
    InstagramContentReader,
)
from app.infrastructure.providers.meta.instagram.content_insights import (  # noqa: E402
    MEDIA_INSIGHT_METRICS,
    STORY_INSIGHT_METRICS,
)
from app.infrastructure.providers.meta.instagram.daily_metrics import (  # noqa: E402
    InstagramDailyMetricsReader,
)
from app.infrastructure.providers.meta.instagram.profile import (  # noqa: E402
    InstagramProfileReader,
)
from app.infrastructure.providers.meta.page_token import resolve_page_access_token  # noqa: E402
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard  # noqa: E402
from app.infrastructure.providers.meta.transport import (  # noqa: E402
    MetaTransport,
    MetaTransportError,
)


class CanaryError(RuntimeError):
    """A sanitized read-canary failure."""


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", type=Path)
    parser.add_argument("--api-version", default="v26.0")
    parser.add_argument("--facebook-link-id", type=int, required=True)
    parser.add_argument("--instagram-link-id", type=int, required=True)
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


def _credential_fingerprint(engine) -> str:
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
    return digest.hexdigest()


def _transport(settings, credential: ProviderCredential, api_version: str) -> MetaTransport:
    return MetaTransport(
        credential=credential,
        rate_guard=MetaRateGuard(sleeper=lambda _seconds: None),
        base_url=settings.meta.graph_base_url,
        api_version=api_version,
        timeout_seconds=settings.meta_activation.provider_timeout_seconds,
        max_retries=0,
        egress_enabled=True,
    )


def _metric_contract(
    transport: MetaTransport,
    content_id: str,
    metrics: tuple[str, ...],
    *,
    story: bool,
) -> tuple[list[str], list[str]]:
    accepted: list[str] = []
    rejected: list[str] = []
    for metric in metrics:
        try:
            transport.get(f"{content_id}/insights", {"metric": metric})
        except MetaTransportError as exc:
            rejected.append(f"{metric}:{exc.code}")
        else:
            accepted.append(metric)
    if story:
        try:
            transport.get(
                f"{content_id}/insights",
                {"metric": "navigation", "breakdown": "story_navigation_action_type"},
            )
        except MetaTransportError as exc:
            rejected.append(f"navigation_breakdown:{exc.code}")
        else:
            accepted.append("navigation_breakdown")
    return accepted, rejected


def main() -> int:
    args = _arguments()
    if args.env is not None:
        _load_env(args.env)
    # Load the candidate contract even while the installed production env is
    # still pinned to the old version. These are endpoint selectors, not gates.
    os.environ["SOCIAL_META_GRAPH_VERSION"] = args.api_version
    os.environ["SOCIAL_META_AUTHORIZATION_URL"] = (
        f"https://www.facebook.com/{args.api_version}/dialog/oauth"
    )
    os.environ["SOCIAL_META_TOKEN_URL"] = (
        f"https://graph.facebook.com/{args.api_version}/oauth/access_token"
    )
    settings = load_settings()
    if not settings.db.url:
        raise CanaryError("database_missing")
    engine = create_engine(settings.db.url, pool_pre_ping=True, hide_parameters=True)
    before = _credential_fingerprint(engine)
    vault = AesGcmTokenVault.from_json(
        active_key_id=settings.meta_activation.credential_active_key_id,
        keyring_json=settings.meta_activation.credential_keyring_json,
    )
    credentials = ProjectionCredentialStore(
        engine,
        WritePolicy.from_settings(settings),
        vault,
    )
    targets = SocialCollectionTargetStore(engine, WritePolicy.from_settings(settings))
    rows = targets.list_connected(
        platforms=(PlatformId.FACEBOOK, PlatformId.INSTAGRAM)
    )
    selected = {
        row.link_id: row
        for row in rows
        if row.link_id in {args.facebook_link_id, args.instagram_link_id}
    }
    if set(selected) != {args.facebook_link_id, args.instagram_link_id}:
        raise CanaryError("allowlisted_target_unavailable")
    if selected[args.facebook_link_id].platform is not PlatformId.FACEBOOK:
        raise CanaryError("facebook_target_mismatch")
    if selected[args.instagram_link_id].platform is not PlatformId.INSTAGRAM:
        raise CanaryError("instagram_target_mismatch")

    yesterday = date.today() - timedelta(days=1)
    output: list[str] = []
    for link_id in (args.facebook_link_id, args.instagram_link_id):
        row = selected[link_id]
        secret = credentials.get(
            CredentialRef(
                platform=row.platform,
                connection_id=row.credential_reference,
                token_kind=TokenKind.ACCESS,
            )
        )
        if secret is None:
            raise CanaryError(f"credential_unavailable:{link_id}")
        credential = ProviderCredential(access_token=secret.value)
        lookup = None
        if row.platform is PlatformId.FACEBOOK:
            lookup = _transport(settings, credential, args.api_version)
            page_token = resolve_page_access_token(
                lookup,
                page_id=row.external_id,
                fallback_token=secret.value,
            )
            credential = ProviderCredential(access_token=page_token)
        transport = _transport(settings, credential, args.api_version)
        account = ProviderAccount(
            platform=row.platform,
            account_id=row.external_id,
            credential=credential,
        )
        try:
            if row.platform is PlatformId.FACEBOOK:
                profile = FacebookProfileReader(transport).fetch_profile(account)
                daily = FacebookDailyMetricsReader(transport).fetch_daily_metrics(
                    account, since=yesterday, until=yesterday
                )
                audience = MetaAudienceReader(
                    transport, platform=PlatformId.FACEBOOK
                ).fetch_audience(account)
                content = FacebookContentReader(
                    transport, insights=True, page_size=1
                ).list_content(account)
                output.append(
                    "facebook="
                    f"profile:{profile.account_id == row.external_id},"
                    f"daily:{len(daily)},audience:{len(audience.breakdowns)},"
                    f"content:{len(content.items)}"
                )
                continue

            profile = InstagramProfileReader(transport).fetch_profile(account)
            daily = InstagramDailyMetricsReader(transport).fetch_daily_metrics(
                account, since=yesterday, until=yesterday
            )
            audience = MetaAudienceReader(
                transport, platform=PlatformId.INSTAGRAM
            ).fetch_audience(account)
            content = InstagramContentReader(
                transport, insights=False, page_size=1
            ).list_content(account)
            media_accepted: list[str] = []
            media_rejected: list[str] = []
            if content.items:
                media_accepted, media_rejected = _metric_contract(
                    transport,
                    content.items[0].external_id,
                    MEDIA_INSIGHT_METRICS,
                    story=False,
                )
            stories = InstagramContentReader(
                transport, stories=True, insights=False, page_size=100
            ).list_content(account)
            story_accepted: list[str] = []
            story_rejected: list[str] = []
            if stories.items:
                story_accepted, story_rejected = _metric_contract(
                    transport,
                    stories.items[0].external_id,
                    STORY_INSIGHT_METRICS,
                    story=True,
                )
            output.extend(
                (
                    "instagram="
                    f"profile:{profile.account_id == row.external_id},"
                    f"daily:{len(daily)},audience:{len(audience.breakdowns)},"
                    f"content:{len(content.items)},stories:{len(stories.items)}",
                    "instagram_media_metrics_accepted=" + ",".join(media_accepted),
                    "instagram_media_metrics_rejected=" + ",".join(media_rejected),
                    "instagram_story_metrics_accepted=" + ",".join(story_accepted),
                    "instagram_story_metrics_rejected=" + ",".join(story_rejected),
                )
            )
        finally:
            transport.close()
            if lookup is not None:
                lookup.close()

    after = _credential_fingerprint(engine)
    engine.dispose()
    if before != after:
        raise CanaryError("credential_projection_changed")
    print(f"meta_version_canary={args.api_version}")
    print("read_only=true")
    print("credential_fingerprint_unchanged=true")
    for line in output:
        print(line)
    print(f"completed_at={datetime.now(UTC).isoformat()}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        reason = str(exc).strip() or "unspecified"
        print(f"meta_version_canary=failed:{type(exc).__name__}:{reason}")
        raise SystemExit(1) from None

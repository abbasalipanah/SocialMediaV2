"""Standalone V2 collection runner for linked Meta and TikTok accounts."""

from __future__ import annotations

import argparse
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import Engine, create_engine, text

from app.application.ports.credentials import CredentialRef, SecretToken, TokenKind
from app.application.ports.platforms import (
    ProviderAccount,
    ProviderCredential,
    ProviderRecord,
)
from app.application.ports.platforms.comments import CommentsReader
from app.application.ports.platforms.content import ContentReader
from app.application.ports.platforms.profile import DailyMetricsReader, ProfileReader
from app.application.services.collection import (
    CollectionStatus,
    CollectionTarget,
    collect_audience,
    collect_comments,
    collect_content,
    collect_daily_metrics,
    collect_profile,
)
from app.application.services.collection.media import ContentMediaWriter, FetchedMedia
from app.core import AppSettings, ConfigurationError, WritePolicy, load_settings
from app.domain.metrics import MetricId, bootstrap_metric_catalog
from app.domain.platforms import PlatformId
from app.infrastructure.checkpoints import ProjectionCheckpointStore
from app.infrastructure.credentials import AesGcmTokenVault, ProjectionCredentialStore
from app.infrastructure.persistence.media_files import AtomicMediaFiles
from app.infrastructure.persistence.social_v2 import (
    SocialCollectionTargetStore,
    SocialCommentStore,
    SocialContentStore,
    SocialMediaStore,
    SocialMetricStore,
)
from app.infrastructure.persistence.social_v2.collection_targets import (
    CollectionTargetRow,
)
from app.infrastructure.providers.meta.audience import MetaAudienceReader
from app.infrastructure.providers.meta.facebook.comments import FacebookCommentsReader
from app.infrastructure.providers.meta.facebook.content import FacebookContentReader
from app.infrastructure.providers.meta.facebook.daily_metrics import (
    FacebookDailyMetricsReader,
)
from app.infrastructure.providers.meta.facebook.profile import FacebookProfileReader
from app.infrastructure.providers.meta.instagram.comments import InstagramCommentsReader
from app.infrastructure.providers.meta.instagram.content import InstagramContentReader
from app.infrastructure.providers.meta.instagram.daily_metrics import (
    InstagramDailyMetricsReader,
)
from app.infrastructure.providers.meta.instagram.profile import InstagramProfileReader
from app.infrastructure.providers.meta.page_token import resolve_page_access_token
from app.infrastructure.providers.meta.rate_guard import MetaRateGuard
from app.infrastructure.providers.meta.transport import MetaTransport
from app.infrastructure.providers.tiktok.accounts import (
    TikTokAccountsWireMapper,
    TikTokAudienceReader,
    TikTokCommentsReader,
    TikTokContentReader,
    TikTokDailyMetricsReader,
    TikTokHttpTransport,
    TikTokProfileReader,
    parse_token,
    parse_token_info,
)

logger = logging.getLogger(__name__)

MAX_MEDIA_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class WorkerAccountResult:
    platform: str
    brand_id: int
    asset_id: int
    status: str
    metric_count: int = 0
    content_count: int = 0
    comment_count: int = 0
    media_count: int = 0
    error_code: str | None = None


@dataclass(frozen=True)
class TikTokAccessContext:
    access_token: str
    scopes: frozenset[str]


class StandaloneCollector:
    def __init__(self, settings: AppSettings, engine: Engine) -> None:
        self.settings = settings
        self.engine = engine
        self.policy = WritePolicy.from_settings(settings)
        self.policy.assert_allows_mutation("standalone_collection")
        try:
            vault = AesGcmTokenVault.from_json(
                active_key_id=settings.meta_activation.credential_active_key_id,
                keyring_json=settings.meta_activation.credential_keyring_json,
            )
        except Exception as exc:
            raise ConfigurationError("Worker credential keyring is invalid") from exc
        catalog = bootstrap_metric_catalog()
        self.credentials = ProjectionCredentialStore(engine, self.policy, vault)
        self.targets = SocialCollectionTargetStore(engine, self.policy)
        self.metrics = SocialMetricStore(engine, self.policy, catalog)
        self.content = SocialContentStore(engine, self.policy)
        self.comments = SocialCommentStore(engine, self.policy)
        self.checkpoints = ProjectionCheckpointStore(engine, self.policy)
        self.media_store = SocialMediaStore(engine, self.policy)
        self.media_files = (
            AtomicMediaFiles(Path(settings.media_storage_root))
            if settings.media_storage_root
            else None
        )
        self.media_fetcher = _MediaFetcher() if self.media_files is not None else None

    def close(self) -> None:
        if self.media_fetcher is not None:
            self.media_fetcher.close()

    def collect_connected(
        self,
        *,
        platforms: tuple[PlatformId, ...],
        brand_id: int | None,
        asset_id: int | None,
    ) -> tuple[WorkerAccountResult, ...]:
        selected = tuple(
            platform
            for platform in platforms
            if (
                platform in {PlatformId.FACEBOOK, PlatformId.INSTAGRAM}
                and self.settings.meta.collection_enabled
            )
            or (
                platform is PlatformId.TIKTOK
                and self.settings.tiktok.collection_enabled
            )
        )
        if not selected:
            raise ConfigurationError("No requested V2 collector is enabled")
        rows = self.targets.list_connected(
            platforms=selected,
            brand_id=brand_id,
            asset_id=asset_id,
        )
        results: list[WorkerAccountResult] = []
        for row in rows:
            try:
                result = self._collect(row)
                self.targets.mark_success(row, datetime.now(UTC))
            except Exception as exc:
                error_code = _error_code(exc)
                self.targets.mark_failure(row, error_code)
                result = WorkerAccountResult(
                    platform=row.platform.value,
                    brand_id=row.brand_id,
                    asset_id=row.asset_id,
                    status="failed",
                    error_code=error_code,
                )
            results.append(result)
        return tuple(results)

    def verify_pending_tiktok(self, connection_id: int) -> WorkerAccountResult:
        pending = self.targets.pending_tiktok(connection_id)
        if pending is None:
            raise ValueError("pending_tiktok_connection_not_found")
        context = self._tiktok_access_context(
            pending.credential_reference, pending.external_id
        )
        provider_account = ProviderAccount(
            platform=PlatformId.TIKTOK,
            account_id=pending.external_id,
            credential=ProviderCredential(access_token=context.access_token),
        )
        profile_reader, _, _, _, _ = self._tiktok_readers(
            provider_account, scopes=context.scopes
        )
        snapshot = profile_reader.fetch_profile(provider_account)
        asset_id = self.targets.create_tiktok_asset(pending, snapshot.display_name)
        row = CollectionTargetRow(
            link_id=pending.link_id,
            connection_id=pending.connection_id,
            asset_id=asset_id,
            brand_id=pending.brand_id,
            platform=PlatformId.TIKTOK,
            external_id=pending.external_id,
            display_name=snapshot.display_name,
            credential_reference=pending.credential_reference,
            backfill_status="pending",
        )
        result = self._collect_tiktok(
            row,
            provider_account=provider_account,
            granted_scopes=context.scopes,
        )
        completed_at = datetime.now(UTC)
        self.targets.complete_tiktok_canary(
            pending,
            asset_id=asset_id,
            synced_at=completed_at,
        )
        return result

    def _collect(self, row: CollectionTargetRow) -> WorkerAccountResult:
        if row.platform is PlatformId.TIKTOK:
            return self._collect_tiktok(row)
        return self._collect_meta(row)

    def _collect_meta(self, row: CollectionTargetRow) -> WorkerAccountResult:
        token = self._access_token(row.platform, row.credential_reference)
        if row.platform is PlatformId.FACEBOOK:
            # Published posts and Page insights are refused with the connected
            # user's token even though the Page profile answers, so a healthy
            # looking credential still collected nothing.
            lookup = MetaTransport(
                credential=ProviderCredential(access_token=token),
                rate_guard=MetaRateGuard(sleeper=time.sleep),
                base_url=self.settings.meta.graph_base_url,
                api_version=self.settings.meta.graph_version,
                timeout_seconds=self.settings.meta_activation.provider_timeout_seconds,
                egress_enabled=True,
            )
            try:
                token = resolve_page_access_token(
                    lookup, page_id=row.external_id, fallback_token=token
                )
            finally:
                lookup.close()
        account = ProviderAccount(
            platform=row.platform,
            account_id=row.external_id,
            credential=ProviderCredential(access_token=token),
        )
        transport = MetaTransport(
            credential=account.credential,
            rate_guard=MetaRateGuard(sleeper=time.sleep),
            base_url=self.settings.meta.graph_base_url,
            api_version=self.settings.meta.graph_version,
            timeout_seconds=self.settings.meta_activation.provider_timeout_seconds,
            egress_enabled=True,
        )
        target = CollectionTarget(
            account=account,
            local_account_id=row.asset_id,
            brand_id=row.brand_id,
        )
        try:
            partial_errors: set[str] = set()
            profile_reader: ProfileReader
            daily_reader: DailyMetricsReader
            content_reader: ContentReader
            comments_reader: CommentsReader
            if row.platform is PlatformId.FACEBOOK:
                profile_reader = FacebookProfileReader(transport)
                daily_reader = FacebookDailyMetricsReader(transport)
                content_reader = FacebookContentReader(transport)
                comments_reader = FacebookCommentsReader(transport)
            else:
                profile_reader = InstagramProfileReader(transport)
                daily_reader = InstagramDailyMetricsReader(transport)
                content_reader = InstagramContentReader(transport, insights=True)
                comments_reader = InstagramCommentsReader(transport)
            audience_reader = MetaAudienceReader(transport, platform=row.platform)
            profile = collect_profile(
                target=target,
                reader=profile_reader,
                metric_store=self.metrics,
            )
            today = date.today()
            since = (
                today - timedelta(days=29)
                if row.backfill_status != "complete"
                else today - timedelta(days=1)
            )
            daily = collect_daily_metrics(
                target=target,
                reader=daily_reader,
                metric_store=self.metrics,
                since=since,
                until=today,
            )
            try:
                audience = collect_audience(
                    target=target,
                    reader=audience_reader,
                    metric_store=self.metrics,
                )
                if audience.status is not CollectionStatus.SUCCESS:
                    partial_errors.add("audience_partial_or_unavailable")
            except Exception:
                audience = None
                partial_errors.add("audience_unavailable")
            comment_count = 0

            def persist_related(item: ProviderRecord) -> int:
                nonlocal comment_count
                try:
                    comments = collect_comments(
                        target=target,
                        content_id=item.external_id,
                        reader=comments_reader,
                        comment_store=self.comments,
                        max_pages=20,
                    )
                    comment_count += comments.comment_count
                    if comments.status is not CollectionStatus.SUCCESS:
                        partial_errors.add("comments_partial")
                except Exception:
                    partial_errors.add("comments_unavailable")
                try:
                    return self._persist_media(target, item)
                except Exception:
                    partial_errors.add("media_unavailable")
                    return 0

            # Guarded like comments, media and stories already are. Left bare,
            # a provider refusal here discarded the profile, daily metrics and
            # audience this account had already collected, and reported the run
            # as a total failure.
            content_count = 0
            content_media_count = 0
            try:
                content = collect_content(
                    target=target,
                    reader=content_reader,
                    content_store=self.content,
                    checkpoint_store=self.checkpoints,
                    record_sink=persist_related,
                    max_pages=100,
                )
                content_count = content.content_count
                content_media_count = content.media_count
                if content.status is not CollectionStatus.SUCCESS:
                    partial_errors.add("content_partial")
            except Exception as exc:
                logger.warning(
                    "content_read_failed platform=%s asset_id=%s reason=%s",
                    row.platform.value,
                    row.asset_id,
                    _error_code(exc),
                )
                partial_errors.add("content_unavailable")
            story_content_count = 0
            story_media_count = 0
            if row.platform is PlatformId.INSTAGRAM:
                story_reader = InstagramContentReader(
                    transport,
                    stories=True,
                    insights=True,
                )

                def persist_story_media(item: ProviderRecord) -> int:
                    try:
                        return self._persist_media(target, item)
                    except Exception:
                        partial_errors.add("story_media_unavailable")
                        return 0

                try:
                    stories = collect_content(
                        target=target,
                        reader=story_reader,
                        content_store=self.content,
                        checkpoint_store=self.checkpoints,
                        record_sink=persist_story_media,
                        checkpoint_account_id=f"{account.account_id}.stories",
                        max_pages=20,
                    )
                    story_content_count = stories.content_count
                    story_media_count = stories.media_count
                    if stories.status is not CollectionStatus.SUCCESS:
                        partial_errors.add("stories_partial")
                except Exception:
                    partial_errors.add("stories_unavailable")
            return WorkerAccountResult(
                platform=row.platform.value,
                brand_id=row.brand_id,
                asset_id=row.asset_id,
                status="partial" if partial_errors else "success",
                metric_count=(
                    profile.metric_count
                    + daily.metric_count
                    + (audience.metric_count if audience is not None else 0)
                ),
                content_count=content_count + story_content_count,
                comment_count=comment_count,
                media_count=content_media_count + story_media_count,
                error_code=_partial_error_code(partial_errors),
            )
        finally:
            transport.close()

    def _collect_tiktok(
        self,
        row: CollectionTargetRow,
        *,
        provider_account: ProviderAccount | None = None,
        granted_scopes: frozenset[str] | None = None,
    ) -> WorkerAccountResult:
        if provider_account is None:
            context = self._tiktok_access_context(
                row.credential_reference, row.external_id
            )
            provider_account = ProviderAccount(
                platform=PlatformId.TIKTOK,
                account_id=row.external_id,
                credential=ProviderCredential(
                    access_token=context.access_token
                ),
            )
            granted_scopes = context.scopes
        if granted_scopes is None:
            raise PermissionError("provider_scope_context_unavailable")
        profile_reader, daily_reader, content_reader, audience_reader, comments_reader = (
            self._tiktok_readers(provider_account, scopes=granted_scopes)
        )
        target = CollectionTarget(
            account=provider_account,
            local_account_id=row.asset_id,
            brand_id=row.brand_id,
        )
        profile = collect_profile(
            target=target,
            reader=profile_reader,
            metric_store=self.metrics,
        )
        until = date.today() - timedelta(days=1)
        since = (
            until - timedelta(days=29)
            if row.backfill_status != "complete"
            else until
        )
        daily = collect_daily_metrics(
            target=target,
            reader=daily_reader,
            metric_store=self.metrics,
            since=since,
            until=until,
        )
        partial_errors: set[str] = set()
        try:
            audience = collect_audience(
                target=target,
                reader=audience_reader,
                metric_store=self.metrics,
            )
            if audience.status is not CollectionStatus.SUCCESS:
                partial_errors.add("audience_partial_or_unavailable")
        except Exception:
            audience = None
            partial_errors.add("audience_unavailable")
        totals: dict[MetricId, int] = {}
        comment_count = 0
        commented_videos = 0

        def persist_related(item: ProviderRecord) -> int:
            nonlocal comment_count, commented_videos
            raw_metrics = item.fields.get("metric_values")
            if isinstance(raw_metrics, dict):
                for metric_id, value in raw_metrics.items():
                    if isinstance(metric_id, MetricId) and isinstance(value, int):
                        totals[metric_id] = totals.get(metric_id, 0) + value
            if comments_reader is not None and commented_videos < 10:
                commented_videos += 1
                try:
                    comments = collect_comments(
                        target=target,
                        content_id=item.external_id,
                        reader=comments_reader,
                        comment_store=self.comments,
                        max_pages=5,
                    )
                    comment_count += comments.comment_count
                    if comments.status is not CollectionStatus.SUCCESS:
                        partial_errors.add("comments_partial")
                except Exception:
                    partial_errors.add("comments_unavailable")
            try:
                return self._persist_media(target, item)
            except Exception:
                partial_errors.add("media_unavailable")
                return 0

        content = collect_content(
            target=target,
            reader=content_reader,
            content_store=self.content,
            checkpoint_store=self.checkpoints,
            record_sink=persist_related,
            max_pages=100,
        )
        for metric_id, value in totals.items():
            from app.application.ports.persistence import MetricPoint

            self.metrics.upsert(
                MetricPoint(
                    platform=PlatformId.TIKTOK,
                    account_id=row.asset_id,
                    brand_id=row.brand_id,
                    observed_on=date.today(),
                    metric_id=metric_id,
                    value=value,
                )
            )
        return WorkerAccountResult(
            platform=row.platform.value,
            brand_id=row.brand_id,
            asset_id=row.asset_id,
            status="partial" if partial_errors else "success",
            metric_count=(
                profile.metric_count
                + daily.metric_count
                + len(totals)
                + (audience.metric_count if audience is not None else 0)
            ),
            content_count=content.content_count,
            comment_count=comment_count,
            media_count=content.media_count,
            error_code=_partial_error_code(partial_errors),
        )

    def _tiktok_readers(
        self,
        account: ProviderAccount,
        *,
        scopes: frozenset[str],
    ):
        config = self.settings.tiktok
        comment_enabled = "comment.list" in scopes
        get_urls = [config.profile_url, config.video_list_url]
        if comment_enabled:
            get_urls.append(config.comment_list_url)
        transport = TikTokHttpTransport(
            post_urls=(config.refresh_url,),
            get_urls=tuple(get_urls),
            timeout_seconds=self.settings.tiktok_activation.provider_timeout_seconds,
            max_retries=3,
            request_budget=500,
        )
        wire = TikTokAccountsWireMapper(config)
        headers = {"Access-Token": account.credential.access_token}
        profile = TikTokProfileReader(
            lambda business_id: transport.get(
                config.profile_url,
                headers=headers,
                params=wire.profile_fields(business_id=business_id),
            )
        )
        daily = TikTokDailyMetricsReader(
            lambda business_id, since, until: transport.get(
                config.profile_url,
                headers=headers,
                params=wire.daily_metric_fields(
                    business_id=business_id,
                    since=since,
                    until=until,
                ),
            )
        )
        content = TikTokContentReader(
            lambda business_id, cursor: transport.get(
                config.video_list_url,
                headers=headers,
                params=wire.video_fields(business_id=business_id, cursor=cursor),
            )
        )
        observed_on = date.today() - timedelta(days=1)
        audience = TikTokAudienceReader(
            lambda business_id, day: transport.get(
                config.profile_url,
                headers=headers,
                params=wire.audience_fields(
                    business_id=business_id,
                    observed_on=day,
                ),
            ),
            observed_on=observed_on,
        )
        comments = (
            TikTokCommentsReader(
                lambda business_id, video_id, cursor: transport.get(
                    config.comment_list_url,
                    headers=headers,
                    params=wire.comment_fields(
                        business_id=business_id,
                        video_id=video_id,
                        cursor=cursor,
                    ),
                )
            )
            if comment_enabled
            else None
        )
        return profile, daily, content, audience, comments

    def _access_token(self, platform: PlatformId, reference: str) -> str:
        token = self.credentials.get(
            CredentialRef(
                platform=platform,
                connection_id=reference,
                token_kind=TokenKind.ACCESS,
            )
        )
        if token is None:
            raise PermissionError("provider_access_token_unavailable")
        return token.value

    def _tiktok_access_context(
        self, reference: str, business_id: str
    ) -> TikTokAccessContext:
        access_reference = CredentialRef(
            platform=PlatformId.TIKTOK,
            connection_id=reference,
            token_kind=TokenKind.ACCESS,
        )
        current = self.credentials.get(access_reference)
        grant = None
        refresh: SecretToken | None = None
        if current is not None and (
            current.expires_at is None
            or current.expires_at > datetime.now(UTC) + timedelta(minutes=5)
        ):
            access_token = current.value
        else:
            refresh_reference = CredentialRef(
                platform=PlatformId.TIKTOK,
                connection_id=reference,
                token_kind=TokenKind.REFRESH,
            )
            refresh = self.credentials.get(refresh_reference)
            if refresh is None:
                raise PermissionError("provider_refresh_token_unavailable")
            access_token = ""
        config = self.settings.tiktok
        transport = TikTokHttpTransport(
            post_urls=(config.refresh_url, config.token_info_url),
            get_urls=(),
            timeout_seconds=self.settings.tiktok_activation.provider_timeout_seconds,
        )
        wire = TikTokAccountsWireMapper(config)
        if not access_token:
            if refresh is None:
                raise PermissionError("provider_refresh_token_unavailable")
            grant = parse_token(
                transport.post(
                    config.refresh_url,
                    data=wire.refresh_fields(refresh_token=refresh.value),
                )
            )
            access_token = grant.access_token
        allowed = set(config.required_scopes) | set(config.optional_scopes)
        info = parse_token_info(
            transport.post(
                config.token_info_url,
                data=wire.token_info_fields(access_token=access_token),
            )
        )
        if (
            info.business_id != business_id
            or not set(config.required_scopes).issubset(info.scopes)
            or not set(info.scopes).issubset(allowed)
            or (grant is not None and set(info.scopes) != set(grant.scopes))
        ):
            raise PermissionError("provider_refresh_identity_rejected")
        if grant is not None:
            now = datetime.now(UTC)
            self.credentials.put_many(
                (
                    (
                        access_reference,
                        SecretToken(
                            value=grant.access_token,
                            expires_at=now + timedelta(seconds=grant.expires_in),
                        ),
                    ),
                    (
                        refresh_reference,
                        SecretToken(
                            value=grant.refresh_token,
                            expires_at=now + timedelta(seconds=grant.refresh_expires_in),
                        ),
                    ),
                )
            )
        return TikTokAccessContext(
            access_token=access_token,
            scopes=frozenset(info.scopes),
        )

    def _persist_media(self, target: CollectionTarget, item: ProviderRecord) -> int:
        if self.media_files is None or self.media_fetcher is None:
            return 0
        return ContentMediaWriter(
            target=target,
            files=self.media_files,
            media_store=self.media_store,
            fetch=self.media_fetcher.fetch,
        ).persist(item)


class _MediaFetcher:
    def fetch(self, url: str) -> FetchedMedia:
        _validate_media_url(url)
        with httpx.stream(
            "GET",
            url,
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
            headers={"User-Agent": "social-media-v2-media/1"},
        ) as response:
            response.raise_for_status()
            _validate_media_url(str(response.url))
            content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            if content_type not in {"image/jpeg", "image/png", "image/webp", "video/mp4"}:
                raise ValueError("media_type_rejected")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_MEDIA_BYTES:
                    raise ValueError("media_too_large")
                chunks.append(chunk)
            return FetchedMedia(
                data=b"".join(chunks),
                mime_type=content_type,
                status_code=response.status_code,
            )

    def close(self) -> None:
        return None


def _validate_media_url(value: str) -> None:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname
        or hostname in {"localhost", "metadata.google.internal"}
    ):
        raise ValueError("media_url_rejected")
    if re.fullmatch(r"(?:127|10|0)\..*", hostname) or hostname in {"::1", "169.254.169.254"}:
        raise ValueError("media_url_rejected")


def _error_code(exc: Exception) -> str:
    """Record the class and the provider's sanitized reason.

    The class name alone said only `metatransporterror`, which is true of a
    refused metric, an expired token and a rate limit alike. The reason is an
    enum-like string from our own provider layer and carries no credential or
    response body, so keeping it turns an opaque failure into an actionable one.
    """
    name = re.sub(r"[^a-z0-9_]+", "_", type(exc).__name__.lower()).strip("_")
    reason = re.sub(r"[^a-z0-9_:.-]+", "_", str(exc).strip().lower()).strip("_")
    code = f"{name}:{reason}" if reason and reason != name else name
    return code[:120] or "collection_failed"


def _partial_error_code(errors: set[str]) -> str | None:
    if not errors:
        return None
    return ",".join(sorted(errors))[:256]


def _lock(engine: Engine, name: str):
    connection = engine.connect()
    acquired = bool(
        connection.execute(
            text("SELECT pg_try_advisory_lock(hashtext(:name))"), {"name": name}
        ).scalar_one()
    )
    if not acquired:
        connection.close()
        return None
    return connection


def _platforms(value: str) -> tuple[PlatformId, ...]:
    if value == "all":
        return tuple(PlatformId)
    return (PlatformId(value),)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Social Media V2 standalone collector")
    subparsers = parser.add_subparsers(dest="command", required=True)
    collect_parser = subparsers.add_parser("collect")
    collect_parser.add_argument(
        "--platform", choices=("all", *PlatformId.exact_set()), default="all"
    )
    collect_parser.add_argument("--brand-id", type=int)
    collect_parser.add_argument("--asset-id", type=int)
    collect_parser.add_argument("--scheduled", action="store_true")
    canary_parser = subparsers.add_parser("verify-tiktok")
    canary_parser.add_argument("--connection-id", type=int, required=True)
    args = parser.parse_args(argv)

    settings = load_settings()
    if args.command == "collect" and args.scheduled and not settings.worker_schedule_enabled:
        raise ConfigurationError("Scheduled collection is disabled")
    if not settings.db.url:
        raise ConfigurationError("Worker requires SOCIAL_DB_URL")
    engine = create_engine(settings.db.url, pool_pre_ping=True, pool_size=2, max_overflow=0)
    lock_name = (
        f"social_media_v2:tiktok_canary:{args.connection_id}"
        if args.command == "verify-tiktok"
        else "social_media_v2:scheduled_collection"
    )
    lock_connection = _lock(engine, lock_name)
    if lock_connection is None:
        engine.dispose()
        return 0
    collector: StandaloneCollector | None = None
    try:
        collector = StandaloneCollector(settings, engine)
        results: tuple[WorkerAccountResult, ...]
        if args.command == "verify-tiktok":
            results = (collector.verify_pending_tiktok(args.connection_id),)
        else:
            results = collector.collect_connected(
                platforms=_platforms(args.platform),
                brand_id=args.brand_id,
                asset_id=args.asset_id,
            )
        print(json.dumps([asdict(item) for item in results], separators=(",", ":")))
        return 1 if any(item.status != "success" for item in results) else 0
    finally:
        if collector is not None:
            collector.close()
        lock_connection.execute(
            text("SELECT pg_advisory_unlock(hashtext(:name))"), {"name": lock_name}
        )
        lock_connection.close()
        engine.dispose()


__all__ = ["StandaloneCollector", "WorkerAccountResult", "main"]

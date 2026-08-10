"""Copy the full SocialMedia reporting snapshot into an empty V2 shadow database.

The legacy connection is repeatable-read and transaction-read-only. Provider
credentials and ephemeral OAuth/job state are intentionally handled by separate,
explicit migration gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from collections import defaultdict
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import URL, make_url

CANONICAL_PLATFORMS = ("facebook", "instagram", "tiktok")
CONTENT_METRICS = (
    "views",
    "reach",
    "interactions",
    "replies",
    "saves",
    "sticker_taps",
    "profile_visits",
    "follows",
    "taps_forward",
    "taps_back",
    "swipe_forward",
    "exits",
    "navigation",
    "completion_rate",
    "story_views",
    "story_reach",
    "story_interactions",
    "story_replies",
    "story_shares",
    "story_saves",
    "story_sticker_taps",
    "story_profile_visits",
    "story_follows",
    "story_taps_forward",
    "story_taps_back",
    "story_swipe_forward",
    "story_exits",
    "story_navigation",
    "story_completion_rate",
    "full_video_watched_rate",
    "total_time_watched",
    "average_time_watched",
)
SENSITIVE_URL_PARAMETERS = {
    "access_token",
    "api_key",
    "client_secret",
    "code",
    "oauth_token",
    "refresh_token",
}
EXPECTED_MIGRATIONS = {
    "0001_v2_initial.sql",
    "0002_content_story_parity.sql",
    "0003_story_action_totals.sql",
    "0004_ai_summary.sql",
}
TARGET_DATA_TABLES = (
    "asset_sync_state",
    "assets",
    "brand_ai_insights",
    "brand_social_account_discoveries",
    "brands",
    "content_comments",
    "content_items",
    "linked_social_accounts",
    "media_assets",
    "meta_accounts",
    "metrics_daily",
    "platform_connections",
    "social_backfill_jobs",
    "social_projection_state",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--target-env", type=Path, required=True)
    parser.add_argument("--source-media-root", type=Path, required=True)
    parser.add_argument("--target-media-root", type=Path, required=True)
    parser.add_argument("--expected-brand-count", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--batch-sleep-ms", type=int, default=5)
    parser.add_argument("--target-runtime-user", default="social-media-v2")
    parser.add_argument("--target-runtime-group", default="social-media-v2")
    return parser.parse_args()


def _env_value(path: Path, key: str) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"missing_setting:{key}")


def _validate_urls(source: URL, target: URL) -> None:
    if source.get_backend_name() != "postgresql" or target.get_backend_name() != "postgresql":
        raise RuntimeError("postgresql_required")
    if source.database != "socialmedia_adv":
        raise RuntimeError("source_database_must_be_socialmedia_adv")
    if not (target.database or "").startswith("social_media_v2_shadow_"):
        raise RuntimeError("target_database_must_be_v2_shadow")
    source_endpoint = (source.host, source.port or 5432, source.database)
    target_endpoint = (target.host, target.port or 5432, target.database)
    if source_endpoint == target_endpoint:
        raise RuntimeError("source_and_target_database_must_differ")


def _safe_media_url(raw_url: object) -> str:
    value = str(raw_url or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    parameters = {name.lower() for name, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    return "" if parameters & SENSITIVE_URL_PARAMETERS else value


def _content_type(raw_value: object) -> str:
    normalized = str(raw_value or "").strip().lower()
    return {
        "carousel_album": "carousel",
        "photo": "image",
        "reels": "reel",
    }.get(normalized, normalized or "post")


def _pick(values: Mapping[str, float], *names: str) -> float | None:
    return next((values[name] for name in names if name in values), None)


def _validate_source(source: Connection, expected_brand_count: int) -> None:
    if source.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
        raise RuntimeError("legacy_connection_is_not_read_only")
    if source.execute(text("SHOW transaction_isolation")).scalar_one() != "repeatable read":
        raise RuntimeError("legacy_connection_is_not_repeatable_read")
    brand_count = source.execute(text("SELECT count(*) FROM brands")).scalar_one()
    if brand_count != expected_brand_count:
        raise RuntimeError(
            f"legacy_brand_count_changed:expected={expected_brand_count}:actual={brand_count}"
        )


def _validate_target(target: Connection) -> None:
    migrations = set(target.execute(text("SELECT version FROM social_schema_migrations")).scalars())
    if migrations != EXPECTED_MIGRATIONS:
        raise RuntimeError("target_migration_set_mismatch")
    nonempty = [
        table
        for table in TARGET_DATA_TABLES
        if target.execute(text(f'SELECT count(*) FROM "{table}"')).scalar_one() != 0
    ]
    if nonempty:
        raise RuntimeError(f"target_tables_must_be_empty:{','.join(nonempty)}")


def _stream_copy(
    source: Connection,
    target: Connection,
    *,
    select_sql: str,
    insert_sql: str,
    batch_size: int,
    sleep_seconds: float,
    parameters: Mapping[str, object] | None = None,
    transform: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
) -> int:
    result = source.execution_options(stream_results=True).execute(
        text(select_sql), dict(parameters or {})
    )
    count = 0
    while rows := result.mappings().fetchmany(batch_size):
        payload = [dict(transform(row) if transform else row) for row in rows]
        target.execute(text(insert_sql), payload)
        count += len(payload)
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return count


def _content_support(
    source: Connection,
) -> tuple[dict[tuple[int, str], dict[str, float]], dict[tuple[int, str], str]]:
    latest: dict[tuple[int, str], dict[str, float]] = defaultdict(dict)
    rows = source.execute(
        text(
            """SELECT DISTINCT ON (asset_id, breakdown_value, metric_id)
                      asset_id, breakdown_value AS content_id, metric_id, value_numeric
               FROM metrics_daily
               WHERE breakdown_key='content_id'
                 AND breakdown_value IS NOT NULL
                 AND metric_id = ANY(:metric_ids)
               ORDER BY asset_id, breakdown_value, metric_id, date DESC, id DESC"""
        ),
        {"metric_ids": list(CONTENT_METRICS)},
    ).mappings()
    for row in rows:
        latest[(int(row["asset_id"]), str(row["content_id"]))][str(row["metric_id"])] = float(
            row["value_numeric"]
        )
    media_urls: dict[tuple[int, str], str] = {}
    rows = source.execute(
        text(
            """SELECT DISTINCT ON (asset_id, content_id)
                      asset_id, content_id, source_url
               FROM media_assets
               ORDER BY asset_id, content_id,
                        CASE WHEN media_kind='cover' THEN 0 ELSE 1 END,
                        updated_at DESC, id DESC"""
        )
    ).mappings()
    for row in rows:
        if safe_url := _safe_media_url(row["source_url"]):
            media_urls[(int(row["asset_id"]), str(row["content_id"]))] = safe_url
    return latest, media_urls


def _content_transform(
    row: Mapping[str, Any],
    latest: Mapping[tuple[int, str], Mapping[str, float]],
    media_urls: Mapping[tuple[int, str], str],
) -> Mapping[str, Any]:
    asset_id = int(row["asset_id"])
    content_id = str(row["content_id"])
    values = latest.get((asset_id, content_id), {})
    normalized_type = _content_type(row["content_type"])
    is_story = normalized_type == "story"
    media_url = media_urls.get((asset_id, content_id)) or _safe_media_url(row["media_url"])
    shares = _pick(values, "story_shares", "shares") if is_story else None
    return {
        **row,
        "content_type": normalized_type,
        "permalink": str(row["permalink"] or ""),
        "message": str(row["message"] or ""),
        "media_url": media_url,
        "likes_count": int(row["likes_count"] or 0),
        "comments_count": int(row["comments_count"] or 0),
        "shares_count": int(shares if shares is not None else row["shares_count"] or 0),
        "views_count": _pick(values, "story_views", "views")
        if is_story
        else _pick(values, "views"),
        "reach_count": _pick(values, "story_reach", "reach")
        if is_story
        else _pick(values, "reach"),
        "cover_url": media_url or None,
        "thumbnail_url": media_url or None,
        "cover_candidates": json.dumps([media_url] if media_url else []),
        "thumbnail_candidates": json.dumps([media_url] if media_url else []),
        "media_url_candidates": json.dumps([media_url] if media_url else []),
        "full_video_watched_rate": _pick(values, "full_video_watched_rate"),
        "total_time_watched": _pick(values, "total_time_watched"),
        "average_time_watched": _pick(values, "average_time_watched"),
        "interactions_count": _pick(values, "story_interactions", "interactions")
        if is_story
        else _pick(values, "interactions"),
        "replies_count": _pick(values, "story_replies", "replies")
        if is_story
        else _pick(values, "replies"),
        "saves_count": _pick(values, "story_saves", "saves")
        if is_story
        else _pick(values, "saves"),
        "sticker_taps": _pick(values, "story_sticker_taps", "sticker_taps")
        if is_story
        else _pick(values, "sticker_taps"),
        "profile_visits": _pick(values, "story_profile_visits", "profile_visits")
        if is_story
        else _pick(values, "profile_visits"),
        "follows_count": _pick(values, "story_follows", "follows")
        if is_story
        else _pick(values, "follows"),
        "taps_forward": _pick(values, "story_taps_forward", "taps_forward")
        if is_story
        else _pick(values, "taps_forward"),
        "taps_back": _pick(values, "story_taps_back", "taps_back")
        if is_story
        else _pick(values, "taps_back"),
        "swipe_forward": _pick(values, "story_swipe_forward", "swipe_forward")
        if is_story
        else _pick(values, "swipe_forward"),
        "exits": _pick(values, "story_exits", "exits") if is_story else _pick(values, "exits"),
        "navigation_count": _pick(values, "story_navigation", "navigation")
        if is_story
        else _pick(values, "navigation"),
        "completion_rate": _pick(values, "story_completion_rate", "completion_rate")
        if is_story
        else _pick(values, "completion_rate"),
    }


def _copy_media(source: Connection, source_root: Path, target_root: Path) -> int:
    resolved_source = source_root.resolve(strict=True)
    resolved_target = target_root.resolve()
    if resolved_target.exists():
        raise RuntimeError("target_media_root_must_not_exist")
    resolved_target.mkdir(parents=True, mode=0o750)
    rows = source.execute(
        text(
            """SELECT storage_path, size_bytes, checksum
               FROM media_assets ORDER BY storage_path, id"""
        )
    ).mappings()
    count = 0
    for row in rows:
        relative = Path(str(row["storage_path"]))
        if relative.is_absolute():
            raise RuntimeError("legacy_media_path_must_be_relative")
        source_path = (resolved_source / relative).resolve(strict=True)
        target_path = (resolved_target / relative).resolve()
        if not source_path.is_relative_to(resolved_source):
            raise RuntimeError("legacy_media_path_outside_source_root")
        if not target_path.is_relative_to(resolved_target):
            raise RuntimeError("target_media_path_outside_target_root")
        expected_size = int(row["size_bytes"])
        if source_path.stat().st_size != expected_size:
            raise RuntimeError("legacy_media_size_mismatch")
        digest = hashlib.file_digest(source_path.open("rb"), "sha256").hexdigest()
        if digest != str(row["checksum"]):
            raise RuntimeError("legacy_media_checksum_mismatch")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        if target_path.stat().st_size != expected_size:
            raise RuntimeError("target_media_size_mismatch")
        count += 1
        if count % 500 == 0:
            print(f"media_verified={count}", flush=True)
    return count


def _secure_media_tree(target_root: Path, *, user: str, group: str) -> int:
    """Make the copied tree private and readable by the isolated V2 runtime."""
    resolved_root = target_root.resolve(strict=True)
    paths = (resolved_root, *sorted(resolved_root.rglob("*")))
    secured = 0
    for path in paths:
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise RuntimeError("target_media_contains_unsupported_entry")
        shutil.chown(path, user=user, group=group)
        path.chmod(0o750 if path.is_dir() else 0o640)
        secured += 1
    return secured


def _copy_database(
    source: Connection,
    target: Connection,
    *,
    batch_size: int,
    sleep_seconds: float,
) -> dict[str, int]:
    counts: dict[str, int] = {}
    brands = (
        source.execute(
            text(
                """SELECT id, name, status, created_at, parent_brand_id
               FROM brands ORDER BY id"""
            )
        )
        .mappings()
        .all()
    )
    target.execute(
        text(
            """INSERT INTO brands
               (id, tenant_id, name, parent_brand_id, active, created_at, updated_at)
               VALUES (:id, 1, :name, NULL, :active, :created_at, :created_at)"""
        ),
        [
            {
                "id": row["id"],
                "name": row["name"],
                "active": str(row["status"]).lower() == "active",
                "created_at": row["created_at"],
            }
            for row in brands
        ],
    )
    for row in brands:
        if row["parent_brand_id"] is not None:
            target.execute(
                text("UPDATE brands SET parent_brand_id=:parent WHERE id=:id"),
                {"id": row["id"], "parent": row["parent_brand_id"]},
            )
    counts["brands"] = len(brands)

    counts["meta_accounts"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, platform, asset_type, external_id, display_name, status,
                             last_discovered_at, created_at, updated_at
                      FROM meta_accounts ORDER BY id""",
        insert_sql="""INSERT INTO meta_accounts
                       (id, platform, asset_type, external_id, display_name, status,
                        last_discovered_at, created_at, updated_at)
                       VALUES (:id, :platform, :asset_type, :external_id, :display_name,
                               :status, :last_discovered_at, :created_at, :updated_at)""",
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["platform_connections"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, brand_id, platform, status, expires_at, projected_at,
                             created_at
                      FROM platform_connections ORDER BY id""",
        insert_sql="""INSERT INTO platform_connections
                       (id, tenant_id, brand_id, platform, status, expires_at,
                        projected_at, projection_source, created_at, updated_at)
                       VALUES (:id, 1, :brand_id, :platform, :status, :expires_at,
                               :projected_at, 'legacy_read_only_snapshot',
                               :created_at, :created_at)""",
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["assets"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, brand_id, platform, asset_type, external_id,
                             display_name, meta_account_id, status, created_at
                      FROM assets
                      WHERE platform = ANY(:platforms)
                      ORDER BY id""",
        insert_sql="""INSERT INTO assets
                       (id, tenant_id, brand_id, platform, asset_type, external_id,
                        display_name, meta_account_id, status, created_at, updated_at)
                       VALUES (:id, 1, :brand_id, :platform, :asset_type, :external_id,
                               COALESCE(:display_name, ''), :meta_account_id, :status,
                               :created_at, :created_at)""",
        parameters={"platforms": list(CANONICAL_PLATFORMS)},
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["linked_social_accounts"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, brand_id, platform, external_id, display_name,
                             connection_id, meta_account_id, asset_id, status,
                             health_status, backfill_status, nightly_enabled,
                             last_synced_at, created_at, updated_at
                      FROM linked_social_accounts
                      WHERE platform = ANY(:platforms)
                      ORDER BY id""",
        insert_sql="""INSERT INTO linked_social_accounts
                       (id, brand_id, platform, external_id, display_name,
                        connection_id, meta_account_id, asset_id, status,
                        health_status, backfill_status, nightly_enabled,
                        last_synced_at, created_at, updated_at)
                       VALUES (:id, :brand_id, :platform, :external_id,
                               COALESCE(:display_name, ''), :connection_id,
                               :meta_account_id, :asset_id, :status,
                               :health_status, :backfill_status, :nightly_enabled,
                               :last_synced_at, :created_at, :updated_at)""",
        parameters={"platforms": list(CANONICAL_PLATFORMS)},
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["asset_sync_state"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT ss.asset_id, ss.last_synced_at, ss.updated_at
                      FROM asset_sync_state ss
                      JOIN assets a ON a.id=ss.asset_id
                      WHERE a.platform = ANY(:platforms)
                      ORDER BY ss.asset_id""",
        insert_sql="""INSERT INTO asset_sync_state
                       (asset_id, last_synced_at, last_error, updated_at)
                       VALUES (:asset_id, :last_synced_at, NULL, :updated_at)""",
        parameters={"platforms": list(CANONICAL_PLATFORMS)},
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["metrics_daily"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, asset_id, brand_id, date, metric_id,
                             value_numeric, breakdown_key, breakdown_value
                      FROM metrics_daily ORDER BY id""",
        insert_sql="""INSERT INTO metrics_daily
                       (id, asset_id, brand_id, date, metric_id, value_numeric,
                        breakdown_key, breakdown_value)
                       VALUES (:id, :asset_id, :brand_id, :date, :metric_id,
                               :value_numeric, :breakdown_key, :breakdown_value)""",
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )

    latest, media_urls = _content_support(source)
    counts["content_items"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, asset_id, brand_id, content_id, content_type,
                             permalink, message, media_url, created_time,
                             likes_count, comments_count, shares_count,
                             created_at
                      FROM content_items ORDER BY id""",
        insert_sql="""INSERT INTO content_items
                       (id, asset_id, brand_id, content_id, content_type, permalink,
                        message, media_url, created_time, likes_count, comments_count,
                        shares_count, views_count, reach_count, cover_url, thumbnail_url,
                        cover_candidates, thumbnail_candidates, media_url_candidates,
                        full_video_watched_rate, total_time_watched,
                        average_time_watched, interactions_count, replies_count,
                        saves_count, sticker_taps, profile_visits, follows_count,
                        taps_forward, taps_back, swipe_forward, exits,
                        navigation_count, completion_rate, created_at, updated_at)
                       VALUES (:id, :asset_id, :brand_id, :content_id, :content_type,
                               :permalink, :message, :media_url, :created_time,
                               :likes_count, :comments_count, :shares_count,
                               :views_count, :reach_count, :cover_url, :thumbnail_url,
                               CAST(:cover_candidates AS jsonb),
                               CAST(:thumbnail_candidates AS jsonb),
                               CAST(:media_url_candidates AS jsonb),
                               :full_video_watched_rate, :total_time_watched,
                               :average_time_watched, :interactions_count,
                               :replies_count, :saves_count, :sticker_taps,
                               :profile_visits, :follows_count, :taps_forward,
                               :taps_back, :swipe_forward, :exits,
                               :navigation_count, :completion_rate,
                               :created_at, :created_at)""",
        transform=lambda row: _content_transform(row, latest, media_urls),
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["content_comments"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, asset_id, content_id, platform, comment_id,
                             user_id, user_name, text, like_count, reply_count,
                             answered, attachment_type, attachment_media_type,
                             attachment_url, commented_at, created_at, updated_at
                      FROM content_comments ORDER BY id""",
        insert_sql="""INSERT INTO content_comments
                       (id, asset_id, content_id, platform, comment_id, user_id,
                        user_name, text, like_count, reply_count, answered,
                        attachment_type, attachment_media_type, attachment_url,
                        commented_at, created_at, updated_at)
                       VALUES (:id, :asset_id, :content_id, :platform, :comment_id,
                               :user_id, :user_name, :text, :like_count,
                               :reply_count, :answered, :attachment_type,
                               :attachment_media_type, :attachment_url,
                               :commented_at, :created_at, :updated_at)""",
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["media_assets"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, brand_id, asset_id, content_id, platform,
                             media_kind, storage_path, source_url, source_status,
                             mime_type, size_bytes, checksum, last_verified_at,
                             created_at, updated_at
                      FROM media_assets ORDER BY id""",
        insert_sql="""INSERT INTO media_assets
                       (id, brand_id, asset_id, content_id, platform, media_kind,
                        storage_path, source_url, source_status, mime_type,
                        size_bytes, checksum, last_verified_at, created_at, updated_at)
                       VALUES (:id, :brand_id, :asset_id, :content_id, :platform,
                               :media_kind, :storage_path, :source_url,
                               :source_status, :mime_type, :size_bytes, :checksum,
                               :last_verified_at, :created_at, :updated_at)""",
        transform=lambda row: {**row, "source_url": _safe_media_url(row["source_url"])},
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )
    counts["brand_ai_insights"] = _stream_copy(
        source,
        target,
        select_sql="""SELECT id, brand_id, status, date_from, date_to,
                             strategic_summary, connector_analysis, anomalies,
                             action_recommendations, platform_evaluations,
                             llm_model, error_message, created_by_user_sub,
                             created_at, completed_at
                      FROM brand_ai_insights ORDER BY id""",
        insert_sql="""INSERT INTO brand_ai_insights
                       (id, brand_id, status, date_from, date_to,
                        strategic_summary, connector_analysis, anomalies,
                        action_recommendations, platform_evaluations,
                        llm_model, error_message, created_by_user_sub,
                        created_at, completed_at)
                       VALUES (:id, :brand_id, :status, :date_from, :date_to,
                               :strategic_summary, :connector_analysis, :anomalies,
                               :action_recommendations, :platform_evaluations,
                               :llm_model, :error_message, :created_by_user_sub,
                               :created_at, :completed_at)""",
        batch_size=batch_size,
        sleep_seconds=sleep_seconds,
    )

    projection_rows = [
        {
            "projection_key": f"legacy-brand:{row['id']}",
            "brand_id": row["id"],
            "payload": json.dumps(
                {"format_version": 1, "mode": "read_only_copy", "source": "SocialMedia"},
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
        for row in brands
    ]
    target.execute(
        text(
            """INSERT INTO social_projection_state
               (projection_key, brand_id, status, projection_source,
                projected_at, payload_json, created_at, updated_at)
               VALUES (:projection_key, :brand_id, 'active',
                       'legacy_read_only_snapshot', now(), CAST(:payload AS jsonb),
                       now(), now())"""
        ),
        projection_rows,
    )
    counts["social_projection_state"] = len(projection_rows)

    job_rows = (
        source.execute(
            text(
                """SELECT brand_id, asset_id, platform, last_synced_at
               FROM linked_social_accounts
               WHERE asset_id IS NOT NULL AND last_synced_at IS NOT NULL
                 AND platform = ANY(:platforms)
               ORDER BY id"""
            ),
            {"platforms": list(CANONICAL_PLATFORMS)},
        )
        .mappings()
        .all()
    )
    if job_rows:
        target.execute(
            text(
                """INSERT INTO social_backfill_jobs
                   (brand_id, asset_id, platform, stage, status, scheduled_for,
                    started_at, finished_at, created_at, updated_at)
                   VALUES (:brand_id, :asset_id, :platform, 'legacy_snapshot',
                           'completed', :last_synced_at, :last_synced_at,
                           :last_synced_at, now(), now())"""
            ),
            job_rows,
        )
    counts["social_backfill_jobs"] = len(job_rows)

    for table in (
        "assets",
        "brand_ai_insights",
        "content_comments",
        "content_items",
        "linked_social_accounts",
        "media_assets",
        "meta_accounts",
        "metrics_daily",
        "platform_connections",
        "social_backfill_jobs",
    ):
        target.execute(
            text(
                f"""SELECT setval(pg_get_serial_sequence('{table}', 'id'),
                                   GREATEST((SELECT COALESCE(max(id), 1) FROM {table}), 1),
                                   true)"""
            )
        )
    return counts


def main() -> None:
    args = _arguments()
    if args.expected_brand_count < 1:
        raise RuntimeError("expected_brand_count_must_be_positive")
    if not 100 <= args.batch_size <= 10_000:
        raise RuntimeError("batch_size_out_of_range")
    if not 0 <= args.batch_sleep_ms <= 1000:
        raise RuntimeError("batch_sleep_out_of_range")
    if not args.target_runtime_user.strip() or not args.target_runtime_group.strip():
        raise RuntimeError("target_runtime_identity_required")
    source_url = make_url(_env_value(args.source_env, "SOCIAL_MEDIA_DATABASE_URL"))
    target_url = make_url(_env_value(args.target_env, "SOCIAL_DB_URL"))
    _validate_urls(source_url, target_url)
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    source_connection = source_engine.connect().execution_options(isolation_level="REPEATABLE READ")
    source_transaction = source_connection.begin()
    try:
        source_connection.execute(text("SET TRANSACTION READ ONLY"))
        _validate_source(source_connection, args.expected_brand_count)
        media_count = _copy_media(
            source_connection,
            args.source_media_root,
            args.target_media_root,
        )
        secured_media_entries = _secure_media_tree(
            args.target_media_root,
            user=args.target_runtime_user,
            group=args.target_runtime_group,
        )
        with target_engine.begin() as target_connection:
            _validate_target(target_connection)
            counts = _copy_database(
                source_connection,
                target_connection,
                batch_size=args.batch_size,
                sleep_seconds=args.batch_sleep_ms / 1000,
            )
        source_transaction.rollback()
    except Exception:
        source_transaction.rollback()
        raise
    finally:
        source_connection.close()
        source_engine.dispose()
        target_engine.dispose()
    print(f"media_files={media_count}")
    print(f"secured_media_entries={secured_media_entries}")
    for name in sorted(counts):
        print(f"{name}={counts[name]}")


if __name__ == "__main__":
    main()

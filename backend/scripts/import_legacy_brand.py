"""Copy one allowlisted Brand snapshot from legacy SocialMedia into a V2-owned DB.

The legacy connection is forced to PostgreSQL read-only mode. Only canonical social
accounts and dashboard rows are selected; credentials, OAuth state, tokens, and
provider configuration are intentionally outside this import surface.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

CANONICAL_PLATFORMS = ("facebook", "instagram", "tiktok")
CANONICAL_METRICS = {
    "followers",
    "following",
    "new_followers",
    "follows",
    "unfollows",
    "followers_net",
    "reach",
    "reach_paid",
    "reach_organic",
    "views",
    "views_paid",
    "views_organic",
    "interactions",
    "page_views",
    "profile_views",
    "website_clicks",
    "total_actions",
    "reactions",
    "media_count",
}
AUDIENCE_METRIC_MAP = {
    "audience_country": ("followers", "audience_country"),
    "audience_city": ("followers", "audience_city"),
    "audience_gender_age": ("followers", "audience_gender_age"),
    "audience_heatmap": ("interactions", "best_time_to_engage"),
    "audience_countries": ("followers", "audience_country"),
    "audience_ages": ("followers", "audience_age"),
    "audience_genders": ("followers", "audience_gender"),
    "audience_activity": ("interactions", "audience_activity"),
}
TIKTOK_TOTAL_MAP = {
    "views": "video_views_total",
    "likes": "video_likes_total",
    "comments": "video_comments_total",
    "shares": "video_shares_total",
}
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


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--source-media-root", type=Path, required=True)
    parser.add_argument("--target-media-root", type=Path, required=True)
    parser.add_argument("--brand-slug", required=True)
    return parser.parse_args()


def _env_value(path: Path, key: str) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if not line.startswith(f"{key}="):
            continue
        return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"missing_source_setting:{key}")


def _validate_urls(source: URL, target: URL) -> None:
    if source.get_backend_name() != "postgresql" or target.get_backend_name() != "postgresql":
        raise RuntimeError("postgresql_required")
    if not (target.database or "").startswith("social_media_v2"):
        raise RuntimeError("target_database_must_be_v2_owned")
    source_endpoint = (source.host, source.port or 5432, source.database)
    target_endpoint = (target.host, target.port or 5432, target.database)
    if source_endpoint == target_endpoint:
        raise RuntimeError("source_and_target_database_must_differ")


def _safe_media_url(raw_url: str | None) -> str:
    value = (raw_url or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    parameters = {name.lower() for name, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    if parameters & SENSITIVE_URL_PARAMETERS:
        return ""
    return value


def _content_type(raw_value: str) -> str:
    normalized = raw_value.strip().lower()
    return {
        "carousel_album": "carousel",
        "photo": "image",
        "reels": "reel",
    }.get(normalized, normalized or "post")


def _pick(values: dict[str, float], *names: str) -> float | None:
    return next((values[name] for name in names if name in values), None)


def _source_snapshot(connection: Any, brand_slug: str) -> dict[str, Any]:
    if connection.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
        raise RuntimeError("legacy_connection_is_not_read_only")
    brand = (
        connection.execute(
            text(
                """SELECT id, name, slug, status
               FROM brands
               WHERE slug=:slug
               ORDER BY id
               LIMIT 2"""
            ),
            {"slug": brand_slug},
        )
        .mappings()
        .all()
    )
    if len(brand) != 1:
        raise RuntimeError("legacy_brand_must_resolve_exactly_once")
    brand_row = dict(brand[0])
    brand_id = int(brand_row["id"])

    accounts = [
        dict(row)
        for row in connection.execute(
            text(
                """SELECT id, platform, asset_type, external_id, display_name,
                          status, created_at
                   FROM assets
                   WHERE brand_id=:brand_id
                     AND platform IN ('facebook', 'instagram', 'tiktok')
                   ORDER BY platform, id"""
            ),
            {"brand_id": brand_id},
        ).mappings()
    ]
    if {row["platform"] for row in accounts} != set(CANONICAL_PLATFORMS):
        raise RuntimeError("legacy_brand_requires_all_canonical_platforms")
    account_ids = tuple(int(row["id"]) for row in accounts)
    platform_by_account = {int(row["id"]): str(row["platform"]) for row in accounts}

    linked_rows = {
        int(row["asset_id"]): dict(row)
        for row in connection.execute(
            text(
                """SELECT asset_id, status, health_status, backfill_status,
                          nightly_enabled, last_synced_at, created_at, updated_at
                   FROM linked_social_accounts
                   WHERE brand_id=:brand_id AND asset_id = ANY(:account_ids)
                   ORDER BY updated_at"""
            ),
            {"brand_id": brand_id, "account_ids": list(account_ids)},
        ).mappings()
    }

    requested_metric_ids = sorted(CANONICAL_METRICS | set(AUDIENCE_METRIC_MAP))
    source_metrics = connection.execute(
        text(
            """SELECT asset_id, date, metric_id, value_numeric,
                      breakdown_key, breakdown_value
               FROM metrics_daily
               WHERE asset_id = ANY(:account_ids)
                 AND metric_id = ANY(:metric_ids)
               ORDER BY asset_id, date, metric_id, breakdown_key, breakdown_value"""
        ),
        {"account_ids": list(account_ids), "metric_ids": requested_metric_ids},
    ).mappings()
    metrics: list[dict[str, Any]] = []
    for row in source_metrics:
        account_id = int(row["asset_id"])
        metric_id = str(row["metric_id"])
        if platform_by_account[account_id] == "tiktok" and metric_id in TIKTOK_TOTAL_MAP:
            # The account-level ``views`` row is a daily flow and powers the
            # selected-period trend. Content-id rows are separately projected
            # to cumulative ``video_views_total`` below.
            if metric_id != "views" or row["breakdown_key"] is not None:
                continue
        if metric_id in AUDIENCE_METRIC_MAP:
            target_metric, target_breakdown = AUDIENCE_METRIC_MAP[metric_id]
            if row["breakdown_value"] is None:
                continue
            metric_id = target_metric
            breakdown_key = target_breakdown
        else:
            breakdown_key = row["breakdown_key"]
        metrics.append(
            {
                "asset_id": account_id,
                "brand_id": brand_id,
                "date": row["date"],
                "metric_id": metric_id,
                "value_numeric": float(row["value_numeric"]),
                "breakdown_key": breakdown_key,
                "breakdown_value": row["breakdown_value"],
            }
        )

    tiktok_ids = [
        account_id for account_id in account_ids if platform_by_account[account_id] == "tiktok"
    ]
    tiktok_totals = connection.execute(
        text(
            """SELECT asset_id, date, metric_id, sum(value_numeric) AS value_numeric
               FROM metrics_daily
               WHERE asset_id = ANY(:account_ids)
                 AND metric_id = ANY(:metric_ids)
                 AND breakdown_key='content_id'
                 AND breakdown_value IS NOT NULL
               GROUP BY asset_id, date, metric_id
               ORDER BY asset_id, date, metric_id"""
        ),
        {"account_ids": tiktok_ids, "metric_ids": list(TIKTOK_TOTAL_MAP)},
    ).mappings()
    metrics.extend(
        {
            "asset_id": int(row["asset_id"]),
            "brand_id": brand_id,
            "date": row["date"],
            "metric_id": TIKTOK_TOTAL_MAP[str(row["metric_id"])],
            "value_numeric": float(row["value_numeric"]),
            "breakdown_key": None,
            "breakdown_value": None,
        }
        for row in tiktok_totals
    )

    latest_content_metrics: dict[tuple[int, str], dict[str, float]] = defaultdict(dict)
    for row in connection.execute(
        text(
            """SELECT DISTINCT ON (asset_id, breakdown_value, metric_id)
                      asset_id, breakdown_value AS content_id, metric_id, value_numeric
               FROM metrics_daily
               WHERE asset_id = ANY(:account_ids)
                 AND breakdown_key='content_id'
                 AND breakdown_value IS NOT NULL
                 AND metric_id = ANY(:metric_ids)
               ORDER BY asset_id, breakdown_value, metric_id, date DESC"""
        ),
        {"account_ids": list(account_ids), "metric_ids": list(CONTENT_METRICS)},
    ).mappings():
        latest_content_metrics[(int(row["asset_id"]), str(row["content_id"]))][
            str(row["metric_id"])
        ] = float(row["value_numeric"])

    media_urls: dict[tuple[int, str], str] = {}
    media: list[dict[str, Any]] = []
    for row in connection.execute(
        text(
            """SELECT DISTINCT ON (asset_id, content_id)
                      id, brand_id, asset_id, content_id, platform, media_kind,
                      storage_path, source_url, source_status, mime_type, size_bytes,
                      checksum, last_verified_at, created_at, updated_at
               FROM media_assets
               WHERE asset_id = ANY(:account_ids)
               ORDER BY asset_id, content_id,
                        CASE WHEN media_kind='cover' THEN 0 ELSE 1 END,
                        updated_at DESC"""
        ),
        {"account_ids": list(account_ids)},
    ).mappings():
        media.append(dict(row))
        if safe_url := _safe_media_url(row["source_url"]):
            media_urls[(int(row["asset_id"]), str(row["content_id"]))] = safe_url

    content: list[dict[str, Any]] = []
    for row in connection.execute(
        text(
            """SELECT asset_id, content_id, content_type, permalink, message,
                      media_url, created_time, likes_count, comments_count,
                      shares_count, created_at
               FROM content_items
               WHERE asset_id = ANY(:account_ids)
               ORDER BY asset_id, created_time, content_id"""
        ),
        {"account_ids": list(account_ids)},
    ).mappings():
        account_id = int(row["asset_id"])
        content_id = str(row["content_id"])
        values = latest_content_metrics[(account_id, content_id)]
        normalized_type = _content_type(str(row["content_type"]))
        is_story = normalized_type == "story"
        media_url = media_urls.get((account_id, content_id)) or _safe_media_url(row["media_url"])
        content.append(
            {
                "asset_id": account_id,
                "brand_id": brand_id,
                "content_id": content_id,
                "content_type": normalized_type,
                "permalink": str(row["permalink"] or ""),
                "message": str(row["message"] or ""),
                "media_url": media_url,
                "created_time": row["created_time"],
                "likes_count": int(row["likes_count"] or 0),
                "comments_count": int(row["comments_count"] or 0),
                "shares_count": int(
                    _pick(values, "story_shares", "shares")
                    if is_story and _pick(values, "story_shares", "shares") is not None
                    else row["shares_count"] or 0
                ),
                "views_count": _pick(values, "story_views", "views")
                if is_story
                else _pick(values, "views"),
                "reach_count": _pick(values, "story_reach", "reach")
                if is_story
                else _pick(values, "reach"),
                "cover_url": media_url or None,
                "thumbnail_url": media_url or None,
                "cover_candidates": [media_url] if media_url else [],
                "thumbnail_candidates": [media_url] if media_url else [],
                "media_url_candidates": [media_url] if media_url else [],
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
                "exits": _pick(values, "story_exits", "exits")
                if is_story
                else _pick(values, "exits"),
                "navigation_count": _pick(values, "story_navigation", "navigation")
                if is_story
                else _pick(values, "navigation"),
                "completion_rate": _pick(values, "story_completion_rate", "completion_rate")
                if is_story
                else _pick(values, "completion_rate"),
                "created_at": row["created_at"],
            }
        )

    comments = [
        dict(row)
        for row in connection.execute(
            text(
                """SELECT asset_id, content_id, platform, comment_id, user_name,
                          text, like_count, reply_count, answered, commented_at,
                          created_at, updated_at
                   FROM content_comments
                   WHERE asset_id = ANY(:account_ids)
                   ORDER BY asset_id, commented_at, comment_id"""
            ),
            {"account_ids": list(account_ids)},
        ).mappings()
    ]
    return {
        "brand": brand_row,
        "accounts": accounts,
        "linked": linked_rows,
        "metrics": metrics,
        "content": content,
        "comments": comments,
        "media": media,
    }


def _copy_media(snapshot: dict[str, Any], source_root: Path, target_root: Path) -> None:
    resolved_source_root = source_root.resolve(strict=True)
    resolved_target_root = target_root.resolve()
    resolved_target_root.mkdir(parents=True, exist_ok=True)
    for row in snapshot["media"]:
        relative = Path(str(row["storage_path"]))
        if relative.is_absolute():
            raise RuntimeError("legacy_media_path_must_be_relative")
        source = (resolved_source_root / relative).resolve(strict=True)
        target = (resolved_target_root / relative).resolve()
        if not source.is_relative_to(resolved_source_root):
            raise RuntimeError("legacy_media_path_outside_source_root")
        if not target.is_relative_to(resolved_target_root):
            raise RuntimeError("target_media_path_outside_target_root")
        if source.stat().st_size != int(row["size_bytes"]):
            raise RuntimeError("legacy_media_size_mismatch")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != str(row["checksum"]):
            raise RuntimeError("legacy_media_checksum_mismatch")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if target.stat().st_size != int(row["size_bytes"]):
            raise RuntimeError("target_media_size_mismatch")


def _replace_target(connection: Any, snapshot: dict[str, Any]) -> dict[str, int]:
    brand = snapshot["brand"]
    brand_id = int(brand["id"])
    account_ids = tuple(int(row["id"]) for row in snapshot["accounts"])

    for statement in (
        """DELETE FROM content_comments
           WHERE asset_id IN (SELECT id FROM assets WHERE brand_id=:brand_id)""",
        "DELETE FROM media_assets WHERE brand_id=:brand_id",
        "DELETE FROM content_items WHERE brand_id=:brand_id",
        "DELETE FROM metrics_daily WHERE brand_id=:brand_id",
        "DELETE FROM social_backfill_jobs WHERE brand_id=:brand_id",
        "DELETE FROM linked_social_accounts WHERE brand_id=:brand_id",
        "DELETE FROM brand_social_account_discoveries WHERE brand_id=:brand_id",
        """DELETE FROM asset_sync_state
           WHERE asset_id IN (SELECT id FROM assets WHERE brand_id=:brand_id)""",
        "DELETE FROM assets WHERE brand_id=:brand_id",
        "DELETE FROM platform_connections WHERE brand_id=:brand_id",
        "DELETE FROM brand_ai_insights WHERE brand_id=:brand_id",
        "DELETE FROM social_projection_state WHERE brand_id=:brand_id",
        "DELETE FROM brands WHERE id=:brand_id",
    ):
        connection.execute(text(statement), {"brand_id": brand_id})

    connection.execute(
        text(
            """INSERT INTO brands (id, tenant_id, name, active)
               VALUES (:id, 1, :name, :active)"""
        ),
        {
            "id": brand_id,
            "name": brand["name"],
            "active": str(brand["status"]).lower() == "active",
        },
    )
    connection.execute(
        text(
            """INSERT INTO social_projection_state
                      (projection_key, brand_id, status, projection_source,
                       projected_at, payload_json)
               VALUES (:projection_key, :brand_id, 'active', 'legacy_read_only_snapshot', now(),
                       CAST(:payload_json AS jsonb))"""
        ),
        {
            "projection_key": f"legacy-brand:{brand_id}",
            "brand_id": brand_id,
            "payload_json": '{"source":"SocialMedia","mode":"read_only_copy"}',
        },
    )

    account_insert = text(
        """INSERT INTO assets
                  (id, tenant_id, brand_id, platform, asset_type, external_id,
                   display_name, status, created_at, updated_at)
           VALUES (:id, 1, :brand_id, :platform, :asset_type, :external_id,
                   :display_name, :status, :created_at, now())"""
    )
    for account in snapshot["accounts"]:
        connection.execute(account_insert, {**account, "brand_id": brand_id})
        linked = snapshot["linked"].get(int(account["id"]), {})
        raw_status = str(linked.get("status") or account["status"])
        connection_state = (
            "connected" if raw_status in {"active", "connected", "ready"} else raw_status
        )
        connection.execute(
            text(
                """INSERT INTO platform_connections
                          (id, tenant_id, brand_id, platform, status, projected_at,
                           projection_source, created_at, updated_at)
                   VALUES (:id, 1, :brand_id, :platform, :status, :projected_at,
                           'legacy_read_only_snapshot', :created_at, :updated_at)"""
            ),
            {
                "id": int(account["id"]),
                "brand_id": brand_id,
                "platform": account["platform"],
                "status": connection_state,
                "projected_at": linked.get("updated_at") or account["created_at"],
                "created_at": linked.get("created_at") or account["created_at"],
                "updated_at": linked.get("updated_at") or account["created_at"],
            },
        )
        connection.execute(
            text(
                """INSERT INTO linked_social_accounts
                          (id, brand_id, platform, external_id, display_name,
                           connection_id, asset_id, status, health_status,
                           backfill_status, nightly_enabled, last_synced_at,
                           created_at, updated_at)
                   VALUES (:id, :brand_id, :platform, :external_id, :display_name,
                           :id, :id, :status, :health_status, :backfill_status,
                           :nightly_enabled, :last_synced_at, :created_at, :updated_at)"""
            ),
            {
                "id": int(account["id"]),
                "brand_id": brand_id,
                "platform": account["platform"],
                "external_id": account["external_id"],
                "display_name": account["display_name"] or "",
                "status": connection_state,
                "health_status": linked.get("health_status") or "unknown",
                "backfill_status": linked.get("backfill_status") or "complete",
                "nightly_enabled": bool(linked.get("nightly_enabled", False)),
                "last_synced_at": linked.get("last_synced_at"),
                "created_at": linked.get("created_at") or account["created_at"],
                "updated_at": linked.get("updated_at") or account["created_at"],
            },
        )
        connection.execute(
            text(
                """INSERT INTO asset_sync_state (asset_id, last_synced_at, updated_at)
                   VALUES (:asset_id, :last_synced_at, now())"""
            ),
            {"asset_id": int(account["id"]), "last_synced_at": linked.get("last_synced_at")},
        )

    if snapshot["metrics"]:
        connection.execute(
            text(
                """INSERT INTO metrics_daily
                          (asset_id, brand_id, date, metric_id, value_numeric,
                           breakdown_key, breakdown_value)
                   VALUES (:asset_id, :brand_id, :date, :metric_id, :value_numeric,
                           :breakdown_key, :breakdown_value)"""
            ),
            snapshot["metrics"],
        )
    if snapshot["content"]:
        connection.execute(
            text(
                """INSERT INTO content_items
                          (asset_id, brand_id, content_id, content_type, permalink,
                           message, media_url, created_time, likes_count, comments_count,
                           shares_count, views_count, reach_count, cover_url, thumbnail_url,
                           cover_candidates, thumbnail_candidates, media_url_candidates,
                           full_video_watched_rate, total_time_watched,
                           average_time_watched, interactions_count, replies_count,
                           saves_count, sticker_taps, profile_visits, follows_count,
                           taps_forward, taps_back,
                           swipe_forward, exits, navigation_count, completion_rate, created_at)
                   VALUES (:asset_id, :brand_id, :content_id, :content_type, :permalink,
                           :message, :media_url, :created_time, :likes_count, :comments_count,
                           :shares_count, :views_count, :reach_count, :cover_url, :thumbnail_url,
                           CAST(:cover_candidates AS jsonb), CAST(:thumbnail_candidates AS jsonb),
                           CAST(:media_url_candidates AS jsonb), :full_video_watched_rate,
                           :total_time_watched, :average_time_watched, :interactions_count,
                           :replies_count, :saves_count, :sticker_taps,
                           :profile_visits, :follows_count, :taps_forward,
                           :taps_back, :swipe_forward, :exits, :navigation_count,
                           :completion_rate, :created_at)"""
            ),
            [
                {
                    **row,
                    "cover_candidates": _json_array(row["cover_candidates"]),
                    "thumbnail_candidates": _json_array(row["thumbnail_candidates"]),
                    "media_url_candidates": _json_array(row["media_url_candidates"]),
                }
                for row in snapshot["content"]
            ],
        )
    if snapshot["comments"]:
        connection.execute(
            text(
                """INSERT INTO content_comments
                          (asset_id, content_id, platform, comment_id, user_name, text,
                           like_count, reply_count, answered, commented_at, created_at, updated_at)
                   VALUES (:asset_id, :content_id, :platform, :comment_id, :user_name, :text,
                           :like_count, :reply_count, :answered, :commented_at,
                           :created_at, :updated_at)"""
            ),
            snapshot["comments"],
        )
    if snapshot["media"]:
        connection.execute(
            text(
                """INSERT INTO media_assets
                          (brand_id, asset_id, content_id, platform, media_kind,
                           storage_path, source_url, source_status, mime_type,
                           size_bytes, checksum, last_verified_at, created_at, updated_at)
                   VALUES (:brand_id, :asset_id, :content_id, :platform, :media_kind,
                           :storage_path, :source_url, :source_status, :mime_type,
                           :size_bytes, :checksum, :last_verified_at, :created_at, :updated_at)"""
            ),
            [
                {
                    **row,
                    "source_url": _safe_media_url(row["source_url"]),
                }
                for row in snapshot["media"]
            ],
        )
    for account_id in account_ids:
        linked = snapshot["linked"].get(account_id, {})
        synced_at = linked.get("last_synced_at")
        if synced_at is None:
            continue
        platform = next(
            row["platform"] for row in snapshot["accounts"] if int(row["id"]) == account_id
        )
        connection.execute(
            text(
                """INSERT INTO social_backfill_jobs
                          (brand_id, asset_id, platform, stage, status, scheduled_for,
                           started_at, finished_at)
                   VALUES (:brand_id, :asset_id, :platform, 'legacy_snapshot', 'completed',
                           :synced_at, :synced_at, :synced_at)"""
            ),
            {
                "brand_id": brand_id,
                "asset_id": account_id,
                "platform": platform,
                "synced_at": synced_at,
            },
        )

    connection.execute(
        text(
            """SELECT setval(pg_get_serial_sequence('assets', 'id'),
                              GREATEST((SELECT max(id) FROM assets), 1), true)"""
        )
    )
    return {
        "accounts": len(snapshot["accounts"]),
        "metrics": len(snapshot["metrics"]),
        "content": len(snapshot["content"]),
        "comments": len(snapshot["comments"]),
        "media": len(snapshot["media"]),
    }


def _json_array(values: list[str]) -> str:
    import json

    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    arguments = _arguments()
    source_url = make_url(_env_value(arguments.source_env, "SOCIAL_MEDIA_DATABASE_URL"))
    target_raw = os.getenv("SOCIAL_DB_URL", "").strip()
    if not target_raw:
        raise RuntimeError("SOCIAL_DB_URL_required")
    target_url = make_url(target_raw)
    _validate_urls(source_url, target_url)

    source_engine = create_engine(
        source_url,
        connect_args={"options": "-c default_transaction_read_only=on"},
        pool_pre_ping=True,
    )
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        with source_engine.connect() as source_connection:
            snapshot = _source_snapshot(source_connection, arguments.brand_slug)
        _copy_media(
            snapshot,
            arguments.source_media_root,
            arguments.target_media_root,
        )
        with target_engine.begin() as target_connection:
            counts = _replace_target(target_connection, snapshot)
    finally:
        source_engine.dispose()
        target_engine.dispose()

    print(
        "Imported read-only legacy snapshot: "
        f"brand={snapshot['brand']['name']!r}, "
        f"accounts={counts['accounts']}, metrics={counts['metrics']}, "
        f"content={counts['content']}, comments={counts['comments']}, "
        f"media={counts['media']}"
    )


if __name__ == "__main__":
    main()

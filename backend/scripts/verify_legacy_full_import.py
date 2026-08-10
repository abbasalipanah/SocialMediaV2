"""Verify an all-brand legacy snapshot without writing either database.

Both connections are repeatable-read and transaction-read-only. The comparison
streams rows in primary-key order, checks per-brand/platform scope, and verifies
every target media file against the source DB checksum.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from import_legacy_all_brands import (
    CANONICAL_PLATFORMS,
    _content_support,
    _content_transform,
    _env_value,
    _safe_media_url,
)
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.engine import URL, make_url

Row = Mapping[str, Any]
Normalizer = Callable[[Row], tuple[Any, ...]]


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--target-env", type=Path, required=True)
    parser.add_argument("--source-media-root", type=Path, required=True)
    parser.add_argument("--target-media-root", type=Path, required=True)
    parser.add_argument("--expected-brand-count", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=5000)
    return parser.parse_args()


def _validate_urls(source: URL, target: URL) -> None:
    if source.get_backend_name() != "postgresql" or target.get_backend_name() != "postgresql":
        raise RuntimeError("postgresql_required")
    if source.database != "socialmedia_adv":
        raise RuntimeError("source_database_must_be_socialmedia_adv")
    if not (target.database or "").startswith("social_media_v2_shadow_"):
        raise RuntimeError("target_database_must_be_v2_shadow")
    if (source.host, source.port or 5432, source.database) == (
        target.host,
        target.port or 5432,
        target.database,
    ):
        raise RuntimeError("source_and_target_database_must_differ")


def _assert_read_only(connection: Connection, label: str) -> None:
    if connection.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
        raise RuntimeError(f"{label}_connection_is_not_read_only")
    if connection.execute(text("SHOW transaction_isolation")).scalar_one() != "repeatable read":
        raise RuntimeError(f"{label}_connection_is_not_repeatable_read")


def _rows(connection: Connection, sql: str, parameters: Mapping[str, object] | None = None) -> Any:
    return (
        connection.execution_options(stream_results=True)
        .execute(text(sql), dict(parameters or {}))
        .mappings()
    )


def _chunks(rows: Any, batch_size: int) -> Iterator[Sequence[Row]]:
    while chunk := rows.fetchmany(batch_size):
        yield chunk


def _compare_streams(
    label: str,
    source_rows: Any,
    target_rows: Any,
    *,
    batch_size: int,
    source_normalizer: Normalizer,
    target_normalizer: Normalizer | None = None,
) -> int:
    target_normalizer = target_normalizer or source_normalizer
    source_chunks = _chunks(source_rows, batch_size)
    target_chunks = _chunks(target_rows, batch_size)
    count = 0
    while True:
        source_chunk = next(source_chunks, ())
        target_chunk = next(target_chunks, ())
        if not source_chunk and not target_chunk:
            break
        if len(source_chunk) != len(target_chunk):
            raise RuntimeError(
                f"{label}_batch_size_mismatch:offset={count}:"
                f"source={len(source_chunk)}:target={len(target_chunk)}"
            )
        for source_row, target_row in zip(source_chunk, target_chunk, strict=True):
            source_value = source_normalizer(source_row)
            target_value = target_normalizer(target_row)
            if source_value != target_value:
                source_id = source_row.get("id", source_row.get("asset_id", count))
                target_id = target_row.get("id", target_row.get("asset_id", count))
                raise RuntimeError(
                    f"{label}_row_mismatch:offset={count}:"
                    f"source_id={source_id}:target_id={target_id}"
                )
            count += 1
        if count and count % 250_000 == 0:
            print(f"{label}_verified={count}", flush=True)
    print(f"{label}={count}", flush=True)
    return count


def _tuple(*names: str) -> Normalizer:
    return lambda row: tuple(row[name] for name in names)


def _group_counts(connection: Connection) -> dict[str, list[tuple[Any, ...]]]:
    parameters = {"platforms": list(CANONICAL_PLATFORMS)}
    queries = {
        "assets": """SELECT brand_id,platform,count(*)
                     FROM assets WHERE platform = ANY(:platforms)
                     GROUP BY brand_id,platform ORDER BY brand_id,platform""",
        "metrics": """SELECT m.brand_id,a.platform,count(*)
                      FROM metrics_daily m JOIN assets a ON a.id=m.asset_id
                      GROUP BY m.brand_id,a.platform ORDER BY m.brand_id,a.platform""",
        "content": """SELECT c.brand_id,a.platform,count(*)
                      FROM content_items c JOIN assets a ON a.id=c.asset_id
                      GROUP BY c.brand_id,a.platform ORDER BY c.brand_id,a.platform""",
        "media": """SELECT ma.brand_id,a.platform,count(*)
                    FROM media_assets ma JOIN assets a ON a.id=ma.asset_id
                    GROUP BY ma.brand_id,a.platform ORDER BY ma.brand_id,a.platform""",
        "comments": """SELECT a.brand_id,cc.platform,count(*)
                       FROM content_comments cc JOIN assets a ON a.id=cc.asset_id
                       GROUP BY a.brand_id,cc.platform ORDER BY a.brand_id,cc.platform""",
    }
    return {
        label: [tuple(row) for row in connection.execute(text(sql), parameters).all()]
        for label, sql in queries.items()
    }


def _verify_media_files(source: Connection, source_root: Path, target_root: Path) -> int:
    resolved_source = source_root.resolve(strict=True)
    resolved_target = target_root.resolve(strict=True)
    rows = source.execute(
        text("SELECT storage_path, size_bytes, checksum FROM media_assets ORDER BY id")
    ).mappings()
    expected_paths: set[Path] = set()
    count = 0
    for row in rows:
        relative = Path(str(row["storage_path"]))
        if relative.is_absolute():
            raise RuntimeError("legacy_media_path_must_be_relative")
        source_path = (resolved_source / relative).resolve(strict=True)
        target_path = (resolved_target / relative).resolve(strict=True)
        if not source_path.is_relative_to(resolved_source):
            raise RuntimeError("legacy_media_path_outside_source_root")
        if not target_path.is_relative_to(resolved_target):
            raise RuntimeError("target_media_path_outside_target_root")
        expected_size = int(row["size_bytes"])
        if (
            source_path.stat().st_size != expected_size
            or target_path.stat().st_size != expected_size
        ):
            raise RuntimeError(f"media_size_mismatch:id={count}")
        source_hash = hashlib.file_digest(source_path.open("rb"), "sha256").hexdigest()
        target_hash = hashlib.file_digest(target_path.open("rb"), "sha256").hexdigest()
        if source_hash != str(row["checksum"]) or target_hash != source_hash:
            raise RuntimeError(f"media_checksum_mismatch:id={count}")
        expected_paths.add(target_path)
        count += 1
        if count % 500 == 0:
            print(f"media_files_verified={count}", flush=True)
    actual_paths = {path.resolve() for path in resolved_target.rglob("*") if path.is_file()}
    if actual_paths != expected_paths:
        raise RuntimeError(
            f"target_media_file_set_mismatch:expected={len(expected_paths)}:actual={len(actual_paths)}"
        )
    print(f"media_files={count}", flush=True)
    return count


def _verify(source: Connection, target: Connection, args: argparse.Namespace) -> None:
    brand_count = source.execute(text("SELECT count(*) FROM brands")).scalar_one()
    if brand_count != args.expected_brand_count:
        raise RuntimeError(
            f"legacy_brand_count_changed:expected={args.expected_brand_count}:actual={brand_count}"
        )
    if _group_counts(source) != _group_counts(target):
        raise RuntimeError("brand_platform_scope_mismatch")
    print("brand_platform_scope=matched", flush=True)

    _compare_streams(
        "brands",
        _rows(source, "SELECT id,name,status,parent_brand_id,created_at FROM brands ORDER BY id"),
        _rows(target, "SELECT id,name,active,parent_brand_id,created_at FROM brands ORDER BY id"),
        batch_size=args.batch_size,
        source_normalizer=lambda row: (
            row["id"],
            row["name"],
            str(row["status"]).lower() == "active",
            row["parent_brand_id"],
            row["created_at"],
        ),
        target_normalizer=_tuple("id", "name", "active", "parent_brand_id", "created_at"),
    )
    exact_tables = (
        (
            "meta_accounts",
            "id,platform,asset_type,external_id,display_name,status,last_discovered_at,created_at,updated_at",
            "",
        ),
        (
            "assets",
            "id,brand_id,platform,asset_type,external_id,display_name,meta_account_id,status,created_at",
            "WHERE platform = ANY(:platforms)",
        ),
        (
            "linked_social_accounts",
            "id,brand_id,platform,external_id,display_name,connection_id,meta_account_id,asset_id,status,health_status,backfill_status,nightly_enabled,last_synced_at,created_at,updated_at",
            "WHERE platform = ANY(:platforms)",
        ),
        (
            "content_comments",
            "id,asset_id,content_id,platform,comment_id,user_id,user_name,text,like_count,reply_count,answered,attachment_type,attachment_media_type,attachment_url,commented_at,created_at,updated_at",
            "",
        ),
        (
            "brand_ai_insights",
            "id,brand_id,status,date_from,date_to,strategic_summary,connector_analysis,anomalies,action_recommendations,platform_evaluations,llm_model,error_message,created_by_user_sub,created_at,completed_at",
            "",
        ),
    )
    parameters = {"platforms": list(CANONICAL_PLATFORMS)}
    for table, columns, where in exact_tables:
        names = tuple(part.strip() for part in columns.split(","))
        _compare_streams(
            table,
            _rows(source, f"SELECT {columns} FROM {table} {where} ORDER BY id", parameters),
            _rows(target, f"SELECT {columns} FROM {table} {where} ORDER BY id", parameters),
            batch_size=args.batch_size,
            source_normalizer=_tuple(*names),
        )

    connection_source_columns = "id,brand_id,platform,status,expires_at,projected_at,created_at"
    _compare_streams(
        "platform_connections",
        _rows(source, f"SELECT {connection_source_columns} FROM platform_connections ORDER BY id"),
        _rows(target, f"SELECT {connection_source_columns} FROM platform_connections ORDER BY id"),
        batch_size=args.batch_size,
        source_normalizer=_tuple(*connection_source_columns.split(",")),
    )
    _compare_streams(
        "asset_sync_state",
        _rows(
            source,
            """SELECT ss.asset_id,ss.last_synced_at,ss.updated_at
               FROM asset_sync_state ss JOIN assets a ON a.id=ss.asset_id
               WHERE a.platform = ANY(:platforms) ORDER BY ss.asset_id""",
            parameters,
        ),
        _rows(
            target,
            "SELECT asset_id,last_synced_at,updated_at FROM asset_sync_state ORDER BY asset_id",
        ),
        batch_size=args.batch_size,
        source_normalizer=_tuple("asset_id", "last_synced_at", "updated_at"),
    )
    metric_columns = (
        "id,asset_id,brand_id,date,metric_id,value_numeric,breakdown_key,breakdown_value"
    )
    _compare_streams(
        "metrics_daily",
        _rows(source, f"SELECT {metric_columns} FROM metrics_daily ORDER BY id"),
        _rows(target, f"SELECT {metric_columns} FROM metrics_daily ORDER BY id"),
        batch_size=args.batch_size,
        source_normalizer=_tuple(*metric_columns.split(",")),
    )

    latest, media_urls = _content_support(source)
    content_source_columns = (
        "id,asset_id,brand_id,content_id,content_type,permalink,message,media_url,created_time,"
        "likes_count,comments_count,shares_count,created_at"
    )
    content_target_columns = (
        "id,asset_id,brand_id,content_id,content_type,permalink,message,media_url,created_time,"
        "likes_count,comments_count,shares_count,views_count,reach_count,cover_url,thumbnail_url,"
        "cover_candidates,thumbnail_candidates,media_url_candidates,full_video_watched_rate,"
        "total_time_watched,average_time_watched,interactions_count,replies_count,saves_count,"
        "sticker_taps,profile_visits,follows_count,taps_forward,taps_back,swipe_forward,exits,"
        "navigation_count,completion_rate,created_at"
    )

    def expected_content(row: Row) -> tuple[Any, ...]:
        transformed = _content_transform(row, latest, media_urls)
        return tuple(transformed[name] for name in content_target_columns.split(","))

    def actual_content(row: Row) -> tuple[Any, ...]:
        values = dict(row)
        for name in ("cover_candidates", "thumbnail_candidates", "media_url_candidates"):
            values[name] = json.dumps(values[name], ensure_ascii=True)
        return tuple(values[name] for name in content_target_columns.split(","))

    _compare_streams(
        "content_items",
        _rows(source, f"SELECT {content_source_columns} FROM content_items ORDER BY id"),
        _rows(target, f"SELECT {content_target_columns} FROM content_items ORDER BY id"),
        batch_size=args.batch_size,
        source_normalizer=expected_content,
        target_normalizer=actual_content,
    )
    media_columns = (
        "id,brand_id,asset_id,content_id,platform,media_kind,storage_path,source_url,"
        "source_status,mime_type,size_bytes,checksum,last_verified_at,created_at,updated_at"
    )
    media_names = tuple(media_columns.split(","))
    _compare_streams(
        "media_assets",
        _rows(source, f"SELECT {media_columns} FROM media_assets ORDER BY id"),
        _rows(target, f"SELECT {media_columns} FROM media_assets ORDER BY id"),
        batch_size=args.batch_size,
        source_normalizer=lambda row: tuple(
            _safe_media_url(row[name]) if name == "source_url" else row[name]
            for name in media_names
        ),
        target_normalizer=_tuple(*media_names),
    )
    _verify_media_files(source, args.source_media_root, args.target_media_root)

    projection_count = target.execute(
        text(
            """SELECT count(*) FROM social_projection_state
               WHERE projection_key='legacy-brand:' || brand_id::text
                 AND status='active'
                 AND projection_source='legacy_read_only_snapshot'
                 AND payload_json->>'mode'='read_only_copy'"""
        )
    ).scalar_one()
    if projection_count != brand_count:
        raise RuntimeError("legacy_brand_projection_mismatch")
    source_jobs = source.execute(
        text(
            """SELECT count(*) FROM linked_social_accounts
               WHERE asset_id IS NOT NULL AND last_synced_at IS NOT NULL
                 AND platform = ANY(:platforms)"""
        ),
        parameters,
    ).scalar_one()
    target_jobs = target.execute(
        text(
            """SELECT count(*) FROM social_backfill_jobs
               WHERE stage='legacy_snapshot' AND status='completed'"""
        )
    ).scalar_one()
    if source_jobs != target_jobs:
        raise RuntimeError("legacy_snapshot_job_count_mismatch")
    print(f"legacy_brand_projections={projection_count}", flush=True)
    print(f"legacy_snapshot_jobs={target_jobs}", flush=True)


def main() -> None:
    args = _arguments()
    if args.expected_brand_count < 1:
        raise RuntimeError("expected_brand_count_must_be_positive")
    if not 100 <= args.batch_size <= 50_000:
        raise RuntimeError("batch_size_out_of_range")
    source_url = make_url(_env_value(args.source_env, "SOCIAL_MEDIA_DATABASE_URL"))
    target_url = make_url(_env_value(args.target_env, "SOCIAL_DB_URL"))
    _validate_urls(source_url, target_url)
    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    source = source_engine.connect().execution_options(isolation_level="REPEATABLE READ")
    target = target_engine.connect().execution_options(isolation_level="REPEATABLE READ")
    source_transaction = source.begin()
    target_transaction = target.begin()
    try:
        source.execute(text("SET TRANSACTION READ ONLY"))
        target.execute(text("SET TRANSACTION READ ONLY"))
        _assert_read_only(source, "source")
        _assert_read_only(target, "target")
        _verify(source, target, args)
        source_transaction.rollback()
        target_transaction.rollback()
    except Exception:
        source_transaction.rollback()
        target_transaction.rollback()
        raise
    finally:
        source.close()
        target.close()
        source_engine.dispose()
        target_engine.dispose()
    print("legacy_full_import_parity=verified", flush=True)


if __name__ == "__main__":
    main()

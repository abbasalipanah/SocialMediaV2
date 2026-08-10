#!/usr/bin/env python3
"""Atomically copy an allowlisted V2-local Brand snapshot into empty V2 staging tables."""

from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import MetaData, create_engine, func, select, text
from sqlalchemy.engine import URL, make_url

EXCLUDED_TABLES = {"social_schema_migrations", "tenants"}
EXPECTED_TABLES = {
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
}


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-env", type=Path, required=True)
    parser.add_argument("--target-env", type=Path, required=True)
    parser.add_argument("--brand-id", type=int, required=True)
    return parser.parse_args()


def _env_value(path: Path, key: str) -> str:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"missing_setting:{key}")


def _validate_database_urls(source: URL, target: URL) -> None:
    if source.get_backend_name() != "postgresql" or target.get_backend_name() != "postgresql":
        raise RuntimeError("postgresql_required")
    if source.database != "social_media_v2_local":
        raise RuntimeError("source_database_must_be_v2_local")
    if target.database != "social_media_v2_staging":
        raise RuntimeError("target_database_must_be_v2_staging")
    if (source.host, source.port or 5432, source.database) == (
        target.host,
        target.port or 5432,
        target.database,
    ):
        raise RuntimeError("source_and_target_database_must_differ")


def _validate_source(connection, tables: dict[str, object], brand_id: int) -> None:
    brand_ids = tuple(connection.execute(select(tables["brands"].c.id)).scalars())
    if brand_ids != (brand_id,):
        raise RuntimeError("source_must_contain_exact_allowlisted_brand")
    projection_keys = tuple(
        connection.execute(select(tables["social_projection_state"].c.projection_key)).scalars()
    )
    if any(key != f"legacy-brand:{brand_id}" for key in projection_keys):
        raise RuntimeError("source_contains_non_snapshot_projection_state")


def _validate_empty_target(connection, tables: dict[str, object]) -> None:
    nonempty = [
        name
        for name, table in tables.items()
        if connection.execute(select(func.count()).select_from(table)).scalar_one() != 0
    ]
    if nonempty:
        raise RuntimeError(f"target_tables_must_be_empty:{','.join(sorted(nonempty))}")


def _sync_sequences(connection, tables: dict[str, object]) -> None:
    for table in tables.values():
        for column in table.primary_key.columns:
            sequence = connection.execute(
                text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
                {"table_name": table.name, "column_name": column.name},
            ).scalar_one_or_none()
            if not sequence:
                continue
            maximum = connection.execute(select(func.max(column))).scalar_one_or_none()
            if maximum is not None:
                connection.execute(
                    text("SELECT setval(CAST(:sequence AS regclass), :value, true)"),
                    {"sequence": sequence, "value": int(maximum)},
                )


def main() -> None:
    args = _arguments()
    if args.brand_id < 1:
        raise RuntimeError("brand_id_must_be_positive")
    source_url = make_url(_env_value(args.source_env, "SOCIAL_DB_URL"))
    target_url = make_url(_env_value(args.target_env, "SOCIAL_DB_URL"))
    _validate_database_urls(source_url, target_url)

    source_engine = create_engine(source_url, pool_pre_ping=True)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    try:
        source_metadata = MetaData()
        target_metadata = MetaData()
        source_metadata.reflect(bind=source_engine)
        target_metadata.reflect(bind=target_engine)
        source_names = set(source_metadata.tables).difference(EXCLUDED_TABLES)
        target_names = set(target_metadata.tables).difference(EXCLUDED_TABLES)
        if source_names != EXPECTED_TABLES or target_names != EXPECTED_TABLES:
            raise RuntimeError("v2_snapshot_schema_mismatch")
        source_tables = {name: source_metadata.tables[name] for name in EXPECTED_TABLES}
        target_tables = {name: target_metadata.tables[name] for name in EXPECTED_TABLES}

        copied: dict[str, int] = {}
        with source_engine.connect() as source, target_engine.begin() as target:
            source.execute(text("SET TRANSACTION READ ONLY"))
            if source.execute(text("SHOW transaction_read_only")).scalar_one() != "on":
                raise RuntimeError("source_connection_is_not_read_only")
            _validate_source(source, source_tables, args.brand_id)
            _validate_empty_target(target, target_tables)
            for target_table in target_metadata.sorted_tables:
                if target_table.name not in EXPECTED_TABLES:
                    continue
                source_table = source_tables[target_table.name]
                result = source.execution_options(stream_results=True).execute(select(source_table))
                count = 0
                while rows := result.mappings().fetchmany(1000):
                    target.execute(target_table.insert(), [dict(row) for row in rows])
                    count += len(rows)
                copied[target_table.name] = count
            _sync_sequences(target, target_tables)
        for name in sorted(copied):
            print(f"{name}={copied[name]}")
    finally:
        source_engine.dispose()
        target_engine.dispose()


if __name__ == "__main__":
    main()

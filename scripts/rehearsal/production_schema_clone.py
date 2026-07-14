#!/usr/bin/env python3
"""Build and fingerprint an immutable V1 migration chain on disposable PostgreSQL."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
SOURCE_BACKEND = ROOT.parent / "SocialMedia" / "backend"
BASELINE = ROOT / "docs" / "fase0" / "baseline_SocialMedia_content.sha256"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", "postgres", "db"}
BLOCKED_DATABASES = {"socialmedia_adv"}

ENVIRONMENT = '''from alembic import context
from sqlalchemy import engine_from_config, pool, text

config = context.config
target_metadata = None

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.execute(text("""CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(128) NOT NULL PRIMARY KEY
        )"""))
        connection.commit()
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    raise RuntimeError("offline_sql_generation_not_supported")
run_migrations_online()
'''


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--confirm-disposable", required=True)
    parser.add_argument("--expected", type=Path)
    return parser.parse_args()


def _assert_disposable(database_url: str, confirmation: str) -> None:
    parsed = urlparse(database_url)
    database = parsed.path.lstrip("/").split("/", 1)[0].lower()
    if (
        confirmation != "phase9-offline-only"
        or parsed.hostname not in LOCAL_HOSTS
        or not database
        or database in BLOCKED_DATABASES
    ):
        raise SystemExit("Refusing non-disposable database target")


def _baseline_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        if relative.startswith("backend/alembic/versions/") and relative.endswith(".py"):
            hashes[relative] = digest
    return hashes


def _verified_migrations() -> list[Path]:
    expected = _baseline_hashes()
    migrations = sorted((SOURCE_BACKEND / "alembic" / "versions").glob("*.py"))
    if len(migrations) != 9:
        raise SystemExit("Unexpected source migration count")
    for path in migrations:
        relative = f"backend/alembic/versions/{path.name}"
        digest = hashlib.sha256(b"file\0" + path.read_bytes()).hexdigest()
        if expected.get(relative) != digest:
            raise SystemExit(f"Source migration baseline mismatch: {path.name}")
    return migrations


def _assert_empty(database_url: str) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            count = connection.execute(
                text(
                    """SELECT count(*) FROM pg_class c
                       JOIN pg_namespace n ON n.oid=c.relnamespace
                       WHERE n.nspname='public' AND c.relkind IN ('r','p')"""
                )
            ).scalar_one()
        if count:
            raise SystemExit("Disposable clone database must start empty")
    finally:
        engine.dispose()


def _upgrade(database_url: str, migrations: list[Path]) -> None:
    with tempfile.TemporaryDirectory(prefix="social-media-v2-phase9-") as directory:
        script = Path(directory) / "alembic"
        versions = script / "versions"
        versions.mkdir(parents=True)
        (script / "env.py").write_text(ENVIRONMENT, encoding="utf-8")
        for migration in migrations:
            shutil.copy2(migration, versions / migration.name)
        config = Config()
        config.set_main_option("script_location", str(script))
        config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
        command.upgrade(config, "head")


def _rows(connection, statement: str) -> list[list[object]]:
    return [list(row) for row in connection.execute(text(statement)).tuples()]


def _fingerprint(database_url: str) -> dict[str, object]:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            tables = _rows(
                connection,
                """SELECT c.relname, c.relkind
                   FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE n.nspname='public' AND c.relkind IN ('r','p')
                   ORDER BY c.relname""",
            )
            columns = _rows(
                connection,
                """SELECT c.relname, a.attnum, a.attname,
                          pg_catalog.format_type(a.atttypid, a.atttypmod),
                          a.attnotnull, pg_get_expr(d.adbin, d.adrelid)
                   FROM pg_attribute a
                   JOIN pg_class c ON c.oid=a.attrelid
                   JOIN pg_namespace n ON n.oid=c.relnamespace
                   LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
                   WHERE n.nspname='public' AND c.relkind IN ('r','p')
                     AND a.attnum > 0 AND NOT a.attisdropped
                   ORDER BY c.relname, a.attnum""",
            )
            constraints = _rows(
                connection,
                """SELECT c.relname, x.conname, x.contype, pg_get_constraintdef(x.oid, true)
                   FROM pg_constraint x
                   JOIN pg_class c ON c.oid=x.conrelid
                   JOIN pg_namespace n ON n.oid=c.relnamespace
                   WHERE n.nspname='public'
                   ORDER BY c.relname, x.conname""",
            )
            indexes = _rows(
                connection,
                """SELECT t.relname, i.relname, pg_get_indexdef(i.oid)
                   FROM pg_index x
                   JOIN pg_class t ON t.oid=x.indrelid
                   JOIN pg_class i ON i.oid=x.indexrelid
                   JOIN pg_namespace n ON n.oid=t.relnamespace
                   WHERE n.nspname='public'
                   ORDER BY t.relname, i.relname""",
            )
            head = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            oauth_config_rows = connection.execute(
                text(
                    """SELECT count(*) FROM social_projection_state
                       WHERE projection_key='tiktok:organic:oauth_config'"""
                )
            ).scalar_one()
    finally:
        engine.dispose()
    canonical = {
        "columns": columns,
        "constraints": constraints,
        "indexes": indexes,
        "tables": tables,
    }
    encoded = json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    return {
        "alembic_head": head,
        "column_count": len(columns),
        "constraint_count": len(constraints),
        "fingerprint_sha256": hashlib.sha256(encoded).hexdigest(),
        "index_count": len(indexes),
        "oauth_config_row_count": oauth_config_rows,
        "source_migration_count": 9,
        "table_count": len(tables),
    }


def main() -> int:
    args = _arguments()
    _assert_disposable(args.database_url, args.confirm_disposable)
    migrations = _verified_migrations()
    _assert_empty(args.database_url)
    _upgrade(args.database_url, migrations)
    report = _fingerprint(args.database_url)
    if args.expected:
        expected = json.loads(args.expected.read_text(encoding="utf-8"))
        if report != expected:
            raise SystemExit("Migration-built schema fingerprint mismatch")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

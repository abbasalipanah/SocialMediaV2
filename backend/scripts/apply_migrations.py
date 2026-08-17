"""Apply ordered, V2-owned SQL migrations to the configured PostgreSQL database."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core import ConfigurationError, load_settings  # noqa: E402

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
LOCK_ID = 724_662_202


def main() -> None:
    settings = load_settings()
    if not settings.db.url:
        raise ConfigurationError("SOCIAL_DB_URL is required for migrations")
    engine = create_engine(settings.db.url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": LOCK_ID})
            connection.execute(
                text(
                    """CREATE TABLE IF NOT EXISTS social_schema_migrations (
                        version varchar(255) PRIMARY KEY,
                        checksum varchar(64) NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )"""
                )
            )
            applied = dict(
                connection.execute(
                    text("SELECT version, checksum FROM social_schema_migrations")
                ).all()
            )
            for path in sorted(MIGRATIONS.glob("*.sql")):
                sql = path.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                if path.name in applied:
                    if applied[path.name] != checksum:
                        raise RuntimeError(f"migration_checksum_mismatch:{path.name}")
                    continue
                connection.exec_driver_sql(sql)
                connection.execute(
                    text(
                        """INSERT INTO social_schema_migrations (version, checksum)
                        VALUES (:version, :checksum)"""
                    ),
                    {"version": path.name, "checksum": checksum},
                )
                print(f"applied {path.name}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

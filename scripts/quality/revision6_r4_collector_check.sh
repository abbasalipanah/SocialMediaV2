#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
CONTAINER="social-media-v2-r4-$$"
PASSWORD="disposable_revision6_r4_password"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$ROOT/scripts/source_write_guard.sh"
"$PYTHON" "$ROOT/scripts/quality/revision6_r4_collector.py"

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest -q \
    tests/test_phase4_metric_catalog.py \
    tests/test_phase4_model_registry.py \
    tests/test_phase4_platform_contracts.py \
    tests/test_phase4_worker_and_architecture.py \
    tests/test_phase5_daily_audience.py \
    tests/test_phase5_meta_parity.py \
    tests/test_phase5_recovery_contracts.py \
    tests/test_phase5_tiktok_accounts.py \
    tests/test_tiktok_runtime_transport.py \
    tests/test_secret_leak_guard.py
)

docker run \
  --name "$CONTAINER" \
  -e POSTGRES_PASSWORD="$PASSWORD" \
  -e POSTGRES_DB=social_media_v2_r4_test \
  -p 127.0.0.1::5432 \
  -d postgres:16-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -U postgres -d social_media_v2_r4_test \
    >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Disposable R4 PostgreSQL did not become ready" >&2
    exit 1
  fi
  sleep 1
done

PORT="$(docker port "$CONTAINER" 5432/tcp | awk -F: '{print $NF}')"
DATABASE_URL="postgresql+psycopg://postgres:${PASSWORD}@127.0.0.1:${PORT}/social_media_v2_r4_test"

(
  cd "$BACKEND"
  APP_ENV=development \
    SOCIAL_RUNTIME_MODE=development \
    SOCIAL_DB_URL="$DATABASE_URL" \
    "$PYTHON" scripts/apply_migrations.py
  APP_ENV=development \
    SOCIAL_RUNTIME_MODE=development \
    SOCIAL_DB_URL="$DATABASE_URL" \
    "$PYTHON" scripts/apply_migrations.py
  TEST_POSTGRES_URL="$DATABASE_URL" "$PYTHON" - <<'PY'
import os

from sqlalchemy import create_engine, text

engine = create_engine(os.environ["TEST_POSTGRES_URL"])
with engine.connect() as connection:
    versions = connection.execute(
        text("SELECT version FROM social_schema_migrations ORDER BY version")
    ).scalars().all()
    columns = set(
        connection.execute(
            text(
                """SELECT column_name FROM information_schema.columns
                   WHERE table_schema='public' AND table_name='content_items'"""
            )
        ).scalars()
    )
required = {
    "views_count",
    "reach_count",
    "cover_candidates",
    "full_video_watched_rate",
    "navigation_count",
    "completion_rate",
    "saves_count",
    "sticker_taps",
}
assert versions == [
    "0001_v2_initial.sql",
    "0002_content_story_parity.sql",
    "0003_story_action_totals.sql",
]
assert required <= columns
print("R4 migration idempotency and content columns: PASS")
engine.dispose()
PY
  TEST_POSTGRES_URL="$DATABASE_URL" "$PYTHON" -m pytest -q \
    tests/test_phase4_persistence_postgres.py \
    tests/test_phase6_reporting_postgres.py
)

(
  cd "$ROOT/frontend"
  npm test
  npm run build
)

"$ROOT/scripts/source_write_guard.sh"
echo "OK: Revision 6 R4 collector/persistence/media certification passed."

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
CONTAINER="social-media-v2-standalone-$PPID-$$"
PASSWORD="disposable_standalone_password"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker run \
  --name "$CONTAINER" \
  -e POSTGRES_PASSWORD="$PASSWORD" \
  -e POSTGRES_DB=social_media_v2_test \
  -p 127.0.0.1::5432 \
  -d postgres:16-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -U postgres -d social_media_v2_test \
    >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Disposable PostgreSQL did not become ready" >&2
    exit 1
  fi
  sleep 1
done

PORT="$(docker port "$CONTAINER" 5432/tcp | awk -F: '{print $NF}')"
export TEST_POSTGRES_URL="postgresql+psycopg://postgres:${PASSWORD}@127.0.0.1:${PORT}/social_media_v2_test"

SOCIAL_DB_URL="$TEST_POSTGRES_URL" "$PYTHON" "$BACKEND/scripts/apply_migrations.py"
SOCIAL_DB_URL="$TEST_POSTGRES_URL" "$PYTHON" "$BACKEND/scripts/apply_migrations.py"

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest -q
)

"$PYTHON" "$ROOT/scripts/quality/export_openapi.py"

(
  cd "$ROOT/frontend"
  npm run generate:api
  npm test -- --run
  npm run build
)

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
schema = json.loads((root / "docs/contracts/social-media-v2-openapi.json").read_text())
assert "/internal/provisioning/events" not in schema["paths"]
assert "/api/media/{platform}/{content_id}" in schema["paths"]

env = (root / "deploy/env/social-media-v2.production.env.example").read_text()
for line in (
    "SOCIAL_RUNTIME_MODE=standalone_ready",
    "SOCIAL_WRITES_ENABLED=false",
    "SOCIAL_META_ACCOUNT_ENABLED=false",
    "SOCIAL_META_COLLECTION_ENABLED=false",
    "SOCIAL_TIKTOK_ACCOUNT_ENABLED=false",
    "SOCIAL_TIKTOK_COLLECTION_ENABLED=false",
    "SOCIAL_WORKER_SCHEDULE_ENABLED=false",
):
    assert line in env.splitlines()

assert (root / "deploy/systemd/social-media-v2-api.service").is_file()
assert (root / "deploy/systemd/social-media-v2-collection.service").is_file()
assert (root / "deploy/systemd/social-media-v2-collection.timer").is_file()
assert (root / "deploy/systemd/social-media-v2-sentiment.service").is_file()
assert (root / "deploy/systemd/social-media-v2-sentiment.timer").is_file()
nginx = (root / "deploy/nginx/social-media-v2.conf").read_text()
assert "127.0.0.1:8026" in nginx
assert "root /opt/social-media-v2/frontend/dist" in nginx
PY

python3 "$ROOT/scripts/quality/check_secret_leaks.py"
python3 "$ROOT/scripts/quality/check_canonical_vocabulary.py"
echo "OK: standalone release verification passed."

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
CONTAINER="social-media-v2-phase2-$$"
PASSWORD="disposable_phase2_password"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$ROOT/scripts/source_write_guard.sh"
"$ROOT/scripts/quality/fase1_bootstrap_check.sh"

docker run \
  --name "$CONTAINER" \
  -e POSTGRES_PASSWORD="$PASSWORD" \
  -e POSTGRES_DB=social_media_v2_test \
  -p 127.0.0.1::5432 \
  -d postgres:16-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -U postgres -d social_media_v2_test >/dev/null 2>&1; then
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

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest
)

"$ROOT/scripts/source_write_guard.sh"
echo "OK: Faz 2 SSO-only contract certification passed."

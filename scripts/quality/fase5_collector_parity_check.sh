#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
CONTAINER="social-media-v2-phase5-$$"
PASSWORD="disposable_phase5_password"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$ROOT/scripts/source_write_guard.sh"
"$ROOT/scripts/quality/fase4_backend_independence_check.sh"

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

docker exec "$CONTAINER" createdb -U postgres social_media_v2_oracle
docker exec "$CONTAINER" createdb -U postgres social_media_v2_candidate

PORT="$(docker port "$CONTAINER" 5432/tcp | awk -F: '{print $NF}')"
BASE_URL="postgresql+psycopg://postgres:${PASSWORD}@127.0.0.1:${PORT}"
export TEST_POSTGRES_URL="${BASE_URL}/social_media_v2_test"
export TEST_PARITY_ORACLE_URL="${BASE_URL}/social_media_v2_oracle"
export TEST_PARITY_CANDIDATE_URL="${BASE_URL}/social_media_v2_candidate"

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest -q
  "$PYTHON" -m pytest -q \
    tests/test_phase5_daily_audience.py \
    tests/test_phase5_meta_parity.py \
    tests/test_phase5_persistence_differential.py \
    tests/test_phase5_recovery_contracts.py \
    tests/test_phase5_tiktok_accounts.py \
    tests/test_phase5_tiktok_state_postgres.py \
    tests/test_phase4_worker_and_architecture.py \
    tests/test_secret_leak_guard.py \
    tests/test_vocabulary_guard.py
)

python3 "$ROOT/scripts/quality/check_secret_leaks.py"
python3 "$ROOT/scripts/quality/check_canonical_vocabulary.py"
"$ROOT/scripts/source_write_guard.sh"
echo "OK: Faz 5 collector parity certification passed."

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
R8_CONTAINER="social-media-v2-r8-$PPID-$$"
R8_DB_PASSWORD="disposable_revision6_r8_password"
R8_TEMP_ROOT="$(mktemp -d /tmp/social-media-v2-r8.XXXXXX)"
R8_REPO_COPY="$R8_TEMP_ROOT/repository"
R8_API_PID=""

cleanup_r8() {
  if [[ -n "$R8_API_PID" ]] && kill -0 "$R8_API_PID" 2>/dev/null; then
    kill "$R8_API_PID" 2>/dev/null || true
    wait "$R8_API_PID" 2>/dev/null || true
  fi
  docker rm -f "$R8_CONTAINER" >/dev/null 2>&1 || true
  if [[ "$R8_TEMP_ROOT" == /tmp/social-media-v2-r8.* && -d "$R8_TEMP_ROOT" ]]; then
    rm -rf -- "$R8_TEMP_ROOT"
  fi
}
trap cleanup_r8 EXIT INT TERM

if [[ ! -x "$PYTHON" ]]; then
  echo "Backend environment is missing: $BACKEND/.venv" >&2
  exit 1
fi

"$PYTHON" - <<'PY'
import socket

with socket.socket() as probe:
    if probe.connect_ex(("127.0.0.1", 8026)) == 0:
        raise SystemExit("Disposable staging port 8026 is already in use")
PY

"$ROOT/scripts/source_write_guard.sh"

mkdir -p "$R8_REPO_COPY/backend" "$R8_TEMP_ROOT/dist" "$R8_TEMP_ROOT/install"
rsync -a \
  --exclude=.venv \
  --exclude=build \
  --exclude=dist \
  --exclude='*.egg-info' \
  --exclude=__pycache__ \
  --exclude=.pytest_cache \
  --exclude=.ruff_cache \
  --exclude=.mypy_cache \
  "$BACKEND/" "$R8_REPO_COPY/backend/"

docker run \
  --name "$R8_CONTAINER" \
  -e POSTGRES_PASSWORD="$R8_DB_PASSWORD" \
  -e POSTGRES_DB=social_media_v2_staging_rehearsal \
  -p 127.0.0.1::5432 \
  -d postgres:16-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$R8_CONTAINER" pg_isready -U postgres -d social_media_v2_staging_rehearsal \
    >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Disposable R8 PostgreSQL did not become ready" >&2
    exit 1
  fi
  sleep 1
done

R8_DB_PORT="$(docker port "$R8_CONTAINER" 5432/tcp | awk -F: '{print $NF}')"
R8_DB_URL="postgresql+psycopg://postgres:${R8_DB_PASSWORD}@127.0.0.1:${R8_DB_PORT}/social_media_v2_staging_rehearsal"

(
  cd "$R8_REPO_COPY/backend"
  APP_ENV=development SOCIAL_RUNTIME_MODE=development SOCIAL_DB_URL="$R8_DB_URL" \
    "$PYTHON" scripts/apply_migrations.py
  APP_ENV=development SOCIAL_RUNTIME_MODE=development SOCIAL_DB_URL="$R8_DB_URL" \
    "$PYTHON" scripts/apply_migrations.py
)

"$PYTHON" -m build --wheel --no-isolation \
  --outdir "$R8_TEMP_ROOT/dist" "$R8_REPO_COPY/backend" >/dev/null

R8_WHEELS=("$R8_TEMP_ROOT"/dist/*.whl)
if [[ "${#R8_WHEELS[@]}" -ne 1 || ! -f "${R8_WHEELS[0]}" ]]; then
  echo "Expected exactly one disposable R8 backend wheel" >&2
  exit 1
fi
"$PYTHON" -m pip install --no-deps --target "$R8_TEMP_ROOT/install" \
  "${R8_WHEELS[0]}" >/dev/null

export PYTHONPATH="$R8_TEMP_ROOT/install"
export APP_ENV=production
export SOCIAL_RUNTIME_MODE=standalone_ready
export SOCIAL_WRITES_ENABLED=false
export SOCIAL_DB_URL="$R8_DB_URL"
export SOCIAL_DB_REQUIRE_TLS=false
export SOCIAL_VAULT_ENABLED=false
export SOCIAL_SESSION_COOKIE_SECURE=true
export SOCIAL_WORKER_SCHEDULE_ENABLED=false
export SOCIAL_META_ACCOUNT_ENABLED=false
export SOCIAL_META_ACCOUNT_OAUTH_MODE=disabled
export SOCIAL_META_COLLECTION_ENABLED=false
export SOCIAL_META_ACTIVATION_GATE_ENABLED=false
export SOCIAL_TIKTOK_ACCOUNT_ENABLED=false
export SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled
export SOCIAL_TIKTOK_COLLECTION_ENABLED=false
export SOCIAL_TIKTOK_ADVERTISER_ENABLED=false
export SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED=false

"$PYTHON" -m uvicorn app.main:create_app --factory \
  --host 127.0.0.1 --port 8026 >"$R8_TEMP_ROOT/api.log" 2>&1 &
R8_API_PID=$!

for attempt in $(seq 1 40); do
  if curl --fail --silent http://127.0.0.1:8026/api/health >/dev/null; then
    break
  fi
  if ! kill -0 "$R8_API_PID" 2>/dev/null; then
    echo "Disposable R8 API stopped during startup" >&2
    exit 1
  fi
  if [[ "$attempt" -eq 40 ]]; then
    echo "Disposable R8 API did not become ready" >&2
    exit 1
  fi
  sleep 0.25
done

"$PYTHON" - <<'PY'
import json
import urllib.request

with urllib.request.urlopen("http://127.0.0.1:8026/api/health") as response:
    assert json.load(response) == {"status": "ok"}
with urllib.request.urlopen("http://127.0.0.1:8026/api/operations/readiness") as response:
    readiness = json.load(response)
assert readiness["runtime_mode"] == "standalone_ready"
assert readiness["writes_enabled"] is False
print("R8 disposable staging health/readiness: PASS")
PY

"$PYTHON" - <<'PY'
from app.core import ConfigurationError
from app.workers.collector import main

try:
    main(["collect", "--platform", "all", "--scheduled"])
except ConfigurationError as exc:
    assert str(exc) == "Scheduled collection is disabled"
else:
    raise AssertionError("scheduled collection unexpectedly opened")
print("R8 disposable staging schedule gate: PASS")
PY

kill "$R8_API_PID"
wait "$R8_API_PID" 2>/dev/null || true
R8_API_PID=""

"$PYTHON" - <<'PY'
import socket

with socket.socket() as probe:
    assert probe.connect_ex(("127.0.0.1", 8026)) != 0
print("R8 disposable staging rollback/port-close: PASS")
PY

"$ROOT/scripts/source_write_guard.sh"
echo "OK: Revision 6 R8 disposable staging deploy/rollback rehearsal passed."

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
R7_CONTAINER="social-media-v2-r7-$PPID-$$"
R7_DB_PASSWORD="disposable_revision6_r7_password"
R7_TEMP_ROOT="$(mktemp -d /tmp/social-media-v2-r7.XXXXXX)"
R7_REPO_COPY="$R7_TEMP_ROOT/repository"

cleanup_r7() {
  docker rm -f "$R7_CONTAINER" >/dev/null 2>&1 || true
  if [[ "$R7_TEMP_ROOT" == /tmp/social-media-v2-r7.* && -d "$R7_TEMP_ROOT" ]]; then
    rm -rf -- "$R7_TEMP_ROOT"
  fi
}
trap cleanup_r7 EXIT

export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$R7_TEMP_ROOT/pycache"

"$ROOT/scripts/source_write_guard.sh"
"$PYTHON" "$ROOT/scripts/quality/revision6_r1_inventory.py"
"$PYTHON" "$ROOT/scripts/quality/revision6_r3_contract.py"
"$PYTHON" "$ROOT/scripts/quality/revision6_r4_collector.py"
"$PYTHON" "$ROOT/scripts/quality/revision6_r5_frontend.py"
"$PYTHON" "$ROOT/scripts/quality/revision6_r6_runtime.py"

docker run \
  --name "$R7_CONTAINER" \
  -e POSTGRES_PASSWORD="$R7_DB_PASSWORD" \
  -e POSTGRES_DB=social_media_v2_r7 \
  -p 127.0.0.1::5432 \
  -d postgres:16-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$R7_CONTAINER" pg_isready -U postgres -d social_media_v2_r7 \
    >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Disposable R7 PostgreSQL did not become ready" >&2
    exit 1
  fi
  sleep 1
done

docker exec "$R7_CONTAINER" createdb -U postgres social_media_v2_r7_oracle
docker exec "$R7_CONTAINER" createdb -U postgres social_media_v2_r7_candidate

R7_DB_PORT="$(docker port "$R7_CONTAINER" 5432/tcp | awk -F: '{print $NF}')"
R7_DB_BASE="postgresql+psycopg://postgres:${R7_DB_PASSWORD}@127.0.0.1:${R7_DB_PORT}"
R7_MAIN_DB="$R7_DB_BASE/social_media_v2_r7"
export TEST_POSTGRES_URL="$R7_MAIN_DB"
export TEST_PARITY_ORACLE_URL="$R7_DB_BASE/social_media_v2_r7_oracle"
export TEST_PARITY_CANDIDATE_URL="$R7_DB_BASE/social_media_v2_r7_candidate"

(
  cd "$BACKEND"
  APP_ENV=development SOCIAL_RUNTIME_MODE=development SOCIAL_DB_URL="$R7_MAIN_DB" \
    "$PYTHON" scripts/apply_migrations.py
  APP_ENV=development SOCIAL_RUNTIME_MODE=development SOCIAL_DB_URL="$R7_MAIN_DB" \
    "$PYTHON" scripts/apply_migrations.py

  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m compileall -q app tests "$ROOT/scripts/quality"
  "$PYTHON" -m mypy app --cache-dir="$R7_TEMP_ROOT/mypy" --no-incremental
  "$PYTHON" -m pytest -q
)

PYTHONPATH="$BACKEND" \
APP_ENV=production \
SOCIAL_RUNTIME_MODE=standalone_ready \
SOCIAL_WRITES_ENABLED=false \
SOCIAL_DB_URL="$R7_MAIN_DB" \
SOCIAL_DB_REQUIRE_TLS=false \
SOCIAL_VAULT_ENABLED=false \
SOCIAL_SESSION_COOKIE_SECURE=true \
SOCIAL_WORKER_SCHEDULE_ENABLED=false \
SOCIAL_META_ACCOUNT_ENABLED=false \
SOCIAL_META_ACCOUNT_OAUTH_MODE=disabled \
SOCIAL_META_COLLECTION_ENABLED=false \
SOCIAL_META_ACTIVATION_GATE_ENABLED=false \
SOCIAL_TIKTOK_ACCOUNT_ENABLED=false \
SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled \
SOCIAL_TIKTOK_COLLECTION_ENABLED=false \
SOCIAL_TIKTOK_ADVERTISER_ENABLED=false \
SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED=false \
"$PYTHON" - <<'PY'
import asyncio

from httpx import ASGITransport, AsyncClient

from app.core import ConfigurationError, RuntimeMode, load_settings
from app.main import create_app
from app.workers.collector import main as worker_main

settings = load_settings()
assert settings.runtime_mode is RuntimeMode.STANDALONE_READY
assert settings.social_writes_enabled is False
assert settings.worker_schedule_enabled is False


async def smoke() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://r7") as client:
        health = await client.get("/api/health")
        readiness = await client.get("/api/operations/readiness")
    assert health.status_code == 200 and health.json() == {"status": "ok"}
    assert readiness.status_code == 200
    assert readiness.json()["runtime_mode"] == "standalone_ready"
    assert readiness.json()["writes_enabled"] is False


asyncio.run(smoke())
try:
    worker_main(["collect", "--platform", "all", "--scheduled"])
except ConfigurationError as exc:
    assert str(exc) == "Scheduled collection is disabled"
else:
    raise AssertionError("scheduled worker unexpectedly opened")
print("R7 standalone deploy/rollback smoke: PASS")
PY

"$PYTHON" "$ROOT/scripts/quality/export_openapi.py" --check
"$PYTHON" "$ROOT/scripts/quality/check_secret_leaks.py"
"$PYTHON" "$ROOT/scripts/quality/check_canonical_vocabulary.py"
"$PYTHON" -m ruff check \
  "$ROOT/scripts/quality/export_openapi.py" \
  "$ROOT/scripts/quality/revision6_r7_release.py"

mkdir -p "$R7_REPO_COPY/backend" "$R7_REPO_COPY/frontend" "$R7_REPO_COPY/docs"
rsync -a \
  --exclude=.venv \
  --exclude=build \
  --exclude=dist \
  --exclude='*.egg-info' \
  --exclude=__pycache__ \
  --exclude=.pytest_cache \
  --exclude=.ruff_cache \
  --exclude=.mypy_cache \
  "$BACKEND/" "$R7_REPO_COPY/backend/"
rsync -a \
  --exclude=node_modules \
  --exclude=dist \
  --exclude=test-results \
  --exclude=playwright-report \
  "$ROOT/frontend/" "$R7_REPO_COPY/frontend/"
rsync -a "$ROOT/docs/" "$R7_REPO_COPY/docs/"

mkdir -p "$R7_TEMP_ROOT/backend-dist" "$R7_TEMP_ROOT/wheel-install"
"$PYTHON" -m build --wheel --no-isolation \
  --outdir "$R7_TEMP_ROOT/backend-dist" "$R7_REPO_COPY/backend"

R7_WHEELS=("$R7_TEMP_ROOT"/backend-dist/*.whl)
if [[ "${#R7_WHEELS[@]}" -ne 1 || ! -f "${R7_WHEELS[0]}" ]]; then
  echo "Expected exactly one R7 backend wheel" >&2
  exit 1
fi
"$PYTHON" -m pip install --no-deps --target "$R7_TEMP_ROOT/wheel-install" \
  "${R7_WHEELS[0]}" >/dev/null
(
  cd "$R7_TEMP_ROOT"
  PYTHONPATH="$R7_TEMP_ROOT/wheel-install" "$PYTHON" - <<'PY'
from pathlib import Path

import app
from app.main import create_app

location = Path(app.__file__).resolve()
assert "wheel-install" in location.parts
assert create_app().title == "Social Media V2"
print("R7 installed-wheel import smoke: PASS")
PY
)

(
  cd "$R7_REPO_COPY/frontend"
  npm ci --ignore-scripts --no-audit --no-fund
  npm run generate:api
  cmp src/api/openapi.generated.ts "$ROOT/frontend/src/api/openapi.generated.ts"
  npm run typecheck
  npm test -- --run
  npm run build
  npm audit --audit-level=high

  "$PYTHON" - <<'PY'
import socket

with socket.socket() as probe:
    if probe.connect_ex(("127.0.0.1", 3011)) == 0:
        raise SystemExit("R7 Playwright port 3011 is already in use")
PY
  npm run test:e2e
)

"$PYTHON" "$ROOT/scripts/quality/revision6_r7_release.py" \
  --frontend-dist "$R7_REPO_COPY/frontend/dist" \
  --backend-wheel "${R7_WHEELS[0]}" \
  --manifest "$ROOT/docs/revision6/r7/r7_release_artifact_manifest.json"

"$ROOT/scripts/source_write_guard.sh"
echo "OK: Revision 6 R7 standalone product release-candidate certification passed."

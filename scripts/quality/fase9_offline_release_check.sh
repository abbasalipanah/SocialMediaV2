#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
CONTAINER="social-media-v2-phase9-$$"
PASSWORD="disposable_phase9_password"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

"$ROOT/scripts/source_write_guard.sh"
"$ROOT/scripts/quality/fase8_social_pages_settings_check.sh"

docker run \
  --name "$CONTAINER" \
  -e POSTGRES_PASSWORD="$PASSWORD" \
  -e POSTGRES_DB=phase9_schema_clone \
  -p 127.0.0.1::5432 \
  -d postgres:16-alpine >/dev/null

for attempt in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -U postgres -d phase9_schema_clone \
    >/dev/null 2>&1; then
    break
  fi
  if [[ "$attempt" -eq 30 ]]; then
    echo "Disposable PostgreSQL did not become ready" >&2
    exit 1
  fi
  sleep 1
done

docker exec "$CONTAINER" createdb -U postgres phase9_full_test
PORT="$(docker port "$CONTAINER" 5432/tcp | awk -F: '{print $NF}')"
BASE_URL="postgresql+psycopg://postgres:${PASSWORD}@127.0.0.1:${PORT}"
export PHASE9_POSTGRES_URL="${BASE_URL}/phase9_schema_clone"
export TEST_POSTGRES_URL="${BASE_URL}/phase9_full_test"

"$PYTHON" "$ROOT/scripts/rehearsal/production_schema_clone.py" \
  --database-url "$PHASE9_POSTGRES_URL" \
  --confirm-disposable phase9-offline-only \
  --expected "$ROOT/docs/fase9/production_schema_fingerprint.json"

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest -q
  "$PYTHON" -m pytest -q tests/test_phase9_release_rehearsal.py
)

"$PYTHON" "$ROOT/scripts/quality/export_openapi.py"

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
schema = json.loads((root / "docs/contracts/social-media-v2-openapi.json").read_text())
assert set(schema["paths"]["/api/settings/tiktok/activation-readiness"]) == {"get"}
assert set(schema["paths"]["/api/settings/tiktok/oauth/account/start"]) == {"post"}
assert set(schema["paths"]["/api/social/tiktok/oauth/callback"]) == {"get"}

env = (root / "deploy/env/social-media-v2.dormant.env").read_text().splitlines()
required = {
    "SOCIAL_RUNTIME_MODE=dormant",
    "SOCIAL_WRITES_ENABLED=false",
    "SOCIAL_TIKTOK_ACCOUNT_ENABLED=false",
    "SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled",
    "SOCIAL_TIKTOK_COLLECTION_ENABLED=false",
    "SOCIAL_TIKTOK_ADVERTISER_ENABLED=false",
}
assert required.issubset(env)

for unit in (root / "deploy/systemd").glob("*.service"):
    lines = unit.read_text().splitlines()
    assert not any(line.strip() == "[Install]" for line in lines)
assert not list((root / "deploy").rglob("*.timer"))
assert not list((root / "deploy").rglob("*cron*"))

nginx = (root / "deploy/nginx/social-media-v2-dark.conf").read_text()
assert "listen 127.0.0.1:8089" in nginx
assert "location /" in nginx and "return 404" in nginx

provider = (
    root
    / "backend/app/infrastructure/providers/tiktok/accounts/activation.py"
).read_text()
assert "httpx" not in provider and "requests" not in provider
PY

python3 "$ROOT/scripts/quality/check_secret_leaks.py"
python3 "$ROOT/scripts/quality/check_canonical_vocabulary.py"
"$ROOT/scripts/source_write_guard.sh"
echo "OK: Faz 9 offline release rehearsal certification passed."

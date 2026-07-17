#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="$BACKEND/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Backend environment is missing: $BACKEND/.venv" >&2
  echo "Create it and install backend/requirements-dev.lock before starting local demo." >&2
  exit 1
fi
if [[ ! -x "$FRONTEND/node_modules/.bin/vite" ]]; then
  echo "Frontend dependencies are missing. Run: cd $FRONTEND && npm ci" >&2
  exit 1
fi

for port in 8000 3010; do
  if python3 - "$port" <<'PY'
import socket
import sys

port = int(sys.argv[1])
with socket.socket() as probe:
    raise SystemExit(probe.connect_ex(("127.0.0.1", port)) == 0)
PY
  then
    continue
  fi
  echo "Port $port is already in use. Stop the existing process and retry." >&2
  exit 1
done

backend_pid=""
cleanup_local() {
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
    wait "$backend_pid" 2>/dev/null || true
  fi
}
trap cleanup_local EXIT INT TERM

unset SOCIAL_DB_URL SOCIAL_DB_HOST SOCIAL_DB_NAME SOCIAL_DB_USER SOCIAL_DB_PASSWORD
export APP_ENV=development
export SOCIAL_RUNTIME_MODE=development
export SOCIAL_WRITES_ENABLED=false
export SOCIAL_LOCAL_DEMO=true
export SOCIAL_TIKTOK_ACCOUNT_ENABLED=false
export SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled
export SOCIAL_TIKTOK_COLLECTION_ENABLED=false
export SOCIAL_TIKTOK_ADVERTISER_ENABLED=false

(
  cd "$BACKEND"
  exec "$PYTHON" -m uvicorn app.local_demo:create_local_demo_app \
    --factory --host 127.0.0.1 --port 8000
) &
backend_pid=$!

for attempt in $(seq 1 40); do
  if curl --fail --silent http://127.0.0.1:8000/api/health >/dev/null; then
    break
  fi
  if ! kill -0 "$backend_pid" 2>/dev/null; then
    echo "Local demo backend stopped during startup." >&2
    exit 1
  fi
  if [[ "$attempt" -eq 40 ]]; then
    echo "Local demo backend did not become ready." >&2
    exit 1
  fi
  sleep 0.25
done

echo
echo "Social Media local demo is ready: http://127.0.0.1:3010/"
echo "Demo data is in memory; production DB and providers are not used."
echo "Press Ctrl+C to stop both processes."
echo

cd "$FRONTEND"
export VITE_API_PROXY_TARGET=http://127.0.0.1:8000
export VITE_LOCAL_DEMO=true
npm run dev

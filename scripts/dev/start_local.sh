#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="$BACKEND/.venv/bin/python"
LOCAL_STATE="${SOCIAL_LOCAL_STATE_DIR:-$ROOT/.local}"
RUNTIME_ENV="${SOCIAL_LOCAL_DB_ENV_FILE:-$LOCAL_STATE/social-media-v2-db.env}"
API_PORT="${SOCIAL_LOCAL_API_PORT:-8000}"
FRONTEND_PORT="${SOCIAL_LOCAL_FRONTEND_PORT:-3010}"

for port in "$API_PORT" "$FRONTEND_PORT"; do
  if [[ ! "$port" =~ ^[0-9]+$ ]] || ((port < 1 || port > 65535)); then
    echo "Invalid local port: $port" >&2
    exit 1
  fi
done
if [[ "$API_PORT" == "$FRONTEND_PORT" ]]; then
  echo "Backend and frontend ports must be different." >&2
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "Backend environment is missing: $BACKEND/.venv" >&2
  echo "Create it and install backend/requirements-dev.lock before starting local demo." >&2
  exit 1
fi
if [[ ! -x "$FRONTEND/node_modules/.bin/vite" ]]; then
  echo "Frontend dependencies are missing. Run: cd $FRONTEND && npm ci" >&2
  exit 1
fi

"$ROOT/scripts/dev/ensure_local_db.sh"
set -a
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
set +a

for port in "$API_PORT" "$FRONTEND_PORT"; do
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

export APP_ENV=development
export SOCIAL_RUNTIME_MODE=development
export SOCIAL_LOCAL_DEMO=true
case "${SOCIAL_LOCAL_ACTIVATION_PROFILE:-disabled}" in
  disabled)
    export SOCIAL_WRITES_ENABLED=false
    ;;
  youtube_canary)
    if [[ "$RUNTIME_ENV" != "$ROOT/.local/platform-expansion-db.env" ]] \
      || [[ "${SOCIAL_DB_HOST:-}" != "127.0.0.1" ]] \
      || [[ "${SOCIAL_DB_PORT:-}" != "56432" ]] \
      || [[ "${SOCIAL_DB_NAME:-}" != "social_media_v2_platforms_dev" ]]; then
      echo "YouTube canary writes require the isolated platform-expansion database." >&2
      exit 1
    fi
    export SOCIAL_WRITES_ENABLED=true
    ;;
  *)
    echo "Unsupported local activation profile: $SOCIAL_LOCAL_ACTIVATION_PROFILE" >&2
    exit 1
    ;;
esac
export SOCIAL_TIKTOK_ACCOUNT_ENABLED=false
export SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled
export SOCIAL_TIKTOK_COLLECTION_ENABLED=false
export SOCIAL_TIKTOK_ADVERTISER_ENABLED=false
export SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED=false
export SOCIAL_META_ACCOUNT_ENABLED=false
export SOCIAL_META_ACCOUNT_OAUTH_MODE=disabled
export SOCIAL_META_ACTIVATION_GATE_ENABLED=false

(
  cd "$BACKEND"
  exec "$PYTHON" -m uvicorn app.local_demo:create_local_demo_app \
    --factory --host 127.0.0.1 --port "$API_PORT" \
    --reload --reload-dir "$BACKEND/app"
) &
backend_pid=$!

for attempt in $(seq 1 40); do
  if curl --fail --silent "http://127.0.0.1:${API_PORT}/api/health" >/dev/null; then
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
echo "Social Media local demo is ready: http://127.0.0.1:${FRONTEND_PORT}/"
echo "Dashboard data is read from the isolated Social Media V2 local database."
echo "Production providers and source-project writers are not used."
if [[ "${SOCIAL_LOCAL_ACTIVATION_PROFILE:-disabled}" == "youtube_canary" ]]; then
  echo "YouTube OAuth canary is enabled; scheduled collection remains disabled."
fi
echo "Press Ctrl+C to stop both processes."
echo

cd "$FRONTEND"
export VITE_API_PROXY_TARGET="http://127.0.0.1:${API_PORT}"
export VITE_DEV_SERVER_PORT="$FRONTEND_PORT"
export VITE_LOCAL_DEMO=true
npm run dev:frontend

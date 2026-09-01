#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
PYTHON="$BACKEND/.venv/bin/python"
BRAND_ID="${SOCIAL_YOUTUBE_CANARY_BRAND_ID:-18}"

# shellcheck source=youtube_canary_env.sh
source "$ROOT/scripts/dev/youtube_canary_env.sh"
prepare_youtube_canary_env "$ROOT"

if [[ ! "$BRAND_ID" =~ ^[1-9][0-9]*$ ]]; then
  echo "SOCIAL_YOUTUBE_CANARY_BRAND_ID must be a positive integer." >&2
  exit 1
fi
if [[ ! -x "$PYTHON" ]]; then
  echo "Backend environment is missing: $PYTHON" >&2
  exit 1
fi

"$ROOT/scripts/dev/ensure_local_db.sh"
set -a
# shellcheck disable=SC1090
source "$SOCIAL_LOCAL_DB_ENV_FILE"
set +a

if [[ "$SOCIAL_LOCAL_DB_ENV_FILE" != "$ROOT/.local/platform-expansion-db.env" ]] \
  || [[ "${SOCIAL_DB_HOST:-}" != "127.0.0.1" ]] \
  || [[ "${SOCIAL_DB_PORT:-}" != "56432" ]] \
  || [[ "${SOCIAL_DB_NAME:-}" != "social_media_v2_platforms_dev" ]]; then
  echo "YouTube canary collection requires the isolated platform-expansion database." >&2
  exit 1
fi

export APP_ENV=development
export SOCIAL_RUNTIME_MODE=development
export SOCIAL_WRITES_ENABLED=true
export SOCIAL_YOUTUBE_COLLECTION_ENABLED=true
export SOCIAL_WORKER_SCHEDULE_ENABLED=false

cd "$BACKEND"
exec "$PYTHON" -m app.workers collect \
  --platform youtube \
  --brand-id "$BRAND_ID" \
  --complete

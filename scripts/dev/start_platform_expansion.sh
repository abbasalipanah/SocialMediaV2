#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

export SOCIAL_LOCAL_DB_ENV_FILE="$ROOT/.local/platform-expansion-db.env"
export SOCIAL_LOCAL_DB_CONTAINER="social-media-v2-platforms-postgres"
export SOCIAL_LOCAL_DB_VOLUME="social_media_v2_platforms_data"
export SOCIAL_LOCAL_DB_PORT="56432"
export SOCIAL_LOCAL_DB_NAME="social_media_v2_platforms_dev"
export SOCIAL_LOCAL_API_PORT="8126"
export SOCIAL_LOCAL_FRONTEND_PORT="3126"

exec "$ROOT/scripts/dev/start_local.sh"

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCAL_STATE="${SOCIAL_LOCAL_STATE_DIR:-$ROOT/.local}"
RUNTIME_ENV="${SOCIAL_LOCAL_DB_ENV_FILE:-$LOCAL_STATE/social-media-v2-db.env}"
CONTAINER="${SOCIAL_LOCAL_DB_CONTAINER:-social-media-v2-postgres}"
VOLUME="${SOCIAL_LOCAL_DB_VOLUME:-social_media_v2_postgres_data}"
IMAGE="${SOCIAL_LOCAL_DB_IMAGE:-postgres:16-alpine}"
HOST_PORT="${SOCIAL_LOCAL_DB_PORT:-55432}"
DATABASE="${SOCIAL_LOCAL_DB_NAME:-social_media_v2_local}"
DATABASE_USER="${SOCIAL_LOCAL_DB_USER:-social_media_v2}"

if [[ ! "$HOST_PORT" =~ ^[0-9]+$ ]] || ((HOST_PORT < 1 || HOST_PORT > 65535)); then
  echo "Invalid local database port: $HOST_PORT" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for the isolated Social Media V2 local database." >&2
  exit 1
fi

mkdir -p "$LOCAL_STATE"
chmod 700 "$LOCAL_STATE"

if [[ ! -f "$RUNTIME_ENV" ]]; then
  if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
    echo "Local DB container exists but its ignored runtime env file is missing." >&2
    echo "Restore $RUNTIME_ENV or remove only the $CONTAINER development container." >&2
    exit 1
  fi
  umask 077
  database_password="$(openssl rand -hex 24)"
  {
    printf 'SOCIAL_DB_URL=postgresql+psycopg://%s:%s@127.0.0.1:%s/%s\n' \
      "$DATABASE_USER" "$database_password" "$HOST_PORT" "$DATABASE"
    printf 'SOCIAL_DB_HOST=127.0.0.1\n'
    printf 'SOCIAL_DB_PORT=%s\n' "$HOST_PORT"
    printf 'SOCIAL_DB_NAME=%s\n' "$DATABASE"
    printf 'SOCIAL_DB_USER=%s\n' "$DATABASE_USER"
    printf 'SOCIAL_DB_PASSWORD=%s\n' "$database_password"
    printf 'SOCIAL_MEDIA_STORAGE_ROOT=%s\n' "$LOCAL_STATE/media"
  } >"$RUNTIME_ENV"
fi

if ! grep -q '^SOCIAL_MEDIA_STORAGE_ROOT=' "$RUNTIME_ENV"; then
  printf 'SOCIAL_MEDIA_STORAGE_ROOT=%s\n' "$LOCAL_STATE/media" >>"$RUNTIME_ENV"
fi

# This file is generated locally, mode 0600, and ignored by Git.
set -a
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
set +a

if ! docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  docker run -d \
    --name "$CONTAINER" \
    --restart unless-stopped \
    -e POSTGRES_DB="$DATABASE" \
    -e POSTGRES_USER="$DATABASE_USER" \
    -e POSTGRES_PASSWORD="$SOCIAL_DB_PASSWORD" \
    -p "127.0.0.1:${HOST_PORT}:5432" \
    -v "${VOLUME}:/var/lib/postgresql/data" \
    --health-cmd="pg_isready -U $DATABASE_USER -d $DATABASE" \
    --health-interval=2s \
    --health-timeout=3s \
    --health-retries=30 \
    "$IMAGE" >/dev/null
elif [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" != "true" ]]; then
  docker start "$CONTAINER" >/dev/null
fi

for attempt in $(seq 1 40); do
  if [[ "$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$CONTAINER")" == "healthy" ]]; then
    break
  fi
  if [[ "$attempt" -eq 40 ]]; then
    echo "Social Media V2 local database did not become healthy." >&2
    exit 1
  fi
  sleep 0.25
done

APP_ENV=development \
SOCIAL_RUNTIME_MODE=development \
SOCIAL_WRITES_ENABLED=false \
SOCIAL_DB_REQUIRE_TLS=false \
SOCIAL_YOUTUBE_ACCOUNT_ENABLED=false \
SOCIAL_YOUTUBE_ACCOUNT_OAUTH_MODE=disabled \
SOCIAL_YOUTUBE_COLLECTION_ENABLED=false \
SOCIAL_YOUTUBE_ACTIVATION_GATE_ENABLED=false \
SOCIAL_X_ACCOUNT_ENABLED=false \
SOCIAL_X_ACCOUNT_OAUTH_MODE=disabled \
SOCIAL_X_COLLECTION_ENABLED=false \
SOCIAL_X_ACTIVATION_GATE_ENABLED=false \
SOCIAL_LINKEDIN_ACCOUNT_ENABLED=false \
SOCIAL_LINKEDIN_ACCOUNT_OAUTH_MODE=disabled \
SOCIAL_LINKEDIN_COLLECTION_ENABLED=false \
SOCIAL_LINKEDIN_ACTIVATION_GATE_ENABLED=false \
"$ROOT/backend/.venv/bin/python" "$ROOT/backend/scripts/apply_migrations.py"

echo "Social Media V2 local database is ready on 127.0.0.1:${HOST_PORT}."

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOCAL_STATE="$ROOT/.local"
CREDENTIAL_FILE="${SOCIAL_YOUTUBE_DEV_CLIENT_FILE:-/home/api/.secrets/socialmedia/youtube-dev-client.json}"
OAUTH_STATE_FILE="$LOCAL_STATE/youtube-canary-oauth-state.secret"
VAULT_KEY_FILE="$LOCAL_STATE/youtube-canary-vault.key"
EXPECTED_REDIRECT_URI="http://localhost:8126/api/social/youtube/oauth/callback"

for command_name in jq openssl; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "$command_name is required for the YouTube canary runtime." >&2
    exit 1
  fi
done

if [[ ! -f "$CREDENTIAL_FILE" ]]; then
  echo "YouTube development OAuth credential is missing: $CREDENTIAL_FILE" >&2
  exit 1
fi
if [[ "$(stat -c '%a' "$CREDENTIAL_FILE")" != "600" ]]; then
  echo "YouTube development OAuth credential must have mode 0600." >&2
  exit 1
fi
if ! jq -e --arg redirect_uri "$EXPECTED_REDIRECT_URI" '
  (.web.project_id == "first-dex-ela")
  and (.web.client_id | type == "string" and endswith(".apps.googleusercontent.com"))
  and (.web.client_secret | type == "string" and length > 20)
  and (.web.redirect_uris == [$redirect_uri])
' "$CREDENTIAL_FILE" >/dev/null; then
  echo "YouTube development OAuth credential does not match the approved contract." >&2
  exit 1
fi

mkdir -p "$LOCAL_STATE"
chmod 700 "$LOCAL_STATE"
umask 077
if [[ ! -f "$OAUTH_STATE_FILE" ]]; then
  openssl rand -base64 48 >"$OAUTH_STATE_FILE"
fi
if [[ ! -f "$VAULT_KEY_FILE" ]]; then
  openssl rand -base64 32 >"$VAULT_KEY_FILE"
fi
chmod 600 "$OAUTH_STATE_FILE" "$VAULT_KEY_FILE"

youtube_client_id="$(jq -er '.web.client_id' "$CREDENTIAL_FILE")"
youtube_client_secret="$(jq -er '.web.client_secret' "$CREDENTIAL_FILE")"
oauth_state_secret="$(tr -d '\r\n' <"$OAUTH_STATE_FILE")"
vault_key="$(tr -d '\r\n' <"$VAULT_KEY_FILE")"
credential_keyring="$(jq -cn --arg key "$vault_key" '{"youtube-dev-key": $key}')"
enabled_at="$(date -u -d '5 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')"
expires_at="$(date -u -d '12 hours' '+%Y-%m-%dT%H:%M:%SZ')"

export SOCIAL_LOCAL_DB_ENV_FILE="$ROOT/.local/platform-expansion-db.env"
export SOCIAL_LOCAL_DB_CONTAINER="social-media-v2-platforms-postgres"
export SOCIAL_LOCAL_DB_VOLUME="social_media_v2_platforms_data"
export SOCIAL_LOCAL_DB_PORT="56432"
export SOCIAL_LOCAL_DB_NAME="social_media_v2_platforms_dev"
export SOCIAL_LOCAL_API_PORT="8126"
export SOCIAL_LOCAL_FRONTEND_PORT="3126"
export SOCIAL_LOCAL_ACTIVATION_PROFILE="youtube_canary"
export SOCIAL_VAULT_ENABLED=true
export SOCIAL_WORKER_SCHEDULE_ENABLED=false
export SOCIAL_CREDENTIAL_ACTIVE_KEY_ID="youtube-dev-key"
export SOCIAL_CREDENTIAL_KEYRING_JSON="$credential_keyring"
export SOCIAL_YOUTUBE_OAUTH_APP_ID="$youtube_client_id"
export SOCIAL_YOUTUBE_OAUTH_APP_SECRET="$youtube_client_secret"
export SOCIAL_YOUTUBE_ACCOUNT_ENABLED=true
export SOCIAL_YOUTUBE_ACCOUNT_OAUTH_MODE="manual_intent_only"
export SOCIAL_YOUTUBE_COLLECTION_ENABLED=false
export SOCIAL_YOUTUBE_REDIRECT_URI="$EXPECTED_REDIRECT_URI"
export SOCIAL_YOUTUBE_OAUTH_STATE_SECRET="$oauth_state_secret"
export SOCIAL_YOUTUBE_ACTIVATION_GATE_ENABLED=true
export SOCIAL_YOUTUBE_ACTIVATION_ENABLED_AT="$enabled_at"
export SOCIAL_YOUTUBE_ACTIVATION_EXPIRES_AT="$expires_at"

exec "$ROOT/scripts/dev/start_local.sh"

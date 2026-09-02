#!/usr/bin/env bash

# Shared, source-only environment preparation for isolated platform canaries.
# OAuth application values remain in ignored files and are exported only to
# the child processes that need them.

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "Source platform_canary_env.sh from a canary command." >&2
  exit 2
fi

prepare_platform_canary_env() {
  local root="${1:?Repository root is required}"
  local local_state="$root/.local"
  local credential_file="${SOCIAL_YOUTUBE_DEV_CLIENT_FILE:-$root/.secrets/socialmedia/youtube-dev-client.json}"
  local x_credential_file="${SOCIAL_X_DEV_APP_FILE:-$root/.secrets/socialmedia/x-dev-oauth.json}"
  local linkedin_credential_file="${SOCIAL_LINKEDIN_DEV_APP_FILE:-$root/.secrets/socialmedia/linkedin-dev-oauth.json}"
  local oauth_state_file="$local_state/youtube-canary-oauth-state.secret"
  local vault_key_file="$local_state/youtube-canary-vault.key"
  local x_oauth_state_file="$local_state/x-canary-oauth-state.secret"
  local linkedin_oauth_state_file="$local_state/linkedin-canary-oauth-state.secret"
  local expected_redirect_uri="http://localhost:8126/api/social/youtube/oauth/callback"
  local x_expected_redirect_uri="http://localhost:8126/api/social/x/oauth/callback"
  local linkedin_expected_redirect_uri="http://localhost:8126/api/social/linkedin/oauth/callback"
  local command_name

  for command_name in jq openssl; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
      echo "$command_name is required for the platform canary runtime." >&2
      return 1
    fi
  done

  if [[ ! -f "$credential_file" ]]; then
    echo "YouTube development OAuth credential is missing: $credential_file" >&2
    return 1
  fi
  if [[ "$(stat -c '%a' "$credential_file")" != "600" ]]; then
    echo "YouTube development OAuth credential must have mode 0600." >&2
    return 1
  fi
  if ! jq -e --arg redirect_uri "$expected_redirect_uri" '
    (.web.project_id == "first-dex-ela")
    and (.web.client_id | type == "string" and endswith(".apps.googleusercontent.com"))
    and (.web.client_secret | type == "string" and length > 20)
    and (.web.redirect_uris == [$redirect_uri])
  ' "$credential_file" >/dev/null; then
    echo "YouTube development OAuth credential does not match the approved contract." >&2
    return 1
  fi

  mkdir -p "$local_state"
  chmod 700 "$local_state"
  umask 077
  if [[ ! -f "$oauth_state_file" ]]; then
    openssl rand -base64 48 >"$oauth_state_file"
  fi
  if [[ ! -f "$vault_key_file" ]]; then
    openssl rand -base64 32 >"$vault_key_file"
  fi
  chmod 600 "$oauth_state_file" "$vault_key_file"

  if [[ -f "$x_credential_file" ]]; then
    if [[ "$(stat -c '%a' "$x_credential_file")" != "600" ]]; then
      echo "X development OAuth credential must have mode 0600." >&2
      return 1
    fi
    if ! jq -e --arg redirect_uri "$x_expected_redirect_uri" '
      (.web.client_id | type == "string" and length > 5)
      and (.web.client_secret | type == "string" and length > 10)
      and (.web.redirect_uris == [$redirect_uri])
    ' "$x_credential_file" >/dev/null; then
      echo "X development OAuth credential does not match the approved contract." >&2
      return 1
    fi
    if [[ ! -f "$x_oauth_state_file" ]]; then
      openssl rand -base64 48 >"$x_oauth_state_file"
    fi
    chmod 600 "$x_oauth_state_file"
  fi

  if [[ -f "$linkedin_credential_file" ]]; then
    if [[ "$(stat -c '%a' "$linkedin_credential_file")" != "600" ]]; then
      echo "LinkedIn development OAuth credential must have mode 0600." >&2
      return 1
    fi
    if ! jq -e --arg redirect_uri "$linkedin_expected_redirect_uri" '
      (.web.client_id | type == "string" and length > 5)
      and (.web.client_secret | type == "string" and length > 10)
      and (.web.redirect_uris == [$redirect_uri])
    ' "$linkedin_credential_file" >/dev/null; then
      echo "LinkedIn development OAuth credential does not match the approved contract." >&2
      return 1
    fi
    if [[ ! -f "$linkedin_oauth_state_file" ]]; then
      openssl rand -base64 48 >"$linkedin_oauth_state_file"
    fi
    chmod 600 "$linkedin_oauth_state_file"
  fi

  local youtube_client_id
  local youtube_client_secret
  local oauth_state_secret
  local vault_key
  local credential_keyring
  local enabled_at
  local expires_at
  youtube_client_id="$(jq -er '.web.client_id' "$credential_file")"
  youtube_client_secret="$(jq -er '.web.client_secret' "$credential_file")"
  oauth_state_secret="$(tr -d '\r\n' <"$oauth_state_file")"
  vault_key="$(tr -d '\r\n' <"$vault_key_file")"
  credential_keyring="$(jq -cn --arg key "$vault_key" '{"youtube-dev-key": $key}')"
  enabled_at="$(date -u -d '5 minutes ago' '+%Y-%m-%dT%H:%M:%SZ')"
  expires_at="$(date -u -d '12 hours' '+%Y-%m-%dT%H:%M:%SZ')"

  export SOCIAL_LOCAL_DB_ENV_FILE="$root/.local/platform-expansion-db.env"
  export SOCIAL_LOCAL_DB_CONTAINER="social-media-v2-platforms-postgres"
  export SOCIAL_LOCAL_DB_VOLUME="social_media_v2_platforms_data"
  export SOCIAL_LOCAL_DB_PORT="56432"
  export SOCIAL_LOCAL_DB_NAME="social_media_v2_platforms_dev"
  export SOCIAL_LOCAL_API_PORT="8127"
  export SOCIAL_LOCAL_FRONTEND_PORT="8126"
  export SOCIAL_LOCAL_ACTIVATION_PROFILE="platform_canary"
  export VITE_LOCAL_PREVIEW_PLATFORMS="youtube,x,linkedin"
  export SOCIAL_VAULT_ENABLED=true
  export SOCIAL_WORKER_SCHEDULE_ENABLED=false
  export SOCIAL_CREDENTIAL_ACTIVE_KEY_ID="youtube-dev-key"
  export SOCIAL_CREDENTIAL_KEYRING_JSON="$credential_keyring"
  export SOCIAL_YOUTUBE_OAUTH_APP_ID="$youtube_client_id"
  export SOCIAL_YOUTUBE_OAUTH_APP_SECRET="$youtube_client_secret"
  export SOCIAL_YOUTUBE_ACCOUNT_ENABLED=true
  export SOCIAL_YOUTUBE_ACCOUNT_OAUTH_MODE="manual_intent_only"
  export SOCIAL_YOUTUBE_COLLECTION_ENABLED=false
  export SOCIAL_YOUTUBE_REDIRECT_URI="$expected_redirect_uri"
  export SOCIAL_YOUTUBE_OAUTH_STATE_SECRET="$oauth_state_secret"
  export SOCIAL_YOUTUBE_ACTIVATION_GATE_ENABLED=true
  export SOCIAL_YOUTUBE_ACTIVATION_ENABLED_AT="$enabled_at"
  export SOCIAL_YOUTUBE_ACTIVATION_EXPIRES_AT="$expires_at"

  export SOCIAL_X_ACCOUNT_ENABLED=false
  export SOCIAL_X_ACCOUNT_OAUTH_MODE=disabled
  export SOCIAL_X_COLLECTION_ENABLED=false
  export SOCIAL_X_ACTIVATION_GATE_ENABLED=false
  if [[ -f "$x_credential_file" ]]; then
    export SOCIAL_X_OAUTH_APP_ID
    export SOCIAL_X_OAUTH_APP_SECRET
    export SOCIAL_X_OAUTH_APP_ID="$(jq -er '.web.client_id' "$x_credential_file")"
    export SOCIAL_X_OAUTH_APP_SECRET="$(jq -er '.web.client_secret' "$x_credential_file")"
    export SOCIAL_X_ACCOUNT_ENABLED=true
    export SOCIAL_X_ACCOUNT_OAUTH_MODE="manual_intent_only"
    export SOCIAL_X_COLLECTION_ENABLED=true
    export SOCIAL_X_REDIRECT_URI="$x_expected_redirect_uri"
    export SOCIAL_X_OAUTH_STATE_SECRET="$(tr -d '\r\n' <"$x_oauth_state_file")"
    export SOCIAL_X_ACTIVATION_GATE_ENABLED=true
    export SOCIAL_X_ACTIVATION_ENABLED_AT="$enabled_at"
    export SOCIAL_X_ACTIVATION_EXPIRES_AT="$expires_at"
  else
    echo "X OAuth remains disabled until this mode-0600 file exists: $x_credential_file" >&2
  fi

  export SOCIAL_LINKEDIN_ACCOUNT_ENABLED=false
  export SOCIAL_LINKEDIN_ACCOUNT_OAUTH_MODE=disabled
  export SOCIAL_LINKEDIN_COLLECTION_ENABLED=false
  export SOCIAL_LINKEDIN_ACTIVATION_GATE_ENABLED=false
  if [[ -f "$linkedin_credential_file" ]]; then
    export SOCIAL_LINKEDIN_OAUTH_APP_ID
    export SOCIAL_LINKEDIN_OAUTH_APP_SECRET
    export SOCIAL_LINKEDIN_OAUTH_APP_ID="$(jq -er '.web.client_id' "$linkedin_credential_file")"
    export SOCIAL_LINKEDIN_OAUTH_APP_SECRET="$(jq -er '.web.client_secret' "$linkedin_credential_file")"
    export SOCIAL_LINKEDIN_ACCOUNT_ENABLED=true
    export SOCIAL_LINKEDIN_ACCOUNT_OAUTH_MODE="manual_intent_only"
    export SOCIAL_LINKEDIN_COLLECTION_ENABLED=true
    export SOCIAL_LINKEDIN_REDIRECT_URI="$linkedin_expected_redirect_uri"
    export SOCIAL_LINKEDIN_OAUTH_STATE_SECRET="$(tr -d '\r\n' <"$linkedin_oauth_state_file")"
    export SOCIAL_LINKEDIN_ACTIVATION_GATE_ENABLED=true
    export SOCIAL_LINKEDIN_ACTIVATION_ENABLED_AT="$enabled_at"
    export SOCIAL_LINKEDIN_ACTIVATION_EXPIRES_AT="$expires_at"
  else
    echo "LinkedIn OAuth remains disabled until this mode-0600 file exists: $linkedin_credential_file" >&2
  fi

  # The canary must never inherit unrelated live provider or AI switches from
  # the operator's shell.
  export SOCIAL_META_ACCOUNT_ENABLED=false
  export SOCIAL_META_ACCOUNT_OAUTH_MODE=disabled
  export SOCIAL_META_COLLECTION_ENABLED=false
  export SOCIAL_META_ACTIVATION_GATE_ENABLED=false
  export SOCIAL_TIKTOK_ACCOUNT_ENABLED=false
  export SOCIAL_TIKTOK_ACCOUNT_OAUTH_MODE=disabled
  export SOCIAL_TIKTOK_COLLECTION_ENABLED=false
  export SOCIAL_TIKTOK_ADVERTISER_ENABLED=false
  export SOCIAL_TIKTOK_ACTIVATION_GATE_ENABLED=false
  export SOCIAL_AI_SUMMARY_ENABLED=false
}

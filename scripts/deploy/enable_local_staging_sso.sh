#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="/etc/social-media-v2/production.env"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this staging transition with sudo." >&2
  exit 1
fi
if [[ ! -f "$ENV_FILE" || ! -d /opt/social-media-v2 || ! -d /var/lib/social-media-v2 ]]; then
  echo "V2 local staging runtime is not installed." >&2
  exit 1
fi
if ! grep -qE '^SOCIAL_DB_URL=.*social_media_v2_staging$' "$ENV_FILE"; then
  echo "Refusing to enable staging writes outside the dedicated V2 staging database." >&2
  exit 1
fi

systemctl disable --now social-media-v2-collection.timer >/dev/null 2>&1 || true
systemctl stop social-media-v2-collection.service >/dev/null 2>&1 || true

if grep -qx 'SOCIAL_SSO_HS256_SECRET=' "$ENV_FILE"; then
  SSO_SECRET="$(openssl rand -hex 48)"
  sed -i "s|^SOCIAL_SSO_HS256_SECRET=$|SOCIAL_SSO_HS256_SECRET=${SSO_SECRET}|" "$ENV_FILE"
fi
sed -i 's|^APP_ENV=.*|APP_ENV=staging|' "$ENV_FILE"
sed -i 's|^SOCIAL_RUNTIME_MODE=.*|SOCIAL_RUNTIME_MODE=staging|' "$ENV_FILE"
sed -i 's|^SOCIAL_WRITES_ENABLED=.*|SOCIAL_WRITES_ENABLED=true|' "$ENV_FILE"

for required in \
  'SOCIAL_SESSION_COOKIE_SECURE=true' \
  'SOCIAL_WORKER_SCHEDULE_ENABLED=false' \
  'SOCIAL_META_ACCOUNT_ENABLED=false' \
  'SOCIAL_META_COLLECTION_ENABLED=false' \
  'SOCIAL_TIKTOK_ACCOUNT_ENABLED=false' \
  'SOCIAL_TIKTOK_COLLECTION_ENABLED=false'; do
  if ! grep -qx "$required" "$ENV_FILE"; then
    echo "Required staging safety invariant is missing: ${required%%=*}" >&2
    exit 1
  fi
done

install -m 0644 "$ROOT/deploy/systemd/social-media-v2-api.service" \
  /etc/systemd/system/social-media-v2-api.service
systemctl daemon-reload
systemctl restart social-media-v2-api.service

for attempt in $(seq 1 40); do
  if curl --fail --silent http://127.0.0.1:8026/api/health >/dev/null; then
    break
  fi
  if [[ "$attempt" -eq 40 ]]; then
    echo "V2 staging API did not become ready after the SSO transition." >&2
    exit 1
  fi
  sleep 0.25
done

echo "V2 local staging SSO mode enabled. Provider collection and schedule remain disabled."

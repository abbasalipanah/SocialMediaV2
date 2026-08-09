#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERVICE_USER="social-media-v2"
SERVICE_GROUP="social-media-v2"
DB_ROLE="social_media_v2_staging"
DB_NAME="social_media_v2_staging"
INSTALL_ROOT="/opt/social-media-v2"
CONFIG_ROOT="/etc/social-media-v2"
DATA_ROOT="/var/lib/social-media-v2"
RELEASE_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_ROOT="$INSTALL_ROOT/releases/$RELEASE_ID"
BUILD_ROOT="$(mktemp -d /tmp/social-media-v2-install.XXXXXX)"

cleanup_build() {
  if [[ "$BUILD_ROOT" == /tmp/social-media-v2-install.* && -d "$BUILD_ROOT" ]]; then
    rm -rf -- "$BUILD_ROOT"
  fi
}
trap cleanup_build EXIT INT TERM

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi
for target in "$INSTALL_ROOT" "$CONFIG_ROOT/production.env" "$DATA_ROOT"; do
  if [[ -e "$target" ]]; then
    echo "Refusing to overwrite existing V2 staging target: $target" >&2
    exit 1
  fi
done
if ss -ltn | grep -qE ':8026\b'; then
  echo "Refusing to install while port 8026 is in use." >&2
  exit 1
fi
if runuser -u postgres -- psql -Atqc "SELECT 1 FROM pg_roles WHERE rolname='$DB_ROLE'" | grep -qx 1; then
  echo "Refusing to overwrite existing PostgreSQL role: $DB_ROLE" >&2
  exit 1
fi
if runuser -u postgres -- psql -Atqc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -qx 1; then
  echo "Refusing to overwrite existing PostgreSQL database: $DB_NAME" >&2
  exit 1
fi

if ! getent group "$SERVICE_GROUP" >/dev/null; then
  groupadd --system "$SERVICE_GROUP"
fi
if ! getent passwd "$SERVICE_USER" >/dev/null; then
  useradd --system --gid "$SERVICE_GROUP" --home-dir "$DATA_ROOT" \
    --shell /usr/sbin/nologin "$SERVICE_USER"
fi

install -d -m 0755 "$INSTALL_ROOT/releases" "$RELEASE_ROOT"
install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_GROUP" \
  "$DATA_ROOT" "$DATA_ROOT/media" "$DATA_ROOT/nginx" \
  "$DATA_ROOT/nginx/client_temp" "$DATA_ROOT/nginx/proxy_temp"
install -d -m 0750 -o root -g "$SERVICE_GROUP" "$CONFIG_ROOT"

mkdir -p "$BUILD_ROOT/backend" "$BUILD_ROOT/frontend"
rsync -a \
  --exclude=.venv \
  --exclude=build \
  --exclude=dist \
  --exclude='*.egg-info' \
  --exclude=__pycache__ \
  --exclude=.pytest_cache \
  --exclude=.ruff_cache \
  --exclude=.mypy_cache \
  --exclude=tests \
  "$ROOT/backend/" "$BUILD_ROOT/backend/"
rsync -a \
  --exclude=node_modules \
  --exclude=dist \
  --exclude=test-results \
  --exclude=playwright-report \
  "$ROOT/frontend/" "$BUILD_ROOT/frontend/"

(
  cd "$BUILD_ROOT/frontend"
  npm ci --ignore-scripts --no-audit --no-fund
  npm run build
)

mkdir -p "$RELEASE_ROOT/backend" "$RELEASE_ROOT/frontend/dist"
rsync -a "$BUILD_ROOT/backend/" "$RELEASE_ROOT/backend/"
rsync -a "$BUILD_ROOT/frontend/dist/" "$RELEASE_ROOT/frontend/dist/"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$RELEASE_ROOT"

runuser -u "$SERVICE_USER" -- python3 -m venv "$RELEASE_ROOT/backend/.venv"
runuser -u "$SERVICE_USER" -- "$RELEASE_ROOT/backend/.venv/bin/python" -m pip install \
  --disable-pip-version-check --require-hashes -r "$RELEASE_ROOT/backend/requirements.lock"

DB_PASSWORD="$(openssl rand -hex 32)"
printf "CREATE ROLE %s LOGIN PASSWORD '%s';\nCREATE DATABASE %s OWNER %s;\n" \
  "$DB_ROLE" "$DB_PASSWORD" "$DB_NAME" "$DB_ROLE" \
  | runuser -u postgres -- psql -v ON_ERROR_STOP=1 >/dev/null

install -m 0640 -o root -g "$SERVICE_GROUP" \
  "$ROOT/deploy/env/social-media-v2.production.env.example" "$CONFIG_ROOT/production.env"
sed -i \
  "s|^SOCIAL_DB_URL=.*|SOCIAL_DB_URL=postgresql+psycopg://${DB_ROLE}:${DB_PASSWORD}@127.0.0.1/${DB_NAME}|" \
  "$CONFIG_ROOT/production.env"

ln -s "releases/$RELEASE_ID/backend" "$INSTALL_ROOT/backend"
ln -s "releases/$RELEASE_ID/frontend" "$INSTALL_ROOT/frontend"

install -m 0644 "$ROOT/deploy/systemd/social-media-v2-api.service" \
  /etc/systemd/system/social-media-v2-api.service
install -m 0644 "$ROOT/deploy/systemd/social-media-v2-migrate.service" \
  /etc/systemd/system/social-media-v2-migrate.service
install -m 0644 "$ROOT/deploy/systemd/social-media-v2-collection.service" \
  /etc/systemd/system/social-media-v2-collection.service
install -m 0644 "$ROOT/deploy/systemd/social-media-v2-collection.timer" \
  /etc/systemd/system/social-media-v2-collection.timer
install -m 0644 "$ROOT/deploy/systemd/social-media-v2-web.service" \
  /etc/systemd/system/social-media-v2-web.service
install -m 0640 -o root -g "$SERVICE_GROUP" \
  "$ROOT/deploy/nginx/social-media-v2-staging-loopback.conf" \
  "$CONFIG_ROOT/nginx-staging.conf"

systemctl daemon-reload
systemctl start social-media-v2-migrate.service
systemctl enable --now social-media-v2-api.service
systemctl enable --now social-media-v2-web.service

echo "Social Media V2 local staging installed: $RELEASE_ROOT"
echo "API: http://127.0.0.1:8026"
echo "Web: http://127.0.0.1:3026"
echo "Collection service/timer were installed but remain disabled."

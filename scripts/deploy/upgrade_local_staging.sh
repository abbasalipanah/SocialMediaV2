#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERVICE_USER="social-media-v2"
SERVICE_GROUP="social-media-v2"
INSTALL_ROOT="/opt/social-media-v2"
ENV_FILE="/etc/social-media-v2/production.env"
RELEASE_ID="${SOCIAL_MEDIA_V2_RELEASE_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
RELEASE_ROOT="$INSTALL_ROOT/releases/$RELEASE_ID"
BUILD_ROOT="$(mktemp -d /tmp/social-media-v2-upgrade.XXXXXX)"
OLD_BACKEND=""
OLD_FRONTEND=""
RELEASE_CREATED=false
SWITCHED=false

cleanup_build() {
  if [[ "$BUILD_ROOT" == /tmp/social-media-v2-upgrade.* && -d "$BUILD_ROOT" ]]; then
    rm -rf -- "$BUILD_ROOT"
  fi
}

restore_symlinks() {
  if [[ "$SWITCHED" != true ]]; then
    return
  fi
  ln -sfn "$OLD_BACKEND" "$INSTALL_ROOT/.backend.rollback"
  ln -sfn "$OLD_FRONTEND" "$INSTALL_ROOT/.frontend.rollback"
  mv -Tf "$INSTALL_ROOT/.backend.rollback" "$INSTALL_ROOT/backend"
  mv -Tf "$INSTALL_ROOT/.frontend.rollback" "$INSTALL_ROOT/frontend"
  systemctl restart social-media-v2-api.service social-media-v2-web.service || true
  echo "Upgrade failed; V2 runtime symlinks were restored." >&2
}

cleanup_failed_release() {
  if [[ "$RELEASE_CREATED" != true ]]; then
    return
  fi
  current_backend="$(readlink -f "$INSTALL_ROOT/backend" 2>/dev/null || true)"
  current_frontend="$(readlink -f "$INSTALL_ROOT/frontend" 2>/dev/null || true)"
  if [[ "$current_backend" == "$RELEASE_ROOT/backend" \
    || "$current_frontend" == "$RELEASE_ROOT/frontend" ]]; then
    echo "Refusing to clean a release still referenced by an active symlink." >&2
    return
  fi
  case "$RELEASE_ROOT" in
    "$INSTALL_ROOT"/releases/*) rm -rf -- "$RELEASE_ROOT" ;;
    *) echo "Refusing to clean unexpected release path: $RELEASE_ROOT" >&2 ;;
  esac
}

on_exit() {
  exit_code=$?
  if [[ "$exit_code" -ne 0 ]]; then
    restore_symlinks
    cleanup_failed_release
  fi
  cleanup_build
  exit "$exit_code"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run this V2 upgrade with sudo." >&2
  exit 1
fi
for required in \
  "$INSTALL_ROOT/releases" \
  "$INSTALL_ROOT/backend" \
  "$INSTALL_ROOT/frontend" \
  "$ENV_FILE"; do
  if [[ ! -e "$required" ]]; then
    echo "Existing V2 staging target is missing: $required" >&2
    exit 1
  fi
done
if [[ -e "$RELEASE_ROOT" ]]; then
  echo "Refusing to overwrite an existing V2 release: $RELEASE_ROOT" >&2
  exit 1
fi
if ! getent passwd "$SERVICE_USER" >/dev/null || ! getent group "$SERVICE_GROUP" >/dev/null; then
  echo "V2 service account is missing." >&2
  exit 1
fi
if ! grep -qE '^SOCIAL_DB_URL=.*social_media_v2_staging$' "$ENV_FILE"; then
  echo "Refusing to upgrade outside the dedicated V2 staging database." >&2
  exit 1
fi
if systemctl is-enabled --quiet social-media-v2-collection.timer; then
  echo "Refusing to upgrade while the V2 collection timer is enabled." >&2
  exit 1
fi

OLD_BACKEND="$(readlink -f "$INSTALL_ROOT/backend")"
OLD_FRONTEND="$(readlink -f "$INSTALL_ROOT/frontend")"
case "$OLD_BACKEND" in
  "$INSTALL_ROOT"/releases/*/backend) ;;
  *) echo "Unexpected V2 backend symlink target: $OLD_BACKEND" >&2; exit 1 ;;
esac
case "$OLD_FRONTEND" in
  "$INSTALL_ROOT"/releases/*/frontend) ;;
  *) echo "Unexpected V2 frontend symlink target: $OLD_FRONTEND" >&2; exit 1 ;;
esac

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
  npm_config_cache="$BUILD_ROOT/npm-cache" npm ci --ignore-scripts --no-audit --no-fund
  npm run build
)

install -d -m 0755 "$RELEASE_ROOT/backend" "$RELEASE_ROOT/frontend/dist"
RELEASE_CREATED=true
rsync -a "$BUILD_ROOT/backend/" "$RELEASE_ROOT/backend/"
rsync -a "$BUILD_ROOT/frontend/dist/" "$RELEASE_ROOT/frontend/dist/"
chown -R "$SERVICE_USER:$SERVICE_GROUP" "$RELEASE_ROOT"

runuser -u "$SERVICE_USER" -- python3 -m venv "$RELEASE_ROOT/backend/.venv"
runuser -u "$SERVICE_USER" -- "$RELEASE_ROOT/backend/.venv/bin/python" -m pip install \
  --disable-pip-version-check --no-cache-dir --require-hashes \
  -r "$RELEASE_ROOT/backend/requirements.lock"
runuser -u "$SERVICE_USER" -- bash -c \
  "set -a; source '$ENV_FILE'; set +a; cd '$RELEASE_ROOT/backend'; .venv/bin/python -c 'from app.main import app; assert app'"

ln -sfn "releases/$RELEASE_ID/backend" "$INSTALL_ROOT/.backend.next"
ln -sfn "releases/$RELEASE_ID/frontend" "$INSTALL_ROOT/.frontend.next"
mv -Tf "$INSTALL_ROOT/.backend.next" "$INSTALL_ROOT/backend"
mv -Tf "$INSTALL_ROOT/.frontend.next" "$INSTALL_ROOT/frontend"
SWITCHED=true

systemctl start social-media-v2-migrate.service
systemctl restart social-media-v2-api.service social-media-v2-web.service

for attempt in $(seq 1 60); do
  if curl --fail --silent http://127.0.0.1:8026/api/health >/dev/null \
    && curl --fail --silent http://127.0.0.1:8026/api/operations/readiness >/dev/null \
    && curl --fail --silent http://127.0.0.1:3026/ >/dev/null; then
    break
  fi
  if [[ "$attempt" -eq 60 ]]; then
    echo "V2 staging did not become healthy after the release switch." >&2
    exit 1
  fi
  sleep 0.5
done

SWITCHED=false
RELEASE_CREATED=false
echo "Social Media V2 local staging upgraded: $RELEASE_ROOT"
echo "Previous backend: $OLD_BACKEND"
echo "Previous frontend: $OLD_FRONTEND"

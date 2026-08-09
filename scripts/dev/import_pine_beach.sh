#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SOURCE_ENV="/home/api/colab_scripts/SocialMedia/backend/.env"
RUNTIME_ENV="$ROOT/.local/social-media-v2-db.env"

"$ROOT/scripts/dev/ensure_local_db.sh"

set -a
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
set +a

APP_ENV=development \
SOCIAL_RUNTIME_MODE=development \
SOCIAL_WRITES_ENABLED=false \
SOCIAL_DB_REQUIRE_TLS=false \
"$ROOT/backend/.venv/bin/python" "$ROOT/backend/scripts/import_legacy_brand.py" \
  --source-env "$SOURCE_ENV" \
  --source-media-root /home/api/colab_scripts/SocialMedia/backend/media \
  --target-media-root "$ROOT/.local/media" \
  --brand-slug pine-beach-belek

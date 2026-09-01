#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
PYTHON="$ROOT/backend/.venv/bin/python"

"$ROOT/scripts/source_write_guard.sh"
"$ROOT/scripts/quality/fase6_dashboard_operations_check.sh"

"$PYTHON" "$ROOT/scripts/quality/export_openapi.py"
(
  cd "$FRONTEND"
  npm ci
  npm run generate:api
  npx playwright install chromium
  npm run typecheck
  npm test
  npm run test:e2e
  npm run build
  npm audit --audit-level=high
)

if grep -REiw "google ads|google analytics|ga4|campaign|currency|spend|notification dot" \
  "$FRONTEND/src/app" \
  "$FRONTEND/src/auth" \
  "$FRONTEND/src/features" \
  "$FRONTEND/src/layout" \
  "$FRONTEND/src/routes" \
  "$FRONTEND/src/ui"; then
  echo "Forbidden paid-media or fake-notification UI leaked into the Social shell." >&2
  exit 1
fi

if grep -REi "serviceWorker|service-worker|navigator\.serviceWorker|workbox" \
  "$FRONTEND/src" "$FRONTEND/vite.config.ts"; then
  echo "PWA/service-worker code is forbidden in the initial frontend." >&2
  exit 1
fi

grep -q 'env.VITE_DEV_SERVER_PORT || "3010"' "$FRONTEND/vite.config.ts"
grep -q 'port: devServerPort' "$FRONTEND/vite.config.ts"
grep -q 'strictPort: true' "$FRONTEND/vite.config.ts"
grep -q '@media (max-width: 1023px)' "$FRONTEND/src/styles.css"

python3 "$ROOT/scripts/quality/check_secret_leaks.py"
python3 "$ROOT/scripts/quality/check_canonical_vocabulary.py"
"$ROOT/scripts/source_write_guard.sh"
echo "OK: Faz 7 frontend shell certification passed."

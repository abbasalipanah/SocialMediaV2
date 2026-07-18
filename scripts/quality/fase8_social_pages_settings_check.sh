#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND="$ROOT/frontend"
PYTHON="$ROOT/backend/.venv/bin/python"

"$ROOT/scripts/source_write_guard.sh"
"$ROOT/scripts/quality/fase7_frontend_shell_check.sh"

(
  cd "$ROOT/backend"
  "$PYTHON" -m pytest -q \
    tests/test_sso_contract.py \
    tests/test_phase6_dashboard_api.py \
    tests/test_command_query_boundary.py
)

python3 - "$ROOT" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
schema = json.loads((root / "docs/contracts/social-media-v2-openapi.json").read_text())
activation = schema["paths"]["/api/settings/tiktok/activation-readiness"]
assert set(activation) == {"get"}, "Activation readiness must remain GET-only"

routes = (root / "frontend/src/routes/AppRoutes.tsx").read_text()
assert 'path="stories"' not in routes
assert 'path="settings"' in routes and 'path="tiktok/connect"' in routes

instagram = (root / "frontend/src/features/dashboard/catalog.ts").read_text()
for required in ('{ id: "stories", label: "Stories" }', 'facebook: [', 'instagram: [', 'tiktok: ['):
    assert required in instagram

settings = (root / "frontend/src/features/settings/SetupDrawer.tsx").read_text()
assert 'const PLATFORMS: Platform[] = ["facebook", "instagram", "tiktok"]' in settings
PY

if grep -REiw "google ads|google analytics|ga4|campaign|currency|spend" \
  "$FRONTEND/src/features" "$FRONTEND/src/ui"; then
  echo "Forbidden paid-media vocabulary leaked into Faz 8 product surfaces." >&2
  exit 1
fi

python3 "$ROOT/scripts/quality/check_secret_leaks.py"
python3 "$ROOT/scripts/quality/check_canonical_vocabulary.py"
"$ROOT/scripts/source_write_guard.sh"
echo "OK: Faz 8 social pages and Settings certification passed."

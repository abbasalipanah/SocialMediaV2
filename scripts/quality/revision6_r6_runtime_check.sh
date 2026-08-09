#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="$BACKEND/.venv/bin/python"

"$ROOT/scripts/source_write_guard.sh"
"$PYTHON" "$ROOT/scripts/quality/revision6_r6_runtime.py"

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest -q
)

"$PYTHON" "$ROOT/scripts/quality/export_openapi.py"

(
  cd "$FRONTEND"
  npm run generate:api
  npm test -- --run
  npm run build
)

"$PYTHON" "$ROOT/scripts/quality/revision6_r6_runtime.py"
"$ROOT/scripts/source_write_guard.sh"

echo "OK: Revision 6 R6 standalone runtime and SSO-only certification passed."

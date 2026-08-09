#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$ROOT/backend/.venv/bin/python"

"$ROOT/scripts/source_write_guard.sh"
"$PYTHON" "$ROOT/scripts/quality/revision6_r1_inventory.py"
"$PYTHON" "$ROOT/scripts/quality/revision6_r5_frontend.py"

(
  cd "$ROOT/backend"
  "$PYTHON" -m ruff check app/application/queries/reporting_range.py tests/test_reporting_range.py
  "$PYTHON" -m pytest -q tests/test_reporting_range.py tests/test_phase6_dashboard_api.py
)

(
  cd "$ROOT/frontend"
  npm test
  npm run build
  npm run test:e2e
)

"$ROOT/scripts/source_write_guard.sh"
echo "OK: Revision 6 R5 frontend parity certification passed."

#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="${PYTHON:-python3}"

python3 "$ROOT/scripts/quality/fase1_smoke_check.py"

PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/social-media-v2-ci-pycache" \
  "$PYTHON" -m compileall -q "$BACKEND/app"

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest
  "$PYTHON" -m build --wheel --no-isolation
)

(
  cd "$FRONTEND"
  npm ci --ignore-scripts --no-audit --no-fund
  npm run build
)

python3 "$ROOT/scripts/quality/check_canonical_vocabulary.py"

echo "OK: downstream CI verification passed."

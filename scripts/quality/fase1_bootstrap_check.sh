#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PYTHON="$BACKEND/.venv/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Missing backend virtual environment: $BACKEND/.venv" >&2
  exit 1
fi

"$ROOT/scripts/source_write_guard.sh"
python3 "$ROOT/scripts/quality/fase1_smoke_check.py"

PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/social-media-v2-pycache" \
  "$PYTHON" -m compileall -q "$BACKEND/app"

(
  cd "$BACKEND"
  "$PYTHON" -m ruff check app tests
  "$PYTHON" -m pytest
  rm -rf build dist
  "$PYTHON" -m build --wheel --no-isolation
)

(
  cd "$FRONTEND"
  npm ci --ignore-scripts --no-audit --no-fund
  npm run build
)

python3 "$ROOT/scripts/quality/check_canonical_vocabulary.py"
"$ROOT/scripts/source_write_guard.sh"
echo "OK: Faz 1 certification passed."

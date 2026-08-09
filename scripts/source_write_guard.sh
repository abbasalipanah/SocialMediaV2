#!/usr/bin/env bash

set -euo pipefail

ROOT="/home/api/colab_scripts/SocialMediadownstream"
BASELINE_TOOL="$ROOT/scripts/quality/source_baseline.py"

READONLY_PROJECTS=(
  "/home/api/colab_scripts/SocialMedia"
  "/home/api/colab_scripts/Accumulate"
  "/home/api/colab_scripts/performance_marketing"
)

usage() {
  cat <<'USAGE'
Usage:
  source_write_guard.sh [PATH ...]

Checks:
- Any explicit PATH inside a protected source project is rejected; other paths
  outside the downstream root are warned.
- Branch, HEAD, origin, status, tracked binary diff, exact untracked inventory and
  artifact-excluded content manifests for all immutable source projects must match
  the approved Revision 6 baseline.

To verify baseline state only:
  source_write_guard.sh
USAGE
}

is_within_root() {
  local candidate=$1
  [[ "$candidate" == "$ROOT" || "$candidate" == "$ROOT/"* ]]
}

is_locked_project() {
  local candidate=$1
  local project
  for project in "${READONLY_PROJECTS[@]}"; do
    if [[ "$candidate" == "$project" || "$candidate" == "$project/"* ]]; then
      return 0
    fi
  done
  return 1
}

main() {
  if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage
    return 0
  fi

  local p rel
  for p in "${@:1}"; do
    rel=$(readlink -f "$p")
    if ! is_within_root "$rel"; then
      if is_locked_project "$rel"; then
        echo "FORBIDDEN: write target is protected source project: $rel"
        echo "Downstream writes to SocialMedia / Accumulate / performance_marketing are disallowed."
        return 1
      fi
      echo "WARNING: path is outside downstream root: $rel"
    fi
  done

  python3 "$BASELINE_TOOL" verify
}

main "$@"

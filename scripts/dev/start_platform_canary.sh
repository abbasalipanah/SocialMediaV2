#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=platform_canary_env.sh
source "$ROOT/scripts/dev/platform_canary_env.sh"
prepare_platform_canary_env "$ROOT"

exec "$ROOT/scripts/dev/start_local.sh"

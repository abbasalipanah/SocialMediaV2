#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=youtube_canary_env.sh
source "$ROOT/scripts/dev/youtube_canary_env.sh"
prepare_youtube_canary_env "$ROOT"

exec "$ROOT/scripts/dev/start_local.sh"

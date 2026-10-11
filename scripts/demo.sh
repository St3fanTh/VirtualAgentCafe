#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/environment.sh
export VAC_MODE="${1:-${VAC_MODE:-demo}}"
case "$VAC_MODE" in
  demo|codex) ;;
  *) echo 'Usage: scripts/demo.sh [demo|codex]' >&2; exit 2 ;;
esac
exec python3 -m uvicorn virtual_agent_cafe.main:app \
  --host "${VAC_BIND_HOST:-127.0.0.1}" --port "${VAC_PORT:-8000}" --no-access-log

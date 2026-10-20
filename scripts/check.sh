#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/environment.sh
PYTHON="${PYTHON:-python3}"
check_log=$(mktemp)
trap 'rm -f "$check_log"' EXIT
check_godot() {
  godot "$@" 2>&1 | tee "$check_log"
  if rg -q 'SCRIPT ERROR|Parse Error|ERROR:' "$check_log"; then
    echo 'Godot reported errors' >&2
    exit 1
  fi
}

run_stage() {
  case "$1" in
    lint)
      ruff check backend scripts
      ruff format --check backend scripts
      ;;
    pytest)
      "$PYTHON" -m pytest backend/tests -q
      ;;
    godot-import)
      check_godot --headless --path game --editor --quit-after 30
      ;;
    godot-states)
      check_godot --headless --path game --script res://tests/test_states.gd
      ;;
    godot-headless)
      check_godot --headless --path game --quit-after 120
      ;;
    websocket-smoke)
      "$PYTHON" scripts/game_smoke.py
      ;;
    *)
      echo "Unknown check stage: $1" >&2
      return 2
      ;;
  esac
}

stages=(lint pytest godot-import godot-states godot-headless websocket-smoke)
if [[ "${1:-all}" == "all" ]]; then
  for stage in "${stages[@]}"; do
    echo "=== $stage ==="
    run_stage "$stage"
  done
else
  run_stage "$1"
fi

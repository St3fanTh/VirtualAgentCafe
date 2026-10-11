#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$PWD/.venv/bin:$PATH"
PYTHON="${PYTHON:-python3}"
ruff check backend scripts
ruff format --check backend scripts
"$PYTHON" -m pytest backend/tests -q
check_log=$(mktemp)
trap 'rm -f "$check_log"' EXIT
check_godot() {
  godot "$@" 2>&1 | tee "$check_log"
  if rg -q 'SCRIPT ERROR|Parse Error|ERROR:' "$check_log"; then
    echo 'Godot reported errors' >&2
    exit 1
  fi
}
check_godot --headless --path game --editor --quit-after 30
check_godot --headless --path game --script res://tests/test_states.gd
check_godot --headless --path game --quit-after 120
"$PYTHON" scripts/game_smoke.py

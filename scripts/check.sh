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
    pytest-core)
      "$PYTHON" -m pytest backend/tests/test_backend.py backend/tests/test_codex.py backend/tests/test_reconnect.py backend/tests/test_roles_messaging.py backend/tests/test_sandbox_diagnostics.py -q
      ;;
    pytest-backend)
      "$PYTHON" -m pytest backend/tests/test_backend.py -q
      ;;
    pytest-codex)
      "$PYTHON" -m pytest backend/tests/test_codex.py -q
      ;;
    pytest-reconnect)
      "$PYTHON" -m pytest backend/tests/test_reconnect.py -q
      ;;
    pytest-roles)
      "$PYTHON" -m pytest backend/tests/test_roles_messaging.py -q
      ;;
    pytest-sandbox)
      "$PYTHON" -m pytest backend/tests/test_sandbox_diagnostics.py -q
      ;;
    pytest-management)
      "$PYTHON" -m pytest backend/tests/test_agent_deletion.py backend/tests/test_management_definitions.py backend/tests/test_project_deletion.py backend/tests/test_project_documents.py backend/tests/test_project_setup.py -q
      ;;
    pytest-agent-deletion)
      "$PYTHON" -m pytest backend/tests/test_agent_deletion.py -q
      ;;
    pytest-management-definitions)
      "$PYTHON" -m pytest backend/tests/test_management_definitions.py -q
      ;;
    pytest-project-deletion)
      "$PYTHON" -m pytest backend/tests/test_project_deletion.py -q
      ;;
    pytest-project-documents)
      "$PYTHON" -m pytest backend/tests/test_project_documents.py -q
      ;;
    pytest-project-setup)
      "$PYTHON" -m pytest backend/tests/test_project_setup.py -q
      ;;
    pytest-execution)
      "$PYTHON" -m pytest backend/tests/test_management_execution.py backend/tests/test_management_git.py backend/tests/test_team_integration.py backend/tests/test_worker_publication.py -q
      ;;
    pytest-gui)
      "$PYTHON" -m pytest backend/tests/test_game_management.py backend/tests/test_game_tasks.py -q
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

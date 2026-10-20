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

run_pytest() {
  local report
  report=$(mktemp)
  if "$PYTHON" -m pytest "$@" -q --junitxml="$report"; then
    rm -f "$report"
    return 0
  else
    local result=$?
    "$PYTHON" - "$report" "${GITHUB_STEP_SUMMARY:-}" <<'PY'
import sys
import xml.etree.ElementTree as ET

report, summary_path = sys.argv[1:]
root = ET.parse(report).getroot()
failures = []
for case in root.iter("testcase"):
    problem = case.find("failure")
    if problem is None:
        problem = case.find("error")
    if problem is not None:
        name = "::".join(part for part in (case.get("classname"), case.get("name")) if part)
        kind = problem.get("type", "TestFailure").split(".")[-1]
        failures.append((name, kind))
for name, kind in failures:
    print(f"::error title=Pytest failure::{name} ({kind})")
if summary_path and failures:
    with open(summary_path, "a", encoding="utf-8") as summary:
        summary.write("\n### Pytest failures\n\n")
        summary.writelines(f"- `{name}` — `{kind}`\n" for name, kind in failures)
PY
    rm -f "$report"
    return "$result"
  fi
}

run_stage() {
  case "$1" in
    lint)
      ruff check backend scripts
      ruff format --check backend scripts
      ;;
    pytest)
      run_pytest backend/tests
      ;;
    pytest-core)
      run_pytest backend/tests/test_backend.py backend/tests/test_codex.py backend/tests/test_reconnect.py backend/tests/test_roles_messaging.py backend/tests/test_sandbox_diagnostics.py
      ;;
    pytest-backend)
      run_pytest backend/tests/test_backend.py
      ;;
    pytest-codex)
      run_pytest backend/tests/test_codex.py
      ;;
    pytest-reconnect)
      run_pytest backend/tests/test_reconnect.py
      ;;
    pytest-roles)
      run_pytest backend/tests/test_roles_messaging.py
      ;;
    pytest-sandbox)
      run_pytest backend/tests/test_sandbox_diagnostics.py
      ;;
    pytest-management)
      run_pytest backend/tests/test_agent_deletion.py backend/tests/test_management_definitions.py backend/tests/test_project_deletion.py backend/tests/test_project_documents.py backend/tests/test_project_setup.py
      ;;
    pytest-agent-deletion)
      run_pytest backend/tests/test_agent_deletion.py
      ;;
    pytest-management-definitions)
      run_pytest backend/tests/test_management_definitions.py
      ;;
    pytest-project-deletion)
      run_pytest backend/tests/test_project_deletion.py
      ;;
    pytest-project-documents)
      run_pytest backend/tests/test_project_documents.py
      ;;
    pytest-project-setup)
      run_pytest backend/tests/test_project_setup.py
      ;;
    pytest-execution)
      run_pytest backend/tests/test_management_execution.py backend/tests/test_management_git.py backend/tests/test_team_integration.py backend/tests/test_worker_publication.py
      ;;
    pytest-gui)
      run_pytest backend/tests/test_game_management.py backend/tests/test_game_tasks.py
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

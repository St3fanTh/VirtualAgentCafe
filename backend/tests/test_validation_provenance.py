"""Worker evidence and declared controller checks must not be confused."""

import json

import pytest
from test_codex import fake_cli
from test_godot_validation import fixture

from virtual_agent_cafe.adapters.codex import CodexAdapter, CodexObserver
from virtual_agent_cafe.adapters.diagnostics import godot_failure_category
from virtual_agent_cafe.management import validation


@pytest.mark.parametrize("script", [None, ""])
def test_godot_plan_requires_explicit_script(script):
    with pytest.raises(ValueError, match="explicit script"):
        validation.Check(id="frontend", kind="godot", script=script)


@pytest.mark.parametrize(
    "output,category",
    [
        ("ERROR: Condition _sock == -1 is true", "UNCLASSIFIED_ERROR"),
        ("SCRIPT ERROR: Assertion failed", "TEST_FAILURE"),
        ("ERROR: Script file does not exist", "CONFIGURATION_ERROR"),
        ("Error attempting to create data dir: /home/agent/.local", "ENVIRONMENT_ERROR"),
    ],
)
def test_engine_failures_need_evidence_before_blame(output, category):
    assert godot_failure_category(output) == category


async def test_wrapper_failure_retains_private_command_evidence(tmp_path):
    row = {
        "type": "item.completed",
        "item": {
            "id": "cmd-wrapper",
            "type": "command_execution",
            "command": "./run-tests.sh",
            "cwd": str(tmp_path),
            "exit_code": 134,
            "aggregated_output": "Error attempting to create data dir: /home/agent/.local",
        },
    }
    cli = fake_cli(
        tmp_path, f"print(json.dumps({row!r})); print(json.dumps({{'type':'turn.completed'}}))\n"
    )
    evidence = []

    async def sink(item, workspace):
        evidence.append((item, workspace))

    result = await CodexAdapter(cli, evidence_sink=sink).run("task", tmp_path, lambda *_: None)
    assert not result.success
    assert result.test_runs[0]["category"] == "ENVIRONMENT_ERROR"
    assert result.test_runs[0]["command_id"] == "cmd-wrapper"
    assert evidence == [(row["item"], tmp_path)]


def test_three_passes_do_not_hide_failed_obsolete_worker_command():
    observer = CodexObserver(lambda *_: None)
    for script, code in [
        ("smoke", 1),
        ("test_states", 0),
        ("test_protocol", 0),
        ("test_acceptance", 0),
    ]:
        observer.consume(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": f"godot --headless --path frontend --script res://tests/{script}.gd",
                    "cwd": "/project",
                    "exit_code": code,
                    "aggregated_output": "ERROR: Script file does not exist" if code else "PASS",
                },
            }
        )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful
    assert len(observer.failed_frameworks) == 1
    assert observer.test_runs[0]["category"] == "CONFIGURATION_ERROR"
    assert all(row["passed"] for row in observer.test_runs[1:])


async def test_only_declared_scripts_run_at_submitted_commit_and_are_cached(tmp_path):
    manager, config, run, workspace, main, _ = await fixture(tmp_path)
    # An obsolete script would fail loudly if an implicit command executed it.
    (workspace / "frontend/tests/smoke.gd").write_text(
        'extends SceneTree\nfunc _initialize():\n\tpush_error("OBSOLETE")\n\tquit(1)\n'
    )
    await manager.git.stage("integration", ["frontend/tests/smoke.gd"])
    await manager.git.commit("integration", "test: obsolete script sentinel")
    commit = (await manager.git.run(workspace, "rev-parse", "HEAD")).strip()
    run["submitted_commit"] = commit
    first = await validation.validate(manager, config, run, workspace)
    assert first["passed"] and first["commit"] == commit != main
    plan = json.loads((workspace / "validation/plan.json").read_text())
    assert len(first["checks"]) == len(plan["checks"]) == 3
    for check, declared in zip(first["checks"], plan["checks"], strict=True):
        assert check["context"]["command"][-1] == "res://" + declared["script"]
        assert check["context"]["cwd"] == str(workspace / "frontend")
        assert check["context"]["commit"] == commit
    second = await validation.validate(manager, config, run, workspace)
    assert second["passed"]
    assert all(check["cached"] for check in second["checks"])

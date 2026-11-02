"""Real repository/namespace regressions; no external projects or model claims."""

import json
import sys

import pytest
from test_godot_validation import fixture, save_plan
from test_team_integration import settle, start_workers, team

from virtual_agent_cafe.adapters.codex import CodexObserver
from virtual_agent_cafe.adapters.diagnostics import test_diagnostic as diagnostic
from virtual_agent_cafe.management import validation


async def pytest_fixture(tmp_path, source="def test_ok():\n    assert True\n"):
    manager, config, run, workspace, _, commit = await fixture(tmp_path)
    (workspace / "backend/tests").mkdir(parents=True)
    (workspace / "backend/tests/test_api.py").write_text(source)
    await manager.git.stage("integration", ["backend/tests/test_api.py"])
    await manager.git.commit("integration", "test: add backend suite")
    await save_plan(
        manager,
        workspace,
        lambda p: p.update(
            checks=[
                {"id": "backend", "kind": "pytest", "directory": "backend", "targets": ["tests"]}
            ],
            requirements=[
                {"id": "REQ-1", "description": "Backend API is correct", "checks": ["backend"]}
            ],
        ),
    )
    return manager, config, run, workspace


@pytest.mark.parametrize(
    "code,output,category",
    [
        (2, "ModuleNotFoundError: absent_package", "ENVIRONMENT_ERROR"),
        (2, "ERROR collecting tests/test_api.py\nSyntaxError", "COLLECTION_ERROR"),
        (2, "interrupted", "INTERRUPTED"),
        (1, "AssertionError", "TEST_FAILURE"),
        (1, "unexplained", "UNCLASSIFIED_ERROR"),
        (3, "INTERNALERROR", "TOOL_ERROR"),
        (5, "no tests ran", "CONFIGURATION_ERROR"),
    ],
)
def test_failure_classification_requires_evidence(code, output, category):
    assert diagnostic("pytest", code, output)["category"] == category


def test_a_passing_subset_does_not_clear_another_failed_scope():
    observer = CodexObserver(lambda *_: None)
    for command, code in [
        ("cd backend && python -m pytest", 2),
        ("cd frontend && python -m pytest", 0),
    ]:
        observer.consume(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": command,
                    "exit_code": code,
                    "aggregated_output": "ModuleNotFoundError: missing" if code else "71 passed",
                },
            }
        )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful
    assert not observer.test_runs[0].get("superseded")
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "cd backend && python -m pytest",
                "exit_code": 0,
            },
        }
    )
    assert observer.successful and observer.test_runs[0]["superseded"]


async def test_controller_collection_error_retains_both_streams_and_exact_context(tmp_path):
    manager, config, run, workspace = await pytest_fixture(
        tmp_path,
        "import sys\nprint('PRIVATE_STDOUT', flush=True)\n"
        "print('PRIVATE_STDERR', file=sys.stderr, flush=True)\n"
        "import definitely_absent_vac_module\n",
    )
    with pytest.raises(ValueError, match="ENVIRONMENT_ERROR"):
        await validation.validate(manager, config, run, workspace)
    report = run["validation"]
    assert report["state"] == "VALIDATION_INFRA_ERROR"
    check = report["checks"][0]
    assert check["exit_code"] == 2
    assert check["context"]["cwd"] == str(workspace / "backend")
    assert check["context"]["command"][0] == validation.runtime_python()
    assert check["context"]["command"][-1] == "./tests"
    assert report["commit"] == (await manager.git.run(workspace, "rev-parse", "HEAD")).strip()
    raw = manager.store.get("validation_outputs", run["id"] + ":backend")
    assert "PRIVATE_STDOUT" in raw["stdout"] and "PRIVATE_STDERR" in raw["stdout"]  # pytest capture
    assert "stderr" in raw and not raw["truncated"]
    assert "PRIVATE_STDOUT" not in repr(manager.store.logs(run["id"]))
    assert "PRIVATE_STDOUT" not in repr(run)


async def test_capture_separates_streams_and_classifies_timeout():
    result = await validation.capture_check(
        [sys.executable, "-c", "import sys; print('stdout'); print('stderr',file=sys.stderr)"], 5
    )
    assert result["stdout"] == "stdout\n" and result["stderr"] == "stderr\n"
    assert result["exit_code"] == 0 and not result["error"]
    result = await validation.capture_check(
        [sys.executable, "-c", "import time; print('before timeout',flush=True); time.sleep(20)"],
        0.2,
    )
    assert result["error"] == "Validation timed out"
    assert result["stdout"] == "before timeout\n" and result["exit_code"] != 0


async def test_cache_requires_same_commit_scope_environment_and_clean_workspace(
    tmp_path, monkeypatch
):
    manager, config, run, workspace = await pytest_fixture(tmp_path)
    original = validation.capture_check
    calls = []

    async def capture(*args):
        calls.append(args)
        return await original(*args)

    monkeypatch.setattr(validation, "capture_check", capture)
    first = await validation.validate(manager, config, run, workspace)
    second = await validation.validate(manager, config, {**run, "id": "second"}, workspace)
    assert first["passed"] and second["checks"][0]["cached"] and len(calls) == 1
    identity = validation.environment_identity()
    monkeypatch.setattr(
        validation, "environment_identity", lambda: {**identity, "sha256": "changed"}
    )
    await validation.validate(manager, config, {**run, "id": "environment"}, workspace)
    assert len(calls) == 2
    (workspace / "backend/tests/test_api.py").write_text("def test_changed():\n    assert True\n")
    with pytest.raises(ValueError, match="workspace.clean_before_tests"):
        await validation.validate(manager, config, run, workspace)
    assert len(calls) == 2
    await manager.git.stage("integration", ["backend/tests/test_api.py"])
    await manager.git.commit("integration", "test: changed dependency")
    await validation.validate(manager, config, run, workspace)
    assert len(calls) == 3
    await save_plan(
        manager, workspace, lambda p: p["checks"][0].update(targets=["tests/test_api.py"])
    )
    await validation.validate(manager, config, run, workspace)
    assert len(calls) == 4


async def test_wrong_submitted_commit_rejected_before_any_test(tmp_path, monkeypatch):
    manager, config, run, workspace = await pytest_fixture(tmp_path)
    run["submitted_commit"] = "0" * 40
    with pytest.raises(ValueError, match="git.submitted_commit"):
        await validation.validate(manager, config, run, workspace)
    assert not run["validation"]["checks"]


async def test_environment_blocker_stops_repairs_but_preserves_worker_commits(
    tmp_path, monkeypatch
):
    manager, remote, initial, _ = await team(tmp_path, monkeypatch)
    original = manager.adapter.run

    async def missing_dependency(context, workspace, emit):
        result = await original(context, workspace, emit)
        if workspace.name.endswith("integration"):
            (workspace / "tests/test_contract.py").write_text("import missing_vac_dependency\n")
            await manager.git.stage(workspace.name, ["tests/test_contract.py"])
            await manager.git.commit(workspace.name, "test: reproduce unavailable dependency")
        return result

    manager.adapter.run = missing_dependency
    await start_workers(manager)
    integration = manager.store.get("projects", "project")["integration"]
    assert integration["status"] == "NEEDS_INPUT" and integration["attempt"] == 1
    assert integration["validation_state"] == "VALIDATION_INFRA_ERROR"
    assert (await manager.git.run(remote, "rev-parse", "main")).strip() == initial
    for worker in ("project-backend", "project-frontend"):
        record = manager.registry.get(worker)
        result = manager.store.get("executions", record["last_execution"])
        assert result["workflow"]["implementation"] == "IMPLEMENTATION_COMPLETE"
        assert result["agent_commit"] and result["publication"] == "PUSHED"
    manager.integrations.schedule("project-backend")
    await settle(manager)
    assert len(manager.adapter.integration_contexts) == 1


async def test_manual_product_acceptance_is_separate_and_does_not_block_workers(
    tmp_path, monkeypatch
):
    manager, remote, _, _ = await team(tmp_path, monkeypatch)
    original = manager.adapter.run

    async def manual(context, workspace, emit):
        result = await original(context, workspace, emit)
        if workspace.name.endswith("integration"):
            path = workspace / "validation/plan.json"
            plan = json.loads(path.read_text())
            plan["manual_acceptance"] = ["Desktop interaction review"]
            path.write_text(json.dumps(plan))
            await manager.git.stage(workspace.name, ["validation/plan.json"])
            await manager.git.commit(workspace.name, "test: require desktop product acceptance")
        return result

    manager.adapter.run = manual
    await start_workers(manager)
    integration = manager.store.get("projects", "project")["integration"]
    assert integration["status"] == "PROMOTED"
    run = manager.store.get("executions", integration["execution"])
    assert run["acceptance"] == "MANUAL_ACCEPTANCE_REQUIRED"
    assert run["workflow"]["integration"] == "INTEGRATED"
    assert (await manager.git.run(remote, "rev-parse", "main")).strip() == run["validation"][
        "commit"
    ]
    manager.integrations.guard_start("project-backend")  # unrelated work remains startable
    reviewed = manager.review(run["id"], True, "Desktop interaction checked")
    assert reviewed["workflow"]["acceptance"] == "ACCEPTED"


async def test_missing_worker_commit_is_explicit(tmp_path):
    manager, _, _, _ = await pytest_fixture(tmp_path)
    with pytest.raises(ValueError, match="Required commit is unavailable"):
        await manager.git.require_commit("integration", "f" * 40)


async def test_successful_push_without_matching_remote_is_not_reported_success(
    tmp_path, monkeypatch
):
    manager, _, _, workspace = await pytest_fixture(tmp_path)
    from unittest.mock import AsyncMock

    monkeypatch.setattr(
        manager.git, "run", AsyncMock(return_value="0" * 40 + "\trefs/heads/main\n")
    )
    with pytest.raises(ValueError, match="does not match"):
        await manager.git.verify_remote_commit(workspace, "origin", "main", "f" * 40)


async def test_host_only_controller_python_is_not_used_inside_sandbox(tmp_path, monkeypatch):
    manager, config, run, workspace = await pytest_fixture(tmp_path)
    monkeypatch.setattr(validation.sys, "executable", "/not-mounted/controller/python")
    report = await validation.validate(manager, config, run, workspace)
    assert report["passed"]
    assert report["checks"][0]["context"]["command"][0] == validation.runtime_python()


async def test_ignored_dependency_disables_cache_reuse(tmp_path):
    manager, config, run, workspace = await pytest_fixture(tmp_path)
    path = workspace / ".gitignore"
    path.write_text(path.read_text() + "dependency.txt\n")
    await manager.git.stage("integration", [".gitignore"])
    await manager.git.commit("integration", "test: declare ignored dependency")
    await validation.validate(manager, config, run, workspace)
    (workspace / "dependency.txt").write_text("changed outside Git")
    report = await validation.validate(manager, config, run, workspace)
    assert report["passed"] and not report["checks"][0]["cached"]


async def test_raw_controller_output_requires_management_auth(tmp_path):
    from fastapi.testclient import TestClient

    from virtual_agent_cafe.main import create_app

    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    manager.store.put("validation_outputs", "run:check", {"stdout": "PRIVATE"})
    with TestClient(app) as client:
        url = "/management/executions/run/validation-output/check"
        assert client.get(url).status_code == 401
        response = client.get(url, headers={"Authorization": "Bearer " + manager.access.token})
        assert response.json()["stdout"] == "PRIVATE"


def test_godot_zero_exit_script_error_does_not_claim_runtime_success():
    observer = CodexObserver(lambda *_: None)
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "godot --headless --script tests/test_api.gd",
                "exit_code": 0,
                "aggregated_output": "SCRIPT ERROR: fixture error\n",
            },
        }
    )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful
    assert observer.test_runs[0]["category"] == "TEST_FAILURE"


async def test_private_codex_evidence_is_available_without_public_output_leak(tmp_path):
    from test_codex import fake_cli

    from virtual_agent_cafe.adapters.codex import CodexAdapter

    row = {
        "type": "item.completed",
        "item": {
            "type": "command_execution",
            "command": "python -m pytest",
            "exit_code": 2,
            "aggregated_output": "ModuleNotFoundError: PRIVATE_PACKAGE_NAME\n",
        },
    }
    cli = fake_cli(
        tmp_path, f"print(json.dumps({row!r})); print(json.dumps({{'type':'turn.completed'}}))\n"
    )
    captured, events = [], []

    async def sink(item, workspace):
        captured.append(item)

    result = await CodexAdapter(cli, evidence_sink=sink).run(
        "task", tmp_path, lambda *event: events.append(event)
    )
    assert result.implementation_complete and not result.success
    assert "PRIVATE_PACKAGE_NAME" in captured[0]["aggregated_output"]
    assert "PRIVATE_PACKAGE_NAME" not in repr(events) + repr(result)


async def test_explicit_project_interpreter_is_used_and_missing_one_is_infrastructure(tmp_path):
    import asyncio

    manager, config, run, workspace = await pytest_fixture(tmp_path)
    await save_plan(manager, workspace, lambda p: p["checks"][0].update(python="project-venv"))
    with pytest.raises(ValueError, match="pytest.interpreter"):
        await validation.validate(manager, config, run, workspace)
    assert run["validation"]["state"] == "VALIDATION_INFRA_ERROR"
    # No installs/network: build a project venv using the already provisioned runtime packages.
    process = await asyncio.create_subprocess_exec(
        validation.runtime_python(),
        "-m",
        "venv",
        "--without-pip",
        "--system-site-packages",
        str(workspace / "backend/.venv"),
    )
    assert await process.wait() == 0
    # A venv created from a virtualenv inherits the base Python's site packages, so expose
    # the already provisioned pytest through a .pth inside the approved project environment.
    import sysconfig

    site = next((workspace / "backend/.venv/lib").glob("python*/site-packages"))
    (site / "fixture.pth").write_text(sysconfig.get_paths()["purelib"] + "\n")
    ignore = workspace / ".gitignore"
    ignore.write_text(ignore.read_text() + ".venv/\n")
    await manager.git.stage("integration", [".gitignore"])
    await manager.git.commit("integration", "test: ignore provisioned environment")
    report = await validation.validate(manager, config, run, workspace)
    assert report["passed"]
    assert report["checks"][0]["context"]["command"][0] == str(
        workspace / "backend/.venv/bin/python"
    )
    assert not report["checks"][0]["cached"]


@pytest.mark.parametrize(
    "exception,rule,detail",
    [
        (TimeoutError, "environment.inspect", "Validation timed out"),
        (RuntimeError, "controller.exception", "Controller validation failed unexpectedly"),
    ],
)
async def test_controller_errors_are_not_implementation_failures(
    tmp_path, monkeypatch, exception, rule, detail
):
    manager, config, run, workspace = await pytest_fixture(tmp_path)

    def fail():
        raise exception("PRIVATE_INTERNAL_DETAIL")

    monkeypatch.setattr(validation, "environment_identity", fail)
    with pytest.raises(ValueError, match=detail):
        await validation.validate(manager, config, run, workspace)
    assert run["validation"]["state"] == "VALIDATION_INFRA_ERROR"
    assert run["validation"]["failed_rule"] == rule
    assert "PRIVATE_INTERNAL_DETAIL" not in repr(run) + repr(manager.store.logs(run["id"]))


def test_verbosity_only_rerun_resolves_same_scope_but_selectors_do_not():
    observer = CodexObserver(lambda *_: None)
    for command, code in [
        ("bash -lc 'cd backend && python -m pytest'", 2),
        ("bash -lc 'cd backend && python -m pytest -q tests/test_subset.py'", 0),
    ]:
        observer.consume(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": command,
                    "exit_code": code,
                },
            }
        )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "bash -lc 'cd backend && python -m pytest -q'",
                "exit_code": 0,
            },
        }
    )
    assert observer.successful

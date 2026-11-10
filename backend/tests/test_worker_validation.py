"""Real nested socket failure -> trusted offline recheck -> real local Git publication."""

import asyncio

import pytest
from test_worker_publication import publication_project

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.adapters.codex import CodexObserver
from virtual_agent_cafe.management import worker_validation
from virtual_agent_cafe.management.sandbox import Sandbox

SCRIPT = """extends SceneTree
func _initialize():
    var server = TCPServer.new()
    print("LISTEN=", server.listen(0, "127.0.0.1"))
    server.stop()
    print("PASS")
    quit(0)
"""


async def setup(tmp_path, monkeypatch, *, real_error=False):
    manager, config, workspace, remote, pushes = await publication_project(tmp_path, monkeypatch)
    (workspace / "frontend/tests").mkdir(parents=True)
    (workspace / "frontend/project.godot").write_text("config_version=5\n")
    source = SCRIPT
    if real_error:
        source = source.replace('print("PASS")', 'push_error("Genuine runtime failure")')
    (workspace / "frontend/tests/test_states.gd").write_text(source)
    for name in ("test_protocol", "test_acceptance"):
        (workspace / f"frontend/tests/{name}.gd").write_text(
            'extends SceneTree\nfunc _initialize():\n print("PASS")\n quit(0)\n'
        )
    await manager.git.stage(
        "project",
        [
            "frontend/project.godot",
            *[
                f"frontend/tests/{name}.gd"
                for name in ("test_states", "test_protocol", "test_acceptance")
            ],
        ],
    )
    await manager.git.commit("project", "feat: committed frontend tests")

    class Runtime:
        calls = 0

        async def run(self, context, path, emit):
            self.calls += 1
            observer = CodexObserver(emit)
            rows = []
            for name in ("test_states", "test_protocol", "test_acceptance"):
                args = [
                    "godot",
                    "--headless",
                    "--path",
                    "frontend",
                    "--script",
                    f"res://tests/{name}.gd",
                ]
                process = await asyncio.create_subprocess_exec(
                    *Sandbox().command(
                        path,
                        ["codex", "sandbox", "-c", 'sandbox_mode="workspace-write"', "--", *args],
                        network=False,
                        writable_git=False,
                    ),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                item = {
                    "type": "command_execution",
                    "command": "/usr/bin/bash -lc '" + " ".join(args) + "'",
                    "cwd": None,
                    "exit_code": process.returncode,
                    "aggregated_output": (stdout + stderr).decode(),
                }
                observer.consume({"type": "item.completed", "item": item})
                rows.append(
                    {
                        "command": item["command"],
                        "reported_cwd": None,
                        "workspace": str(path),
                        "aggregated_output": item["aggregated_output"],
                        "exit_code": item["exit_code"],
                    }
                )
            observer.consume({"type": "turn.completed"})
            assert not observer.successful
            assert "_sock == -1" in rows[0]["aggregated_output"]
            run_id = manager.registry.get(config.id)["last_execution"]
            manager.store.put("runtime_test_outputs", run_id, {"checks": rows})
            return RunResult(
                False,
                "Unresolved Godot socket failure",
                tuple(observer.test_runs),
                implementation_complete=True,
            )

    runtime = Runtime()
    manager.adapter = runtime
    return manager, config, workspace, remote, pushes, runtime


async def finished(manager, config, **kwargs):
    run = await manager.start(config.id, **kwargs)
    await manager.running[config.id]
    return manager.store.get("executions", run["id"])


async def test_socket_blocked_worker_is_rechecked_then_published(tmp_path, monkeypatch):
    manager, config, workspace, remote, pushes, runtime = await setup(tmp_path, monkeypatch)
    commit = (await manager.git.run(workspace, "rev-parse", "HEAD")).strip()
    run = await finished(manager, config)
    assert run["status"] == "COMPLETED", run["detail"]
    assert runtime.calls == 1 and run["controller_recovered"]
    assert run["worker_runtime_success"] is False
    assert run["worker_validation"]["commit"] == commit
    assert len(run["worker_validation"]["checks"]) == 3
    assert all(c["passed"] for c in run["worker_validation"]["checks"])
    assert run["publication"] == "PUSHED" and pushes
    assert run["workflow"]["integration"] == "INTEGRATION_PENDING"
    assert "validation" not in run  # Observed-test recovery is not shared requirements acceptance.
    assert all(t["passed"] or t.get("superseded") for t in run["test_runs"])
    assert await manager.git.run(
        remote, "show", "refs/heads/agent/backend-agent/task:frontend/tests/test_states.gd"
    )


async def test_real_error_at_zero_exit_stays_blocked(tmp_path, monkeypatch):
    manager, config, _, _, pushes, _ = await setup(tmp_path, monkeypatch, real_error=True)
    run = await finished(manager, config)
    assert run["status"] == "FAILED"
    assert not run.get("controller_recovered")
    assert run["worker_validation"]["passed"] is False
    assert any(not c["passed"] for c in run["worker_validation"]["checks"])
    assert not pushes and run["publication"] == "NOT_PUBLISHED"
    assert any(not t["passed"] and not t.get("superseded") for t in run["test_runs"])


async def test_retry_existing_failed_run_without_another_model_turn(tmp_path, monkeypatch):
    manager, config, workspace, _, pushes, runtime = await setup(tmp_path, monkeypatch)
    recover = worker_validation.recover

    async def old_controller(manager, config, run, workspace, result):
        return result

    monkeypatch.setattr(worker_validation, "recover", old_controller)
    old = await finished(manager, config)
    assert old["status"] == "FAILED" and not pushes
    monkeypatch.setattr(worker_validation, "recover", recover)
    manager.store.put("executions", old["id"], {**old, "agent_commit": "0" * 40})
    with pytest.raises(ValueError, match="commit changed"):
        await manager.start(config.id, retry_validation=True)
    manager.store.put("executions", old["id"], old)
    assert manager.registry.get(config.id)["state"] == "FAILED"
    (workspace / "frontend/tests/test_states.gd").write_text(SCRIPT + "\n# uncommitted\n")
    with pytest.raises(ValueError):
        await manager.start(config.id, retry_validation=True)
    (workspace / "frontend/tests/test_states.gd").write_text(SCRIPT)
    retried = await finished(manager, config, retry_validation=True)
    assert retried["status"] == "COMPLETED", retried["detail"]
    assert retried["recheck_of"] == old["id"]
    assert retried["publication"] == "PUSHED"
    assert runtime.calls == 1
    assert manager.store.get("executions", old["id"])["status"] == "FAILED"


@pytest.mark.parametrize(
    "command",
    [
        "godot --headless --path frontend --script res://tests/test_states.gd",
        '/bin/bash -lc \'cd "$PWD" && env XDG_RUNTIME_DIR=/tmp/runtime '
        'FONTCONFIG_FILE="$PWD/frontend/fonts.conf" godot --headless '
        "--path frontend --script res://tests/test_states.gd'",
    ],
)
def test_explicit_commands_are_parsed_without_shell_execution(tmp_path, command):
    (tmp_path / "frontend/tests").mkdir(parents=True)
    check = worker_validation.observed_check(
        {"command": command, "reported_cwd": str(tmp_path)}, tmp_path
    )
    assert check.directory == "frontend" and check.script == "tests/test_states.gd"
    if "FONTCONFIG_FILE" in command:
        assert check.fontconfig_file == "frontend/fonts.conf"


@pytest.mark.parametrize("shell", ["/usr/bin/bash", "/usr/bin/sh"])
@pytest.mark.parametrize("name", ["test_states", "test_protocol", "test_acceptance"])
def test_recorded_shell_wrappers_resolve_null_cwd_to_workspace(tmp_path, shell, name):
    (tmp_path / "frontend/tests").mkdir(parents=True)
    command = f"{shell} -lc 'godot --headless --path frontend --script res://tests/{name}.gd'"
    check = worker_validation.observed_check({"command": command, "reported_cwd": None}, tmp_path)
    assert check.directory == "frontend"
    assert check.script == f"tests/{name}.gd"
    direct = worker_validation.observed_check(
        {"command": f"godot --headless --path frontend --script res://tests/{name}.gd"}, tmp_path
    )
    assert check == direct


@pytest.mark.parametrize(
    "command",
    [
        "godot --headless --script test.gd; touch /tmp/escape",
        "godot --headless --script test.gd | cat",
        "godot --headless --script test.gd -- --skip-tests",
        "env TEST_FILTER=none godot --headless --script test.gd",
        "godot --headless --path /etc --script test.gd",
        "godot --headless --script ../test.gd",
        "godot --headless --script test.gd > output.txt",
        "python3 wrapper.py",
        "/tmp/bash -lc 'godot --headless --script test.gd'",
        "/custom/usr/bin/sh -lc 'godot --headless --script test.gd'",
        "/usr/bin/bash-custom -lc 'godot --headless --script test.gd'",
        "/usr/bin/bash -lc 'godot --headless --script test.gd; touch /tmp/escape'",
        "/usr/bin/sh -lc 'godot --headless --script test.gd && touch /tmp/escape'",
        "/usr/bin/bash -lc 'godot --headless --script test.gd' && touch /tmp/escape",
        "/usr/bin/bash -lc 'godot --headless --script \"$(touch /tmp/escape).gd\"'",
        "/usr/bin/bash -lc 'godot --headless --script \"`touch /tmp/escape`.gd\"'",
    ],
)
def test_unsupported_or_escaping_commands_remain_blocked(tmp_path, command):
    with pytest.raises(ValueError):
        worker_validation.observed_check({"command": command}, tmp_path)


def test_other_failure_cannot_be_cleared_by_godot_recheck(tmp_path):
    result = RunResult(
        False, "failed", ({"tool": "pytest", "passed": False, "category": "TEST_FAILURE"},), True
    )
    assert worker_validation.candidates(result, {"checks": []}, tmp_path) is None


@pytest.mark.parametrize("blocked_stage", ["frontend", "integration"])
async def test_recovered_worker_automatically_integrates_with_shared_tests(
    tmp_path, monkeypatch, blocked_stage
):
    import json

    from test_team_integration import start_workers, team

    manager, remote, initial, _ = await team(tmp_path, monkeypatch)
    original = manager.adapter.run

    async def socket_blocked(context, workspace, emit):
        result = await original(context, workspace, emit)
        if workspace.name.endswith("frontend"):
            (workspace / "frontend/tests").mkdir(parents=True)
            (workspace / "frontend/project.godot").write_text("config_version=5\n")
            (workspace / "frontend/tests/test_states.gd").write_text(SCRIPT)
            await manager.git.stage(
                workspace.name, ["frontend/project.godot", "frontend/tests/test_states.gd"]
            )
            await manager.git.commit(workspace.name, "test: local networking coverage")
        if workspace.name.endswith("integration"):
            path = workspace / "validation/plan.json"
            plan = json.loads(path.read_text())
            plan["checks"].append(
                {
                    "id": "godot",
                    "kind": "godot",
                    "directory": "frontend",
                    "script": "tests/test_states.gd",
                }
            )
            plan["requirements"][0]["checks"].append("godot")
            path.write_text(json.dumps(plan))
            await manager.git.stage(workspace.name, ["validation/plan.json"])
            await manager.git.commit(workspace.name, "test: shared Godot coverage")
        if workspace.name.endswith(blocked_stage):
            command = (
                "/usr/bin/bash -lc 'XDG_DATA_HOME=/tmp/simworld-xdg-data "
                "XDG_CONFIG_HOME=/tmp/simworld-xdg-config "
                "XDG_CACHE_HOME=/tmp/simworld-xdg-cache XDG_STATE_HOME=/tmp/simworld-xdg-state "
                f"godot --headless --path {workspace}/frontend --script res://tests/test_states.gd'"
            )
            output = (
                'ERROR: Condition "_sock == -1" is true.\n'
                " at: open (drivers/unix/net_socket_unix.cpp:273)"
            )
            observer = CodexObserver(emit)
            observer.consume(
                {
                    "type": "item.completed",
                    "item": {
                        "type": "command_execution",
                        "command": command,
                        "cwd": None,
                        "exit_code": 0,
                        "aggregated_output": output,
                    },
                }
            )
            run_id = manager.registry.get(workspace.name)["last_execution"]
            manager.store.put(
                "runtime_test_outputs",
                run_id,
                {
                    "checks": [
                        {
                            "command": command,
                            "reported_cwd": None,
                            "workspace": str(workspace),
                            "exit_code": 0,
                            "aggregated_output": output,
                        }
                    ]
                },
            )
            return RunResult(False, "Socket blocked", tuple(observer.test_runs), True)
        return result

    manager.adapter.run = socket_blocked
    await start_workers(manager)
    project = manager.store.get("projects", "project")
    assert project["integration"]["status"] == "PROMOTED", project["integration"]
    run = manager.store.get("executions", project["integration"]["execution"])
    assert run["validation"]["passed"] and len(run["validation"]["checks"]) == 2
    assert run["workflow"]["integration"] == "INTEGRATED"
    if blocked_stage == "integration":
        assert run["controller_recovered"]
        assert run["worker_validation"]["passed"]
        assert (
            run["worker_validation"]["checks"][0]["context"]["runtime_environment"][
                "XDG_STATE_HOME"
            ]
            == "/tmp/vac-user/state"
        )
    assert (await manager.git.run(remote, "rev-parse", "main")).strip() != initial


def test_retry_validation_api_requires_authentication_and_dispatches(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    from fastapi.testclient import TestClient

    from virtual_agent_cafe.main import create_app

    monkeypatch.setenv("VAC_MANAGEMENT_TOKEN", "recheck-test-management-token")
    app = create_app("codex", management_root=tmp_path)
    with TestClient(app) as client:
        start = AsyncMock(return_value={"id": "new-recheck"})
        monkeypatch.setattr(app.state.management, "start", start)
        url = "/management/agents/frontend/retry-validation"
        assert client.post(url, json={}).status_code == 401
        client.headers["Authorization"] = "Bearer recheck-test-management-token"
        assert client.post(url, json={}).status_code == 202
        start.assert_awaited_once_with("frontend", retry_validation=True)


def test_incomplete_evidence_never_clears_unknown_failures(tmp_path):
    result = RunResult(
        False,
        "failed",
        ({"tool": "Godot headless tests", "passed": False, "category": "UNCLASSIFIED_ERROR"},),
        True,
    )
    with pytest.raises(ValueError, match="incomplete history"):
        worker_validation.candidates(result, {"checks": [{}] * 100}, tmp_path)


def test_godot_recheck_rejects_symlink_project(tmp_path):
    (tmp_path / "frontend").symlink_to("/etc", target_is_directory=True)
    with pytest.raises(ValueError, match="Symlinks"):
        worker_validation.observed_check(
            {"command": "godot --headless --path frontend --script tests/test_states.gd"}, tmp_path
        )


@pytest.mark.parametrize("name", ["test_states", "test_protocol", "test_acceptance"])
def test_recorded_integration_xdg_state_command(tmp_path, name):
    (tmp_path / "frontend/tests").mkdir(parents=True)
    command = (
        "/usr/bin/bash -lc 'XDG_DATA_HOME=/tmp/simworld-xdg-data "
        "XDG_CONFIG_HOME=/tmp/simworld-xdg-config XDG_CACHE_HOME=/tmp/simworld-xdg-cache "
        "XDG_STATE_HOME=/tmp/simworld-xdg-state godot --headless "
        f"--path {tmp_path}/frontend --script res://tests/{name}.gd'"
    )
    check = worker_validation.observed_check({"command": command, "reported_cwd": None}, tmp_path)
    direct = worker_validation.observed_check(
        {"command": f"godot --headless --path frontend --script res://tests/{name}.gd"}, tmp_path
    )
    assert check == direct  # Worker XDG overrides never enter the controller command/cache scope.
    assert check.directory == "frontend" and check.script == f"tests/{name}.gd"


@pytest.mark.parametrize(
    "assignments, expected",
    [
        (
            "XDG_STATE_HOME=private-value XDG_STATE_HOME=other-value",
            "Repeated test environment setting: XDG_STATE_HOME",
        ),
        ("TEST_FILTER=private-value", "Unsupported test environment setting: TEST_FILTER"),
        ("bad/private-value=secret", "Unsupported test environment setting: <invalid name>"),
    ],
)
def test_environment_errors_name_setting_without_values(tmp_path, assignments, expected):
    with pytest.raises(ValueError) as error:
        worker_validation.observed_check(
            {"command": f"{assignments} godot --headless --script test.gd"}, tmp_path
        )
    assert str(error.value) == expected

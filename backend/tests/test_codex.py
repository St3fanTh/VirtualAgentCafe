import asyncio
import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.adapters.codex import CodexAdapter, CodexObserver, is_test_command
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.jobs import BusyError, JobManager
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.models import EventType


@pytest.mark.parametrize(
    "command",
    [
        "pytest -q",
        "python3 -m unittest -v",
        "/bin/bash -lc 'python3 -m pytest'",
        "npm test",
        "cargo test",
        "godot --headless --path game",
    ],
)
def test_known_test_commands(command):
    assert is_test_command(command)


@pytest.mark.parametrize(
    "command",
    ["ls", "cat pytest.ini", "echo testing", "git status", "echo 'pytest -q'", "cat pytest"],
)
def test_other_commands_are_not_invented_tests(command):
    assert not is_test_command(command)


def test_observer_evidence_and_redaction():
    events = []
    observer = CodexObserver(lambda kind, detail: events.append((kind, detail)))
    observer.consume({"type": "turn.started"})
    observer.consume({"type": "item.started", "item": {"type": "reasoning", "text": "SECRET"}})
    observer.consume(
        {"type": "item.completed", "item": {"type": "file_change", "status": "completed"}}
    )
    observer.consume(
        {
            "type": "item.started",
            "item": {"type": "command_execution", "command": "python3 -m unittest -v"},
        }
    )
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "python3 -m unittest -v",
                "exit_code": 0,
                "aggregated_output": "SECRET",
            },
        }
    )
    observer.consume(
        {"type": "item.completed", "item": {"type": "agent_message", "text": "SECRET"}}
    )
    observer.consume({"type": "turn.completed"})
    assert observer.successful
    assert [e[0] for e in events] == [
        EventType.THINKING,
        EventType.CODING,
        EventType.TESTING,
        EventType.TESTING,
        EventType.MESSAGE,
    ]
    assert "SECRET" not in repr(events)


def test_namespace_failure_cannot_be_reported_as_success():
    observer = CodexObserver(lambda *_: None)
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "ls",
                "exit_code": 1,
                "aggregated_output": "bwrap: No permissions to create a new namespace",
            },
        }
    )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful


def test_failed_tests_require_observed_successful_rerun():
    observer = CodexObserver(lambda *_: None)
    for code in [1, 0]:
        observer.consume(
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "pytest", "exit_code": code},
            }
        )
        observer.consume({"type": "turn.completed"})
        assert observer.successful == (code == 0)


def fake_cli(tmp_path: Path, body: str) -> str:
    executable = tmp_path / "fake-codex"
    executable.write_text(
        "#!/usr/bin/env python3\nimport json, sys, time, os\nprompt = sys.stdin.read()\n" + body
    )
    executable.chmod(0o755)
    return str(executable)


async def test_actual_subprocess_stdin_and_jsonl(tmp_path):
    transcript = [
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "file_change"}},
        {"type": "turn.completed"},
    ]
    body = (
        "assert prompt == 'PRIVATE task'\nassert 'PRIVATE task' not in sys.argv\n"
        f"for row in {transcript!r}: print(json.dumps(row), flush=True)\n"
    )
    cli = fake_cli(tmp_path, body)
    events = []
    result = await CodexAdapter(cli).run(
        "PRIVATE task", tmp_path, lambda kind, detail: events.append((kind, detail))
    )
    assert result.success
    assert "PRIVATE" not in repr(events)


@pytest.mark.parametrize(
    "body",
    [
        "print('not-json')",
        "print('{}')",
        "sys.exit(1)",
        "print(json.dumps({'type':'turn.failed'}))",
        "print('x' * (1024 * 1024 + 1))",
    ],
)
async def test_bad_process_streams_fail_safely(tmp_path, body):
    result = await CodexAdapter(fake_cli(tmp_path, body)).run("test", tmp_path, lambda *_: None)
    assert not result.success


async def test_timeout_terminates_process(tmp_path):
    pidfile = tmp_path / "pid"
    cli = fake_cli(tmp_path, f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)")
    result = await CodexAdapter(cli, timeout=0.2).run("test", tmp_path, lambda *_: None)
    assert not result.success and "timed out" in result.reason
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


async def test_cancel_terminates_process(tmp_path):
    pidfile = tmp_path / "pid"
    cli = fake_cli(tmp_path, f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)")
    task = asyncio.create_task(CodexAdapter(cli).run("test", tmp_path, lambda *_: None))
    for _ in range(100):
        if pidfile.exists():
            break
        await asyncio.sleep(0.01)
    assert pidfile.exists()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    with pytest.raises(ProcessLookupError):
        os.kill(int(pidfile.read_text()), 0)


class ControlledAdapter:
    def __init__(self):
        self.release = asyncio.Event()

    async def run(self, prompt, workspace, emit):
        emit(EventType.CODING, "Observed edit")
        await self.release.wait()
        (workspace / "result.txt").write_text("done")
        return RunResult(True, "Complete")


async def test_jobs_busy_isolated_workspaces_completion(tmp_path):
    bus = EventBus()
    adapter = ControlledAdapter()
    jobs = JobManager(bus, adapter, tmp_path)
    first = jobs.submit("ada", "private")
    second = jobs.submit("turing", "other")
    with pytest.raises(BusyError):
        jobs.submit("ada", "duplicate")
    adapter.release.set()
    await asyncio.gather(*list(jobs.running.values()))
    assert not jobs.running
    assert jobs.history[first["task_id"]]["status"] == "finished"
    assert jobs.history[second["task_id"]]["status"] == "finished"
    assert (tmp_path / "ada/result.txt").exists()
    assert (tmp_path / "turing/result.txt").exists()
    assert "private" not in json.dumps(bus.snapshot())


async def test_cancel_before_job_started(tmp_path):
    jobs = JobManager(EventBus(), ControlledAdapter(), tmp_path)
    record = jobs.submit("ada", "private")
    assert await jobs.cancel("ada")
    assert not jobs.running
    assert jobs.history[record["task_id"]]["status"] == "cancelled"


async def test_symlink_workspace_escape_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "ada").symlink_to(tmp_path, target_is_directory=True)
    jobs = JobManager(EventBus(), ControlledAdapter(), root)
    record = jobs.submit("ada", "private")
    await asyncio.gather(*list(jobs.running.values()))
    assert jobs.history[record["task_id"]]["status"] == "error"


def test_task_api_validation_busy_cancel_and_privacy(tmp_path):
    app = create_app(mode="codex", adapter=ControlledAdapter(), workspace_root=tmp_path)
    with TestClient(app) as client:
        assert client.post("/agents/ada/tasks", json={"prompt": " "}).status_code == 422
        assert client.post("/agents/ada/tasks", json={"prompt": "x" * 8001}).status_code == 422
        assert (
            client.post(
                "/agents/ada/tasks",
                content="x" * 32769,
                headers={"content-type": "application/json"},
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/agents/ada/tasks", json={"prompt": "ok"}, headers={"origin": "https://evil.test"}
            ).status_code
            == 403
        )
        assert (
            client.post("/agents/ada/tasks", json={"prompt": "ok", "cwd": "/"}).status_code == 422
        )
        assert client.post("/agents/nope/tasks", json={"prompt": "ok"}).status_code == 404
        with client.websocket_connect("/ws/events") as ws:
            ws.receive_json()
            response = client.post("/agents/ada/tasks", json={"prompt": "SECRET"})
            assert response.status_code == 202
            task_id = response.json()["task_id"]
            assert "SECRET" not in json.dumps(ws.receive_json())
            assert client.post("/agents/ada/tasks", json={"prompt": "another"}).status_code == 409
            assert client.post("/agents/ada/cancel").status_code == 200
            assert client.get("/tasks/" + task_id).json()["status"] == "cancelled"
    assert not app.state.jobs.running


def test_demo_rejects_live_tasks_and_messages(tmp_path):
    with TestClient(create_app(workspace_root=tmp_path)) as client:
        assert client.post("/agents/ada/tasks", json={"prompt": "task"}).status_code == 409


def test_actual_peer_message_delivery(tmp_path):
    with TestClient(create_app(mode="codex", workspace_root=tmp_path)) as client:
        with client.websocket_connect("/ws/events") as ws:
            ws.receive_json()
            response = client.post(
                "/agents/ada/messages", json={"recipient": "turing", "text": "Please review"}
            )
            assert response.status_code == 202
            sent, received = ws.receive_json()["event"], ws.receive_json()["event"]
            assert sent["payload"]["recipient"] == "turing"
            assert received["agent_id"] == "turing"
            assert sent["correlation_id"] == received["correlation_id"]
            assert (
                client.post(
                    "/agents/ada/messages", json={"recipient": "ada", "text": "Hello"}
                ).status_code
                == 422
            )


def test_helper_failure_does_not_override_later_edit_and_successful_tests():
    events = []
    observer = CodexObserver(lambda kind, detail: events.append((kind, detail)))
    transcript = [
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "rg --files", "exit_code": 1},
        },
        {"type": "item.completed", "item": {"type": "file_change", "status": "completed"}},
        {
            "type": "item.started",
            "item": {"type": "command_execution", "command": "python3 -m unittest -v"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "python3 -m unittest -v",
                "exit_code": 0,
            },
        },
        {"type": "turn.completed"},
    ]
    for entry in transcript:
        observer.consume(entry)
    assert observer.successful
    assert observer.command_warnings == 1
    assert EventType.ERROR in [kind for kind, _ in events]
    assert EventType.CODING in [kind for kind, _ in events]
    assert EventType.TESTING in [kind for kind, _ in events]


@pytest.mark.parametrize("failure", ["test", "patch", "runtime", "sandbox"])
def test_successful_other_commands_cannot_clear_real_failures(failure):
    observer = CodexObserver(lambda *_: None)
    if failure == "test":
        observer.consume(
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": "pytest", "exit_code": 1},
            }
        )
    elif failure == "patch":
        observer.consume(
            {"type": "item.completed", "item": {"type": "file_change", "status": "failed"}}
        )
    elif failure == "runtime":
        observer.consume({"type": "turn.failed"})
    else:
        observer.consume(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "ls",
                    "exit_code": 1,
                    "aggregated_output": "bwrap: Operation not permitted",
                },
            }
        )
    observer.consume(
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "echo done", "exit_code": 0},
        }
    )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful


def test_new_turn_requires_its_own_completion():
    observer = CodexObserver(lambda *_: None)
    observer.consume({"type": "turn.completed"})
    observer.consume({"type": "turn.started"})
    assert not observer.successful


async def test_adapter_completes_recovered_user_transcript_with_warning(tmp_path):
    transcript = [
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "rg --files", "exit_code": 1},
        },
        {"type": "item.completed", "item": {"type": "file_change", "status": "completed"}},
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "python3 -m unittest -v",
                "exit_code": 0,
            },
        },
        {"type": "turn.completed"},
    ]
    cli = fake_cli(tmp_path, f"for row in {transcript!r}: print(json.dumps(row), flush=True)\n")
    result = await CodexAdapter(cli).run("task", tmp_path, lambda *_: None)
    assert result.success
    assert "warnings" in result.reason


async def test_shell_file_edits_are_observed_as_coding(tmp_path):
    body = (
        "from pathlib import Path\n"
        "workspace = Path(sys.argv[sys.argv.index('-C') + 1])\n"
        "(workspace / 'feature.py').write_text('def ready(): return True\\n')\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'command_execution',"
        "'command':'python3 -c PRIVATE','exit_code':0}}), flush=True)\n"
        "print(json.dumps({'type':'turn.completed'}), flush=True)\n"
    )
    events = []
    result = await CodexAdapter(fake_cli(tmp_path, body)).run(
        "task", tmp_path, lambda kind, detail: events.append((kind, detail))
    )
    assert result.success
    assert (EventType.CODING, "CLI wrote code files · 1 changes") in events
    assert "PRIVATE" not in repr(events)


async def test_runtime_files_are_not_invented_coding_activity(tmp_path):
    body = (
        "from pathlib import Path\n"
        "workspace = Path(sys.argv[sys.argv.index('-C') + 1])\n"
        "(workspace / '.cafe' / 'tool-state.json').write_text('{}')\n"
        "print(json.dumps({'type':'item.completed','item':{'type':'command_execution',"
        "'command':'ls','exit_code':0}}), flush=True)\n"
        "print(json.dumps({'type':'turn.completed'}), flush=True)\n"
    )
    events = []
    await CodexAdapter(fake_cli(tmp_path, body)).run(
        "task", tmp_path, lambda kind, detail: events.append((kind, detail))
    )
    assert EventType.CODING not in [kind for kind, _ in events]


async def test_failed_collection_has_actionable_private_evidence(tmp_path):
    transcript = [
        {"type": "turn.started"},
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "python -m pytest",
                "exit_code": 2,
                "aggregated_output": (
                    "ModuleNotFoundError: SECRET\nERROR tests/test_api.py - SECRET\n"
                ),
            },
        },
        {"type": "turn.completed"},
    ]
    events = []
    cli = fake_cli(tmp_path, f"for row in {transcript!r}: print(json.dumps(row), flush=True)\n")
    result = await CodexAdapter(cli).run("task", tmp_path, lambda *e: events.append(e))
    assert not result.success
    assert "exit 2" in result.reason
    assert "collection/import" in result.reason
    assert "ModuleNotFoundError" in result.reason
    assert result.test_runs[0]["tests"] == ["tests/test_api.py"]
    assert "SECRET" not in repr(result) + repr(events)
    assert "test_api.py" not in repr(events)


def test_diagnostics_remove_assertion_values_and_keep_rerun_history():
    observer = CodexObserver(lambda *_: None)
    for code in (1, 0):
        observer.consume(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "pytest",
                    "exit_code": code,
                    "aggregated_output": (
                        "FAILED tests/test_auth.py::test_login[SECRET] - AssertionError: SECRET"
                        if code
                        else "1 passed"
                    ),
                },
            }
        )
    observer.consume({"type": "turn.completed"})
    assert observer.successful
    assert not observer.failed_diagnostics
    assert [run["passed"] for run in observer.test_runs] == [False, True]
    assert observer.test_runs[0]["tests"] == ["tests/test_auth.py::test_login"]
    assert "SECRET" not in repr(observer.test_runs)

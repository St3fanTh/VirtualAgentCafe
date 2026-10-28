import asyncio

import pytest
from fastapi.testclient import TestClient

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.execution import ExecutionManager
from virtual_agent_cafe.models import EventType


class ControlledRuntime:
    def __init__(self, success=True):
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.contexts = []
        self.success = success

    async def run(self, prompt, workspace, emit):
        self.contexts.append(prompt)
        self.started.set()
        emit(EventType.CODING, "Editing code")
        await self.release.wait()
        (workspace / "result.txt").write_text("changed")
        response = workspace / ".cafe" / "last-response.md"
        response.parent.mkdir(exist_ok=True)
        response.write_text("## Recap\nImplemented the API and pushed the tested change.")
        emit(EventType.TESTING, "CLI: pytest · PASS (exit 0)")
        return RunResult(
            self.success,
            "Runtime completed" if self.success else "Tests failed",
            ({"tool": "pytest", "exit_code": 0, "passed": True, "causes": [], "tests": []},),
        )


def configured(tmp_path, runtime):
    manager = ExecutionManager(tmp_path, EventBus(), runtime)
    manager.workspaces.create("project")
    manager.tasks.save("task.md", "# Task\n## Acceptance Criteria\nTests pass.")
    manager.roles.save("backend.md", "# Backend\nUse existing architecture.")
    manager.configure(
        AgentConfig(
            id="backend-agent",
            name="Backend",
            workspace="project",
            task="task.md",
            roles=["backend.md"],
        )
    )
    return manager


async def completed(manager):
    for _ in range(100):
        if not manager.running:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("Runtime did not complete")


async def test_lifecycle_context_snapshot_logs_and_separate_acceptance(tmp_path):
    runtime = ControlledRuntime()
    manager = configured(tmp_path, runtime)
    run = await manager.start("backend-agent")
    await runtime.started.wait()
    with pytest.raises(ValueError):
        await manager.start("backend-agent")
    assert manager.registry.get("backend-agent")["state"] == "RUNNING"
    manager.tasks.save("task.md", "# Replacement task\nNew objective.")
    assert "Replacement" not in runtime.contexts[0]
    assert "SYSTEM SECURITY" in runtime.contexts[0]
    assert "Use existing architecture" in runtime.contexts[0]
    runtime.release.set()
    await completed(manager)
    result = manager.store.get("executions", run["id"])
    assert result["status"] == "COMPLETED"
    assert result["acceptance"] == "UNVERIFIED"
    assert result["task_state"] != "COMPLETED"
    assert "Implemented the API" in result["changelog"]
    assert result["test_runs"][0]["tool"] == "pytest"
    assert len(manager.store.logs(run["id"])) >= 3
    manager.review(run["id"], True, "Reviewed generated changes and tests")
    assert manager.registry.get("backend-agent")["task_state"] == "ASSIGNED"
    # Accepting an old execution must not accept instructions edited during that run.
    restarted = ExecutionManager(tmp_path, EventBus(), runtime)
    assert restarted.store.get("executions", run["id"])["acceptance"] == "ACCEPTED"
    assert restarted.store.get("executions", run["id"])["test_runs"] == result["test_runs"]
    assert (manager.workspaces.get("project") / "result.txt").read_text() == "changed"


async def test_shared_workspace_lock_cancellation_and_independent_parallelism(tmp_path):
    runtime = ControlledRuntime()
    manager = configured(tmp_path, runtime)
    manager.configure(
        AgentConfig(id="other-agent", name="Other", workspace="project", task="task.md")
    )
    await manager.start("backend-agent")
    with pytest.raises(ValueError, match="Workspace"):
        await manager.start("other-agent")
    manager.workspaces.create("isolated")
    manager.configure(
        AgentConfig(id="other-agent", name="Other", workspace="isolated", task="task.md")
    )
    await manager.start("other-agent")
    assert len(manager.running) == 2
    await manager.stop("backend-agent")
    await manager.stop("other-agent")
    assert not manager.claims
    assert manager.registry.get("backend-agent")["state"] == "CANCELLED"
    assert manager.registry.get("other-agent")["state"] == "CANCELLED"


async def test_failure_timeout_and_restart_recovery(tmp_path):
    runtime = ControlledRuntime(success=False)
    runtime.release.set()
    manager = configured(tmp_path, runtime)
    run = await manager.start("backend-agent")
    await completed(manager)
    assert manager.store.get("executions", run["id"])["status"] == "FAILED"
    with pytest.raises(ValueError):
        manager.review(run["id"], True, "Cannot accept failed runtime")
    runtime.release.clear()
    runtime.started.clear()
    record = manager.registry.get("backend-agent")["config"]
    record["execution"]["timeout_seconds"] = 1
    manager.configure(AgentConfig.model_validate(record))
    run = await manager.start("backend-agent")
    async with asyncio.timeout(5):
        await runtime.started.wait()
        await manager.running["backend-agent"]
    assert manager.store.get("executions", run["id"])["detail"] == "Execution timed out"
    manager.store.put("executions", "interrupted", {**run, "id": "interrupted"})
    manager.registry.update("backend-agent", state="RUNNING")
    manager.store.put(
        "projects", "project", {"id": "project", "integration": {"status": "REPAIRING"}}
    )
    restarted = ExecutionManager(tmp_path, EventBus(), runtime)
    assert restarted.store.get("executions", "interrupted")["status"] == "FAILED"
    assert restarted.registry.get("backend-agent")["state"] == "FAILED"
    assert restarted.store.get("projects", "project")["integration"]["status"] == "INTERRUPTED"


def test_management_api_editable_assignments_security_and_persistence(tmp_path):
    root = tmp_path / "management"
    app = create_app("codex", management_root=root)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + app.state.management.access.token
        assert client.post("/management/workspaces", json={"id": "project"}).status_code == 201
        for kind, file in [("tasks", "task.md"), ("roles", "backend.md")]:
            assert (
                client.put(
                    f"/management/definitions/{kind}/{file}",
                    json={"content": "# Instructions\nWrite tests."},
                ).status_code
                == 200
            )
        assert (
            client.post(
                "/management/workspaces/project/git", json={"operation": "init"}
            ).status_code
            == 200
        )
        remote = client.post(
            "/management/workspaces/project/git",
            json={
                "operation": "remote",
                "remote_name": "team",
                "remote": "git@example.com:team/project.git",
            },
        )
        assert remote.status_code == 200
        assert remote.json()["remotes"] == ["team"]
        config = {
            "id": "backend-agent",
            "name": "Backend",
            "workspace": "project",
            "task": "task.md",
            "roles": ["backend.md"],
        }
        assert client.post("/management/agents", json=config).status_code == 201
        assert client.post("/management/agents", json=config).status_code == 409
        config["name"] = "Updated Backend"
        assert client.put("/management/agents/backend-agent", json=config).status_code == 200
        assert client.post("/management/workspaces", json={"id": "../escape"}).status_code == 422
        assert (
            client.post(
                "/management/workspaces",
                json={"id": "blocked"},
                headers={"Origin": "https://evil.test"},
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/management/workspaces/project/git", json={"operation": "reset"}
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/management/workspaces/project/git",
                json={"operation": "clone", "remote": "git@example.com:project.git"},
            ).status_code
            == 409
        )
    restarted_app = create_app("codex", management_root=root)
    with TestClient(restarted_app) as client:
        assert client.get("/management").status_code == 401
        client.headers["Authorization"] = "Bearer " + restarted_app.state.management.access.token
        overview = client.get("/management").json()
        assert overview["agents"][0]["config"]["name"] == "Updated Backend"
        assert overview["tasks"][0]["content"].startswith("# Instructions")


class GitHelperRuntime:
    async def run(self, prompt, workspace, emit):
        from virtual_agent_cafe.management.sandbox import Sandbox

        sandbox = Sandbox()
        (workspace / "feature.py").write_text("def feature():\n    return 'implemented'\n")
        for operation in [
            ["branch", "agent/backend-agent/feature"],
            ["stage", "feature.py"],
            ["commit", "feat: implement feature"],
        ]:
            process = await asyncio.create_subprocess_exec(
                *sandbox.command(
                    workspace, ["python3", ".cafe/git.py", *operation], writable_git=False
                ),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            output, error = await process.communicate()
            assert process.returncode == 0, (output + error).decode()
        return RunResult(True, "Git helper completed")


async def test_runtime_git_helper_commits_only_assigned_branch(tmp_path):
    manager = configured(tmp_path, GitHelperRuntime())
    await manager.git.init("project")
    (manager.workspaces.get("project") / "readme.md").write_text("# Project")
    await manager.git.stage("project", ["readme.md"])
    await manager.git.commit("project", "feat: initial project")
    manager.workspaces.create("backend")
    record = manager.registry.get("backend-agent")["config"]
    record.update(workspace="backend", git={"enabled": True, "repository": "project"})
    manager.configure(AgentConfig.model_validate(record))
    run = await manager.start("backend-agent")
    for _ in range(200):
        if not manager.running:
            break
        await asyncio.sleep(0.02)
    result = manager.store.get("executions", run["id"])
    assert result["status"] == "COMPLETED", result
    assert result["branch"] == "agent/backend-agent/feature"
    assert manager.registry.get("backend-agent")["branch"] == result["branch"]
    assert len((await manager.git.info("backend"))["history"]) == 2
    assert len((await manager.git.info("project"))["history"]) == 1
    assert any("Git: commit" in log["detail"] for log in manager.store.logs(run["id"]))
    for sensitive in [".env", ".cafe/git.py", "private.key"]:
        with pytest.raises(ValueError):
            await manager.git.stage("backend", [sensitive])


async def test_unavailable_isolation_fails_before_runtime_and_git(tmp_path):
    runtime = ControlledRuntime()
    manager = configured(tmp_path, runtime)

    async def unavailable(_workspace):
        raise ValueError("Filesystem isolation unavailable")

    manager.sandbox.validate = unavailable
    with pytest.raises(ValueError, match="isolation"):
        await manager.start("backend-agent")
    assert not manager.running
    assert not runtime.contexts
    assert manager.registry.get("backend-agent")["state"] == "CONFIGURED"


def test_managed_worker_cannot_use_management_or_legacy_api_without_token(tmp_path):
    runtime = ControlledRuntime()
    root = tmp_path / "management"
    app = create_app("codex", management_root=root, managed_adapter=runtime)
    manager = app.state.management
    manager.workspaces.create("project")
    manager.tasks.save("task.md", "# Task\nWait for review.")
    manager.configure(AgentConfig(id="agent", name="Agent", workspace="project", task="task.md"))
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + manager.access.token
        response = client.post("/management/agents/agent/start", json={})
        assert response.status_code == 202
        del client.headers["Authorization"]
        assert client.get("/management").status_code == 401
        assert (
            client.post("/agents/ada/tasks", json={"prompt": "Attempt legacy bypass"}).status_code
            == 401
        )
        assert (
            client.post(
                "/agents/ada/messages", json={"recipient": "turing", "text": "Bypass"}
            ).status_code
            == 401
        )
        client.headers["Authorization"] = "Bearer " + manager.access.token
        assert client.post("/management/agents/agent/stop", json={}).status_code == 202
        assert client.post("/management/agents/agent/restart", json={}).status_code == 202
        assert client.post("/management/agents/agent/stop", json={}).status_code == 202


def test_second_controller_cannot_recover_or_corrupt_active_store(tmp_path):
    root = tmp_path / "management"
    first = create_app("codex", management_root=root)
    second = create_app("codex", management_root=root)
    with TestClient(first):
        with pytest.raises(RuntimeError, match="Another controller"):
            with TestClient(second):
                pass
    # Graceful shutdown releases the lock for the next backend instance.
    with TestClient(second) as client:
        assert client.get("/health").status_code == 200


async def test_large_role_assignments_fit_realtime_snapshot_budget(tmp_path):
    import json

    runtime = ControlledRuntime()
    manager = configured(tmp_path, runtime)
    names = []
    for index in range(16):
        name = f"role-{index:02d}-" + "x" * 48 + ".md"
        manager.roles.save(name, "# Role\nFollow the system security policy.")
        names.append(name)
    config = manager.registry.get("backend-agent")["config"]
    config["roles"] = names
    manager.configure(AgentConfig.model_validate(config))
    await manager.start("backend-agent")
    snapshot = manager.bus.snapshot()
    assert len(json.dumps(snapshot).encode()) < 65536
    assert len(snapshot["agents"][-1]["role"]) <= 120
    assert len(manager.registry.get("backend-agent")["config"]["roles"]) == 16
    await manager.close()


async def test_git_start_failure_is_visible_and_persisted(tmp_path, monkeypatch):
    from virtual_agent_cafe.management.git import GitOperationError

    runtime = ControlledRuntime()
    manager = configured(tmp_path, runtime)
    config = manager.registry.get("backend-agent")["config"]
    config["git"] = {"enabled": True, "repository": "project", "worktree": False}
    manager.configure(AgentConfig.model_validate(config))

    async def fail(*args):
        raise GitOperationError("Git status failed. Workspace is not writable.")

    monkeypatch.setattr(manager.git, "repository", fail)
    with pytest.raises(GitOperationError):
        await manager.start("backend-agent")
    assert not runtime.started.is_set()
    assert manager.bus.agents["backend-agent"].status == EventType.ERROR
    assert not manager.running and not manager.claims
    restarted = ExecutionManager(tmp_path, EventBus(), runtime)
    assert restarted.registry.get("backend-agent")["state"] == "FAILED"
    assert restarted.bus.agents["backend-agent"].status == EventType.ERROR
    assert "not writable" in restarted.bus.agents["backend-agent"].detail
    assert restarted.tasks.load("task.md")["content"].startswith("# Task")
    assert restarted.roles.load("backend.md")["content"].startswith("# Backend")


async def test_private_chat_persists_and_is_loaded_on_resume(tmp_path):
    runtime = ControlledRuntime()
    manager = configured(tmp_path, runtime)
    message = "Use the documented contract. " + "x" * 3000
    saved = await manager.conversations.send("backend-agent", message, False)
    assert saved["delivery"] == "SAVED"
    assert saved["messages"][-1]["content"] == message
    runtime.release.set()
    response = await manager.conversations.send("backend-agent", "Please continue.", True)
    assert response["delivery"] == "STARTED"
    await completed(manager)
    assert message in runtime.contexts[-1]
    assert "Please continue." in runtime.contexts[-1]
    history = manager.conversations.read("backend-agent")
    assert history["messages"][-1]["role"] == "assistant"
    assert "Recap" in history["messages"][-1]["content"]
    restored = ExecutionManager(tmp_path, EventBus(), runtime)
    assert restored.conversations.read("backend-agent") == history
    for run in manager.store.list("executions"):
        assert message not in str(manager.store.logs(run["id"]))


async def test_chat_during_runtime_is_saved_for_next_attempt_without_duplicate_start(tmp_path):
    runtime = ControlledRuntime()
    manager = configured(tmp_path, runtime)
    await manager.start("backend-agent")
    await runtime.started.wait()
    reply = await manager.conversations.send("backend-agent", "New clarification", True)
    assert reply["delivery"] == "NEXT_ATTEMPT"
    assert len(manager.running) == 1
    assert "New clarification" not in runtime.contexts[0]
    runtime.release.set()
    await completed(manager)
    await manager.start("backend-agent")
    await completed(manager)
    assert "New clarification" in runtime.contexts[-1]


def test_chat_api_auth_validation_and_private_history(tmp_path):
    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    manager.workspaces.create("project")
    manager.configure(AgentConfig(id="agent", name="Agent", workspace="project"))
    url = "/management/agents/agent/chat"
    with TestClient(app) as client:
        assert client.get(url).status_code == 401
        client.headers["Authorization"] = "Bearer " + manager.access.token
        assert client.post(url, json={"content": "   ", "resume": False}).status_code == 422
        assert client.post(url, json={"content": "x" * 4001}).status_code == 422
        assert (
            client.post(url, json={"content": "Private clarification", "resume": False}).status_code
            == 200
        )
        assert client.get(url).json()["messages"][0]["content"] == "Private clarification"
        assert client.get("/management/agents/missing/chat").status_code == 404

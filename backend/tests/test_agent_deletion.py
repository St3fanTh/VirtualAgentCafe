import asyncio

import pytest
from fastapi.testclient import TestClient

from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.execution import ExecutionManager


def agent(manager):
    manager.workspaces.create("project")
    manager.tasks.save("task.md", "# Task\nKeep the result files.")
    manager.roles.save("backend.md", "# Backend\nFollow the project requirements.")
    manager.configure(
        AgentConfig(
            id="backend-agent",
            name="Backend",
            workspace="project",
            task="task.md",
            roles=["backend.md"],
        )
    )
    return manager.workspaces.get("project")


async def test_deletion_survives_restart_preserves_files_git_and_history(tmp_path):
    manager = ExecutionManager(tmp_path, EventBus())
    workspace = agent(manager)
    await manager.git.init("project")
    (workspace / "result.txt").write_text("completed work")
    await manager.git.stage("project", ["result.txt"])
    await manager.git.commit("project", "feat: saved work")
    before = await manager.git.info("project")
    manager.store.put(
        "executions",
        "past-run",
        {"id": "past-run", "agent_id": "backend-agent", "status": "COMPLETED"},
    )
    manager.store.log("past-run", {"type": "agent.finished", "detail": "Completed"})
    queue = manager.bus.subscribe()
    queue.get_nowait()
    result = await manager.delete("backend-agent")
    assert result["deleted"]
    assert all(row["agent_id"] != "backend-agent" for row in queue.get_nowait()["agents"])
    restored = ExecutionManager(tmp_path, EventBus())
    assert not restored.store.list("agents")
    assert "backend-agent" not in restored.bus.agents
    assert restored.store.list("deleted_agents")[0]["agent"]["config"]["id"] == "backend-agent"
    assert (workspace / "result.txt").read_text() == "completed work"
    assert (await restored.git.info("project"))["history"] == before["history"]
    assert restored.tasks.load("task.md")["content"].startswith("# Task")
    assert restored.roles.load("backend.md")["content"].startswith("# Backend")
    assert restored.store.get("executions", "past-run")["status"] == "COMPLETED"
    assert restored.store.logs("past-run")[0]["detail"] == "Completed"
    with pytest.raises(KeyError):
        await restored.delete("backend-agent")
    with pytest.raises(ValueError, match="Built-in"):
        await restored.delete("ada")


async def test_running_agent_and_team_integrations_must_be_stopped(tmp_path):
    manager = ExecutionManager(tmp_path, EventBus())
    agent(manager)
    task = asyncio.create_task(asyncio.Event().wait())
    manager.running["backend-agent"] = task
    with pytest.raises(ValueError, match="Stop the agent"):
        await manager.delete("backend-agent")
    manager.running.pop("backend-agent")
    manager.store.put(
        "projects",
        "project",
        {
            "id": "project",
            "agents": ["backend-agent", "frontend-agent"],
            "integrator": "test-agent",
            "auto_integrate": True,
            "status": "READY",
        },
    )
    manager.integrations.running["project"] = task
    with pytest.raises(ValueError, match="Stop all team"):
        await manager.delete("backend-agent")
    manager.integrations.running.pop("project")
    manager.running["frontend-agent"] = task
    with pytest.raises(ValueError, match="Stop all team"):
        await manager.delete("backend-agent")
    manager.running.pop("frontend-agent")
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await manager.delete("backend-agent")
    project = manager.store.get("projects", "project")
    assert not project["auto_integrate"] and project["integration"]["status"] == "DISABLED"
    assert project["status"] == "INCOMPLETE"
    manager.integrations.schedule("frontend-agent")
    assert not manager.integrations.running


def test_delete_api_requires_auth_confirmation_and_rejects_browser_requests(tmp_path):
    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    agent(manager)
    headers = {"Authorization": "Bearer " + manager.access.token}
    with TestClient(app) as client:
        assert (
            client.request(
                "DELETE", "/management/agents/backend-agent", json={"confirmed": True}
            ).status_code
            == 401
        )
        for body in ({}, {"confirmed": False}):
            assert (
                client.request(
                    "DELETE", "/management/agents/backend-agent", headers=headers, json=body
                ).status_code
                == 422
            )
        assert (
            client.request(
                "DELETE",
                "/management/agents/backend-agent",
                headers={**headers, "Origin": "https://example.org"},
                json={"confirmed": True},
            ).status_code
            == 403
        )
        assert manager.registry.get("backend-agent")
        response = client.request(
            "DELETE", "/management/agents/backend-agent", headers=headers, json={"confirmed": True}
        )
        assert response.status_code == 200 and response.json()["deleted"]
        assert not client.get("/management", headers=headers).json()["agents"]
        assert (
            client.request(
                "DELETE", "/management/agents/missing", headers=headers, json={"confirmed": True}
            ).status_code
            == 404
        )


def test_task_and_workspace_delete_api_guards_and_file_behavior(tmp_path):
    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    workspace = agent(manager)
    (workspace / "keep.txt").write_text("workspace contents")
    headers = {"Authorization": "Bearer " + manager.access.token}
    with TestClient(app) as client:
        task_response = client.request(
            "DELETE",
            "/management/definitions/tasks/task.md",
            headers=headers,
            json={"confirmed": True},
        )
        workspace_response = client.request(
            "DELETE",
            "/management/workspaces/project",
            headers=headers,
            json={"confirmed": True},
        )
        assert task_response.status_code == 409
        assert "assigned" in task_response.json()["detail"]
        assert workspace_response.status_code == 409
        assert "assigned" in workspace_response.json()["detail"]
        missing_confirmation = client.request(
            "DELETE", "/management/workspaces/project", headers=headers, json={}
        )
        assert missing_confirmation.status_code == 422

        manager.configure(
            AgentConfig(
                id="backend-agent",
                name="Backend",
                workspace="project",
                task=None,
                roles=["backend.md"],
            )
        )
        task_response = client.request(
            "DELETE",
            "/management/definitions/tasks/task.md",
            headers=headers,
            json={"confirmed": True},
        )
        assert task_response.status_code == 200 and task_response.json()["deleted"]
        assert not (manager.tasks.files.root / "task.md").exists()

        assert (
            client.request(
                "DELETE",
                "/management/agents/backend-agent",
                headers=headers,
                json={"confirmed": True},
            ).status_code
            == 200
        )
        workspace_response = client.request(
            "DELETE",
            "/management/workspaces/project",
            headers=headers,
            json={"confirmed": True},
        )
        assert workspace_response.status_code == 200
        assert workspace_response.json()["files_preserved"]
        assert (workspace / "keep.txt").read_text() == "workspace contents"


@pytest.mark.parametrize("orphaned_project", [False, True])
def test_unregister_missing_workspace_directory_through_api(tmp_path, orphaned_project):
    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    manager.workspaces.create("stale")
    manager.workspaces.get("stale").rmdir()
    if orphaned_project:
        manager.store.put(
            "projects",
            "stale",
            {
                "id": "stale",
                "agents": ["deleted-backend", "deleted-frontend"],
                "integrator": "deleted-integration",
                "auto_integrate": False,
            },
        )
    manager.workspaces.create("preserved-worker")
    work = manager.workspaces.get("preserved-worker") / "uncommitted.txt"
    work.write_text("keep this work")
    headers = {"Authorization": "Bearer " + manager.access.token}
    with TestClient(app) as client:
        response = client.request(
            "DELETE", "/management/workspaces/stale", headers=headers, json={"confirmed": True}
        )
        assert response.status_code == 200
        assert response.json()["removed"]
        overview = client.get("/management", headers=headers).json()
        assert [w["id"] for w in overview["workspaces"]] == ["preserved-worker"]
        assert not overview["projects"]
    restored = ExecutionManager(tmp_path, EventBus())
    assert [w["id"] for w in restored.store.list("workspaces")] == ["preserved-worker"]
    assert bool(restored.store.list("deleted_projects")) == orphaned_project
    assert work.read_text() == "keep this work"


async def test_unregister_project_source_protects_members_and_integration(tmp_path):
    manager = ExecutionManager(tmp_path, EventBus())
    agent(manager)
    manager.workspaces.create("source")
    manager.store.put("projects", "source", {"id": "source", "agents": ["backend-agent"]})
    with pytest.raises(ValueError, match="Project still has agents"):
        await manager.delete_workspace("source")
    await manager.delete("backend-agent")
    running = asyncio.create_task(asyncio.Event().wait())
    manager.integrations.running["source"] = running
    try:
        with pytest.raises(ValueError, match="running integration"):
            await manager.delete_workspace("source")
        assert manager.store.get("workspaces", "source")
        assert manager.store.get("projects", "source")
    finally:
        manager.integrations.running.pop("source")
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)

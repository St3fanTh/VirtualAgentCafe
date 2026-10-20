import asyncio

import pytest
from fastapi.testclient import TestClient

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.execution import ExecutionManager


class Idle:
    async def run(self, prompt, workspace, emit):
        await asyncio.Event().wait()
        return RunResult(True, "unreachable")


def configured(manager):
    manager.workspaces.create("project")
    manager.tasks.save("backend.md", "# Backend\nImplement service")
    manager.roles.save("backend.md", "# Backend\nWrite tests")
    source = manager.workspaces.get("project")
    (source / "README.md").write_text("source project")
    return source


async def test_delete_project_removes_clean_worktrees_and_archives_history(tmp_path):
    manager = ExecutionManager(tmp_path, EventBus(), Idle())
    source = configured(manager)
    await manager.git.init("project")
    await manager.git.stage("project", ["README.md"])
    await manager.git.commit("project", "feat: source")
    worker = AgentConfig(
        id="project-backend",
        name="Backend",
        workspace="project-backend",
        task="backend.md",
        roles=["backend.md"],
        git={
            "enabled": True,
            "repository": "project",
            "branch": "agent/project-backend/implementation",
        },
    )
    manager.workspaces.create(worker.workspace)
    await manager.git.worktree("project", worker.workspace, worker.git.branch)
    manager.configure(worker)
    second = worker.model_copy(
        update={
            "id": "project-frontend",
            "name": "Frontend",
            "workspace": "project-frontend",
            "branch": "agent/project-frontend/implementation",
            "task": "frontend.md",
            "roles": ["frontend.md"],
            "git": worker.git.model_copy(
                update={"branch": "agent/project-frontend/implementation"}
            ),
        }
    )
    manager.tasks.save("frontend.md", "# Frontend\nImplement view")
    manager.roles.save("frontend.md", "# Frontend\nWrite UI")
    manager.workspaces.create(second.workspace)
    await manager.git.worktree("project", second.workspace, second.git.branch)
    manager.configure(second)
    manager.store.put("projects", "project", {"id": "project", "agents": [worker.id, second.id]})
    manager.store.put("executions", "run-1", {"id": "run-1", "agent_id": worker.id})
    result = await manager.delete_project("project")
    assert result["deleted"] and (source / "README.md").read_text() == "source project"
    assert not manager.store.list("projects") and not manager.store.list("agents")
    archived = manager.store.list("deleted_projects")[0]
    assert archived["project"]["id"] == "project"
    assert manager.store.get("executions", "run-1")["agent_id"] == worker.id
    assert not manager.workspaces.files.path(worker.workspace).exists()
    assert not manager.workspaces.files.path(second.workspace).exists()
    assert {workspace["id"] for workspace in manager.store.list("workspaces")} == {"project"}
    assert "refs/heads/agent/project-backend/implementation" in (
        await manager.git.run(source, "for-each-ref", "--format=%(refname)", "refs/heads/")
    )


async def test_delete_project_refuses_dirty_or_running_worktrees(tmp_path):
    manager = ExecutionManager(tmp_path, EventBus(), Idle())
    configured(manager)
    await manager.git.init("project")
    source = manager.workspaces.get("project")
    (source / "README.md").write_text("source")
    await manager.git.stage("project", ["README.md"])
    await manager.git.commit("project", "feat: source")
    worker = AgentConfig(
        id="project-backend",
        name="Backend",
        workspace="project-backend",
        task="backend.md",
        roles=["backend.md"],
        git={
            "enabled": True,
            "repository": "project",
            "branch": "agent/project-backend/implementation",
        },
    )
    manager.workspaces.create(worker.workspace)
    worktree = await manager.git.worktree("project", worker.workspace, worker.git.branch)
    manager.configure(worker)
    manager.store.put("projects", "project", {"id": "project", "agents": [worker.id]})
    (worktree / "uncommitted.txt").write_text("keep")
    with pytest.raises(ValueError, match="Commit or resolve"):
        await manager.delete_project("project")
    assert (worktree / "uncommitted.txt").exists()
    (worktree / "uncommitted.txt").unlink()
    running = asyncio.create_task(asyncio.Event().wait())
    manager.running[worker.id] = running
    with pytest.raises(ValueError, match="Stop all project"):
        await manager.delete_project("project")
    manager.running.pop(worker.id)
    running.cancel()
    await asyncio.gather(running, return_exceptions=True)


def test_project_delete_api_requires_confirmation_and_exact_all_project_list(tmp_path):
    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    configured(manager)
    manager.store.put("projects", "project", {"id": "project", "agents": []})
    headers = {"Authorization": "Bearer " + manager.access.token}
    with TestClient(app) as client:
        assert (
            client.request(
                "DELETE", "/management/projects/project", headers=headers, json={}
            ).status_code
            == 422
        )
        assert (
            client.request(
                "DELETE",
                "/management/projects",
                headers=headers,
                json={"confirmed": True, "project_ids": []},
            ).status_code
            == 409
        )
        response = client.request(
            "DELETE",
            "/management/projects/project",
            headers=headers,
            json={"confirmed": True},
        )
        assert response.status_code == 200 and response.json()["deleted"]

"""Publication uses real temporary Git repositories, with local-only transport."""

import pytest
from pydantic import ValidationError

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.management.config import AgentConfig, GitConfig
from virtual_agent_cafe.management.execution import ExecutionManager


async def publication_project(tmp_path, monkeypatch):
    monkeypatch.setenv("VAC_ALLOW_REMOTE_GIT", "1")
    manager = ExecutionManager(tmp_path / "management", EventBus())
    manager.workspaces.create("project")
    manager.workspaces.create("remote")
    path = manager.workspaces.get("project")
    remote = manager.workspaces.get("remote")
    git = manager.git
    await git.init("project")
    await git.run(remote, "init", "--bare", "-q")
    (path / "README.md").write_text("# Original\n")
    await git.stage("project", ["README.md"])
    await git.commit("project", "feat: initial")
    await git.branch("project", "agent/backend-agent/task")
    await git.set_remote("project", "origin", "git@example.org:team/project.git")
    manager.tasks.save("task.md", "# Task\nCreate and commit a tested result.")
    config = AgentConfig(
        id="backend-agent",
        name="Backend",
        workspace="project",
        task="task.md",
        git=GitConfig(
            enabled=True,
            repository="project",
            worktree=False,
            allow_push=True,
            push_on_success=True,
        ),
    )
    manager.configure(config)
    original = git.run
    commands = []

    async def local_transport(path, *arguments, **kwargs):
        if "push" in arguments:
            commands.append(arguments)
            # Only the transport is replaced: run real Git push inside the same
            # namespace against an explicitly mounted temporary bare repository.
            offset = arguments.index("push")
            arguments = (
                *arguments[:offset],
                "-c",
                "protocol.file.allow=always",
                *arguments[offset:-2],
                str(remote),
                arguments[-1],
            )
            kwargs["extra_mounts"] = (remote,)
        return await original(path, *arguments, **kwargs)

    monkeypatch.setattr(git, "run", local_transport)
    return manager, config, path, remote, commands


async def test_successful_worker_commits_and_pushes_own_branch(tmp_path, monkeypatch):
    manager, config, path, remote, commands = await publication_project(tmp_path, monkeypatch)

    class Runtime:
        async def run(self, context, workspace, emit):
            assert "PUBLICATION AUTHORIZED" in context
            (workspace / "result.txt").write_text("tested result")
            await manager.git.stage("project", ["result.txt"])
            await manager.git.commit("project", "feat: tested worker result")
            return RunResult(True, "Tests passed")

    manager.adapter = Runtime()
    run = await manager.start(config.id)
    await manager.running[config.id]
    result = manager.store.get("executions", run["id"])
    assert result["publication"] == "PUSHED"
    assert result["status"] == "COMPLETED"
    assert result["acceptance"] == "UNVERIFIED"
    ref = "refs/heads/agent/backend-agent/task"
    assert await manager.git.run(remote, "show", f"{ref}:result.txt") == "tested result"
    assert "refs/heads/main" not in await manager.git.run(remote, "show-ref")
    assert len(commands) == 1
    assert commands[0][-1] == f"HEAD:{ref}"
    assert not any(arg in {"--force", "--mirror", "--all", "--tags"} for arg in commands[0])
    restarted = ExecutionManager(manager.contexts.root.parent, EventBus())
    assert restarted.store.get("executions", run["id"])["publication"] == "PUSHED"
    assert (path / "result.txt").read_text() == "tested result"


async def test_uncommitted_worker_results_are_preserved_and_not_claimed_as_pushed(
    tmp_path, monkeypatch
):
    manager, config, path, _, commands = await publication_project(tmp_path, monkeypatch)

    class Runtime:
        async def run(self, context, workspace, emit):
            (workspace / "result.txt").write_text("uncommitted result")
            return RunResult(True, "Process finished")

    manager.adapter = Runtime()
    run = await manager.start(config.id)
    await manager.running[config.id]
    result = manager.store.get("executions", run["id"])
    assert result["runtime_success"] is True
    assert result["status"] == "FAILED" and result["publication"] == "FAILED"
    assert "not fully committed" in result["detail"]
    assert (path / "result.txt").read_text() == "uncommitted result"
    assert not commands


async def test_publication_requires_permissions_own_branch_and_safe_remote(tmp_path, monkeypatch):
    manager, config, path, _, commands = await publication_project(tmp_path, monkeypatch)
    config.git.allow_push = False
    with pytest.raises(ValueError, match="permission"):
        await manager.git.push(config)
    config.git.allow_push = True
    monkeypatch.setenv("VAC_ALLOW_REMOTE_GIT", "0")
    with pytest.raises(ValueError, match="opt-in"):
        await manager.git.push(config)
    monkeypatch.setenv("VAC_ALLOW_REMOTE_GIT", "1")
    await manager.git.branch("project", "main", create=False)
    with pytest.raises(ValueError, match="own branch"):
        await manager.git.push(config)
    await manager.git.branch("project", "agent/backend-agent/task", create=False)
    await manager.git.run(
        path, "remote", "set-url", "--push", "origin", "https://secret@example.org/repo"
    )
    with pytest.raises(ValueError, match="credential-free"):
        await manager.git.push(config)
    assert not commands
    with pytest.raises(ValidationError):
        GitConfig(push_on_success=True)


async def test_remote_divergence_rejects_push_and_preserves_both_versions(tmp_path, monkeypatch):
    manager, config, path, remote, commands = await publication_project(tmp_path, monkeypatch)
    await manager.git.push(config)
    manager.workspaces.create("peer")
    peer = await manager.git.worktree("project", "peer", "agent/peer/change")
    (peer / "peer.txt").write_text("remote work must survive")
    await manager.git.stage("peer", ["peer.txt"])
    await manager.git.commit("peer", "feat: competing remote work")
    remote_head = (await manager.git.run(peer, "rev-parse", "HEAD")).strip()
    # Bare-repository fixture simulates a second writer publishing ahead of us.
    ref = "refs/heads/agent/backend-agent/task"
    await manager.git.run(peer, "push", "origin", f"HEAD:{ref}")
    (path / "local.txt").write_text("local work must survive")
    await manager.git.stage("project", ["local.txt"])
    await manager.git.commit("project", "feat: local work")
    with pytest.raises(ValueError, match="Git push failed"):
        await manager.git.push(config)
    assert (await manager.git.run(remote, "rev-parse", ref)).strip() == remote_head
    assert await manager.git.run(remote, "show", f"{ref}:peer.txt") == "remote work must survive"
    assert (path / "local.txt").read_text() == "local work must survive"
    assert len(commands) == 3

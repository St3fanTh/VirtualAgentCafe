import asyncio

import pytest

from virtual_agent_cafe.management.files import WorkspaceManager
from virtual_agent_cafe.management.git import GitService
from virtual_agent_cafe.management.sandbox import Sandbox, bubblewrap
from virtual_agent_cafe.management.storage import Store


async def test_git_init_commit_branches_worktrees_and_path_validation(tmp_path):
    workspaces = WorkspaceManager(tmp_path / "workspaces", Store(tmp_path))
    project = workspaces.create("project")
    git = GitService(workspaces)
    assert (await git.init("project"))["branch"] == "main"
    path = workspaces.get("project")
    (path / "readme.md").write_text("# Project\n")
    await git.stage("project", ["readme.md"])
    assert (await git.commit("project", "feat: initial project"))["history"]
    workspaces.create("frontend")
    workspaces.create("backend")
    front, back = await asyncio.gather(
        git.worktree("project", "frontend", "agent/frontend/task"),
        git.worktree("project", "backend", "agent/backend/task"),
    )
    assert front != back
    (front / "readme.md").write_text("# Frontend\n")
    assert "Frontend" in await git.diff("frontend")
    assert (back / "readme.md").read_text() == "# Project\n"
    await git.stage("frontend", ["readme.md"])
    await git.commit("frontend", "feat: frontend")
    assert len((await git.info("frontend"))["history"]) == 2
    assert len((await git.info("backend"))["history"]) == 1
    assert await git.worktree("project", "frontend", "agent/frontend/task") == front
    await git.branch("backend", "agent/backend/next")
    await git.branch("backend", "agent/backend/task", create=False)
    for malicious in ["../../secret", "/etc/passwd", ":(glob)**", ".git/config"]:
        with pytest.raises(ValueError):
            await git.stage("frontend", [malicious])
    with pytest.raises(ValueError):
        await git.branch("project", "--force")
    with pytest.raises(ValueError):
        await git.clone("project", "ext::sh -c bad")
    assert project["id"] == "project"


async def test_real_filesystem_isolation_hides_host_and_peer_workspaces(tmp_path):
    try:
        bubblewrap()
    except ValueError as error:
        pytest.skip(str(error))
    workspace = tmp_path / "assigned"
    peer = tmp_path / "peer"
    workspace.mkdir()
    peer.mkdir()
    secret = peer / "private.txt"
    secret.write_text("private")
    sandbox = Sandbox()
    try:
        await sandbox.validate(workspace)
    except ValueError as error:
        pytest.skip(str(error))
    script = (
        "from pathlib import Path; "
        f"assert not Path({str(secret)!r}).exists(); "
        "assert not Path('/workspace/AGENTS.md').exists(); "
        "assert not Path('/home/node/.codex/auth.json').exists(); "
        "assert not Path('/run/docker.sock').exists(); "
        f"Path({str(workspace / 'result.txt')!r}).write_text('isolated')"
    )
    process = await asyncio.create_subprocess_exec(
        *sandbox.command(workspace, ["/usr/bin/python3", "-c", script], network=False)
    )
    assert await process.wait() == 0
    assert (workspace / "result.txt").read_text() == "isolated"
    assert secret.read_text() == "private"


async def test_runtime_readonly_git_metadata_and_markdown_mounts(tmp_path):
    workspace = tmp_path / "assigned"
    instructions = tmp_path / "private-context"
    workspace.mkdir()
    (workspace / ".git").mkdir()
    (workspace / ".git" / "config").write_text("original")
    instructions.mkdir()
    (instructions / "task.md").write_text("# Exact task")
    sandbox = Sandbox()
    program = (
        "from pathlib import Path; "
        f"task = Path({str(workspace / '.cafe/instructions/task.md')!r}); "
        "assert task.read_text() == '# Exact task'; "
        f"config = Path({str(workspace / '.git/config')!r}); "
        "\nfor path in (task, config):\n"
        "    try: path.write_text('escape')\n"
        "    except OSError: pass\n"
        "    else: raise AssertionError('readonly mount was writable')\n"
    )
    process = await asyncio.create_subprocess_exec(
        *sandbox.command(
            workspace,
            ["/usr/bin/python3", "-c", program],
            network=False,
            writable_git=False,
            instructions=instructions,
        )
    )
    assert await process.wait() == 0
    assert (instructions / "task.md").read_text() == "# Exact task"
    assert (workspace / ".git/config").read_text() == "original"

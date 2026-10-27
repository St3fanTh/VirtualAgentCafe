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
    for malicious in ["../../secret", "/etc/passwd", ":(glob)**", ".git/config", "."]:
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


async def test_git_remotes_are_configurable_without_network_or_credentials(tmp_path):
    workspaces = WorkspaceManager(tmp_path / "workspaces", Store(tmp_path))
    workspaces.create("project")
    git = GitService(workspaces)
    await git.init("project")
    assert (await git.set_remote("project", "team", "git@example.com:team/project.git"))[
        "remotes"
    ] == ["team"]
    await git.set_remote("project", "team", "https://example.com/team/project.git")
    with pytest.raises(ValueError):
        await git.set_remote("project", "--force", "git@example.com:team/project.git")
    with pytest.raises(ValueError):
        await git.set_remote("project", "team", "https://user:secret@example.com/project.git")


async def test_approved_bind_mount_with_different_owner(tmp_path, monkeypatch):
    workspaces = WorkspaceManager(tmp_path / "workspaces", Store(tmp_path))
    workspaces.create("project")
    git = GitService(workspaces)
    await git.init("project")
    path = workspaces.get("project")
    (path / "README.md").write_text("# Host-owned repository\n")
    await git.stage("project", ["README.md"])
    await git.commit("project", "feat: initial host project")
    original = Sandbox.command

    def host_owned(self, workspace, command, **kwargs):
        return original(
            self,
            workspace,
            ["/usr/bin/env", "GIT_TEST_ASSUME_DIFFERENT_OWNER=1", *command],
            **kwargs,
        )

    monkeypatch.setattr(Sandbox, "command", host_owned)
    assert (await git.info("project"))["history"]
    workspaces.create("agent")
    await git.worktree("project", "agent", "agent/worker/task")
    assert (await git.info("agent"))["branch"] == "agent/worker/task"


async def test_branch_conflict_reports_operation_and_preserves_worktrees(tmp_path):
    workspaces = WorkspaceManager(tmp_path / "workspaces", Store(tmp_path))
    git = GitService(workspaces)
    for name in ("project", "first", "second"):
        workspaces.create(name)
    await git.init("project")
    source = workspaces.get("project")
    (source / "README.md").write_text("original")
    await git.stage("project", ["README.md"])
    await git.commit("project", "feat: initial")
    first = await git.worktree("project", "first", "agent/shared/task")
    (first / "unsaved.txt").write_text("keep this work")
    with pytest.raises(ValueError, match="Git worktree failed.*already assigned"):
        await git.worktree("project", "second", "agent/shared/task")
    assert (first / "unsaved.txt").read_text() == "keep this work"
    assert (source / "README.md").read_text() == "original"
    assert "secret" not in GitService.failure("fetch", "secret: authentication failed")


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("Permission denied (publickey). private@example.org", "Remote authentication failed"),
        ("No user exists for uid 1000", "SSH cannot resolve the sandbox user"),
        ("fatal: cannot open private/path: Permission denied", "not writable"),
        ("fatal: unable to create private/index.lock: File exists", "lock or destination conflict"),
        ("[rejected] secret-url (non-fast-forward)", "force-push is disabled"),
    ],
)
def test_git_diagnostics_distinguish_auth_filesystem_and_conflicts(stderr, expected):
    message = GitService.failure("push", stderr)
    assert expected in message
    assert "private" not in message and "secret-url" not in message


async def test_real_ssh_resolves_user_inside_git_sandbox(tmp_path):
    import subprocess

    sandbox = Sandbox()
    await sandbox.validate(tmp_path)
    command = sandbox.command(
        tmp_path,
        ["ssh", "-G", "-F", "/dev/null", "git@example.invalid"],
        ssh=True,
        network=False,
    )
    result = await asyncio.to_thread(
        subprocess.run, command, capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0, result.stderr
    assert "user git" in result.stdout
    # Account data is visible, but never writable; shadow and host homes stay hidden.
    script = (
        "import os,pwd; from pathlib import Path; "
        "assert pwd.getpwuid(os.getuid()); "
        "assert not Path('/etc/shadow').exists(); "
        "assert not Path('/home/node').exists(); "
        "assert not Path('/root').exists(); "
        "p=Path('/etc/passwd'); "
        "assert os.statvfs(p).f_flag & os.ST_RDONLY"
    )
    result = await asyncio.to_thread(
        subprocess.run,
        sandbox.command(tmp_path, ["python3", "-c", script], ssh=True, network=False),
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


async def test_empty_former_project_mount_has_actionable_git_read_errors(tmp_path):
    workspaces = WorkspaceManager(tmp_path / "workspaces", Store(tmp_path))
    workspaces.create("old-project")
    git = GitService(workspaces)
    for read in (git.info, git.diff):
        with pytest.raises(ValueError, match="Select the current agent worktree"):
            await read("old-project")


async def test_missing_worktree_registration_reports_recovery_without_deleting_data(tmp_path):
    import shutil

    workspaces = WorkspaceManager(tmp_path / "workspaces", Store(tmp_path))
    git = GitService(workspaces)
    for name in ("project", "worker"):
        workspaces.create(name)
    await git.init("project")
    source = workspaces.get("project")
    (source / "README.md").write_text("original")
    await git.stage("project", ["README.md"])
    await git.commit("project", "feat: initial")
    target = await git.worktree("project", "worker", "agent/worker/task")
    # Simulate loss of a mounted worktree while its source metadata remains.
    shutil.rmtree(target)
    workspaces.create("worker")
    with pytest.raises(ValueError, match="old Git worktree registration"):
        await git.worktree("project", "worker", "agent/worker/task")
    assert (source / "README.md").read_text() == "original"
    assert (source / ".git/worktrees/worker").is_dir()
    assert not any(target.iterdir())


async def test_targeted_prune_preserves_live_and_unrelated_registrations(tmp_path):
    import shutil

    workspaces = WorkspaceManager(tmp_path / "workspaces", Store(tmp_path))
    git = GitService(workspaces)
    workspaces.create("project")
    await git.init("project")
    source = workspaces.get("project")
    (source / "README.md").write_text("original")
    await git.stage("project", ["README.md"])
    await git.commit("project", "feat: initial")
    for name in ("lost", "live", "unrelated"):
        workspaces.create(name)
        await git.worktree("project", name, "agent/" + name + "/task")
    shutil.rmtree(workspaces.get("lost"))
    shutil.rmtree(workspaces.get("unrelated"))
    await git.remove_worktree("project", "lost")
    await git.prune_worktrees("project", ["lost", "live"])
    assert not (source / ".git/worktrees/lost").exists()
    assert (source / ".git/worktrees/unrelated").exists()
    assert (await git.info("live"))["branch"] == "agent/live/task"
    workspaces.create("lost")
    await git.worktree("project", "lost", "agent/lost/task")
    assert (await git.info("lost"))["branch"] == "agent/lost/task"

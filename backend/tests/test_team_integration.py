import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.management.execution import ExecutionManager
from virtual_agent_cafe.management.git import GitService
from virtual_agent_cafe.management.sandbox import Sandbox
from virtual_agent_cafe.management.setup import ProjectSetup, SetupInput


async def team(
    tmp_path,
    monkeypatch,
    *,
    fail_test=False,
    fail_worker=False,
    conflict=False,
    bad_plan=False,
    repair=False,
):
    monkeypatch.setenv("VAC_ALLOW_REMOTE_GIT", "1")
    manager = ExecutionManager(tmp_path / "controller", EventBus())
    for name in ("project", "remote"):
        manager.workspaces.create(name)
    git = manager.git
    source = manager.workspaces.get("project")
    remote = manager.workspaces.get("remote")
    await git.init("project")
    (source / "README.md").write_text("# Project\n")
    (source / "PLANNING.md").write_text(
        "# Requirements\nBackend and frontend must share an API contract.\n"
    )
    await git.stage("project", ["README.md", "PLANNING.md"])
    await git.commit("project", "feat: initial")
    await git.run(remote, "init", "--bare", "-q")
    await git.run(
        source,
        "-c",
        "protocol.file.allow=always",
        "push",
        str(remote),
        "HEAD:refs/heads/main",
        extra_mounts=(remote,),
    )
    initial = (await git.run(source, "rev-parse", "HEAD")).strip()
    await git.set_remote("project", "origin", "git@example.org:team/project.git")
    original = git.run
    pushed = []

    async def local_transport(path, *arguments, **kwargs):
        operation = GitService.operation(arguments)
        if operation in {"push", "fetch", "ls-remote"}:
            if operation == "push":
                pushed.append(arguments[-1])
            offset = arguments.index(operation)
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
    setup = ProjectSetup(manager, "codex")
    monkeypatch.setattr(setup, "command_ok", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "virtual_agent_cafe.management.setup.shutil",
        SimpleNamespace(which=lambda _: "/usr/bin/true"),
    )
    await setup.create(
        SetupInput(
            project="project",
            objective="Build and jointly test both components.",
            auto_integrate=True,
        )
    )

    class Runtime:
        def __init__(self):
            self.repair = repair

        async def run(self, context, workspace, emit):
            if workspace.name.endswith("integration"):
                data = manager.integrations.inputs[workspace.name]
                assert "Read .cafe/instructions/requirements.md" in context
                if conflict:
                    assert await git.merge_pending(workspace.name)
                    if not self.repair:
                        # A model success claim must not publish an unfinished merge.
                        return RunResult(True, "Claimed success without resolving conflicts")

                    async def helper(*args, accepted=True):
                        process = await asyncio.create_subprocess_exec(
                            *Sandbox().command(
                                workspace, ["python3", ".cafe/git.py", *args], writable_git=False
                            ),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        output, error = await process.communicate()
                        assert (process.returncode == 0) == accepted, (output + error).decode()

                    await helper("merge", "f" * 40, accepted=False)
                    await helper("switch", "agent/project-integration/other", accepted=False)
                    document = workspace / "docs/decisions.md"
                    assert "<<<<<<<" in document.read_text()
                    document.write_text("# Decisions\nBackend: fixed tick.\nFrontend: Godot.\n")
                    await helper("stage", "docs/decisions.md")
                    await helper("commit", "merge: reconcile component decisions")
                    for commit in data["commits"]:
                        await helper("merge", commit)

                assert (workspace / "backend.py").is_file() and (
                    workspace / "frontend.py"
                ).is_file()
                (workspace / "tests").mkdir(exist_ok=True)
                (workspace / "tests/test_contract.py").write_text(
                    "import backend, frontend\ndef test_contract():\n"
                    "    assert backend.VALUE == frontend.VALUE" + (" + 1\n" if fail_test else "\n")
                )
                (workspace / "validation").mkdir(exist_ok=True)
                (workspace / "validation/requirements.md").write_text(data["text"])
                (workspace / "validation/plan.json").write_text(
                    json.dumps(
                        {
                            "source_sha256": data["sha256"],
                            "requirements": [
                                {
                                    "id": "REQ-1",
                                    "description": "Backend and frontend use the same API contract",
                                    "checks": ["contract"],
                                }
                            ],
                            "checks": [
                                {
                                    "id": "contract",
                                    "kind": "shell" if bad_plan else "pytest",
                                    "directory": ".",
                                }
                            ],
                        }
                    )
                )
                files = [
                    "tests/test_contract.py",
                    "validation/plan.json",
                    "validation/requirements.md",
                ]
            else:
                role = "backend" if workspace.name.endswith("backend") else "frontend"
                if fail_worker and role == "backend":
                    return RunResult(False, "Backend tests failed")
                name = role + ".py"
                (workspace / name).write_text("VALUE = 1\n")
                files = [name]
                if conflict:
                    (workspace / "docs").mkdir(exist_ok=True)
                    (workspace / "docs/decisions.md").write_text("# " + role + " decisions\n")
                    files.append("docs/decisions.md")
            await git.stage(workspace.name, files)
            await git.commit(workspace.name, "feat: tested component")
            return RunResult(True, "Worker process finished")

    manager.adapter = Runtime()
    return manager, remote, initial, pushed


async def settle(manager):
    async with asyncio.timeout(30):
        while manager.running or manager.integrations.running:
            await asyncio.gather(
                *list(manager.running.values()), *list(manager.integrations.running.values())
            )


async def start_workers(manager):
    await manager.start("project-backend")
    await manager.start("project-frontend")
    await settle(manager)


async def test_complete_team_merges_runs_real_requirements_tests_and_promotes_main(
    tmp_path, monkeypatch
):
    manager, remote, initial, pushed = await team(tmp_path, monkeypatch)
    original_command = Sandbox.command
    ssh_flags = []

    def capture(self, workspace, command, **kwargs):
        if any(":refs/heads/" in part for part in command):
            ssh_flags.append(kwargs.get("ssh", False))
        return original_command(self, workspace, command, **kwargs)

    monkeypatch.setattr(Sandbox, "command", capture)
    await start_workers(manager)
    project = manager.store.get("projects", "project")
    assert project["integration"]["status"] == "PROMOTED", project
    assert ssh_flags and all(ssh_flags)
    run = manager.store.get("executions", project["integration"]["execution"])
    assert run["validation"]["passed"] and run["validation"]["checks"][0]["exit_code"] == 0
    assert run["acceptance"] == "AUTO_VALIDATED"
    head = (await manager.git.run(remote, "rev-parse", "refs/heads/main")).strip()
    assert head != initial and head == run["validation"]["commit"] == run["promoted"]["commit"]
    for path in (
        "backend.py",
        "frontend.py",
        "tests/test_contract.py",
        "validation/plan.json",
        "validation/requirements.md",
    ):
        assert await manager.git.run(remote, "show", f"refs/heads/main:{path}")
    assert len(pushed) == 4  # two workers, integration feature, exact tested main
    assert pushed[-1] == head + ":refs/heads/main"
    assert all(
        manager.registry.get(name)["task_state"] == "COMPLETED" for name in project["agents"]
    )
    count = len(manager.store.list("executions"))
    manager.integrations.schedule("project-backend")
    await settle(manager)
    assert len(manager.store.list("executions")) == count
    restored = ExecutionManager(manager.contexts.root.parent, EventBus())
    assert restored.store.get("projects", "project")["integration"]["status"] == "PROMOTED"


@pytest.mark.parametrize("failure", ["test", "worker", "conflict", "plan"])
async def test_failed_team_never_changes_main_and_preserves_worktrees(
    tmp_path, monkeypatch, failure
):
    manager, remote, initial, pushed = await team(
        tmp_path,
        monkeypatch,
        fail_test=failure == "test",
        fail_worker=failure == "worker",
        conflict=failure == "conflict",
        bad_plan=failure == "plan",
    )
    await start_workers(manager)
    project = manager.store.get("projects", "project")
    assert project["integration"]["status"] in {"FAILED", "WAITING_FOR_WORKERS"}
    assert (await manager.git.run(remote, "rev-parse", "refs/heads/main")).strip() == initial
    assert all(not ref.endswith(":refs/heads/main") for ref in pushed)
    assert manager.workspaces.get("project-frontend").exists()
    assert manager.workspaces.get("project-backend").exists()
    if failure == "test":
        run = manager.store.get("executions", project["integration"]["execution"])
        assert run["runtime_success"] is True and run["validation"]["passed"] is False
        assert run["acceptance"] == "VALIDATION_FAILED"


def test_ssh_forwarding_detects_git_operation_after_global_options():
    assert (
        GitService.operation(
            ("-c", "remote.origin.mirror=false", "-c", "push.followTags=false", "push", "origin")
        )
        == "push"
    )
    command = Sandbox().command(Path("/workspace"), ["git", "push"], ssh=False)
    assert "/run/ssh-agent" not in command


async def test_concurrent_remote_main_update_blocks_stale_promotion(tmp_path, monkeypatch):
    manager, remote, initial, pushed = await team(tmp_path, monkeypatch)
    original = manager.git.promote
    advanced = []

    async def concurrent_main(config, commit, base):
        manager.workspaces.create("concurrent")
        path = await manager.git.worktree("project", "concurrent", "agent/other/update")
        (path / "README.md").write_text("concurrent main update")
        await manager.git.stage("concurrent", ["README.md"])
        await manager.git.commit("concurrent", "feat: another main writer")
        await manager.git.run(path, "push", "origin", "HEAD:refs/heads/main")
        advanced.append((await manager.git.run(path, "rev-parse", "HEAD")).strip())
        return await original(config, commit, base)

    monkeypatch.setattr(manager.git, "promote", concurrent_main)
    await start_workers(manager)
    record = manager.store.get("projects", "project")
    assert record["integration"]["status"] == "FAILED"
    run = manager.store.get("executions", record["integration"]["execution"])
    assert run["validation"]["passed"] and run["promotion"] == "FAILED"
    assert "Remote main changed" in run["detail"]
    assert (await manager.git.run(remote, "rev-parse", "refs/heads/main")).strip() == advanced[0]
    assert advanced[0] != initial and advanced[0] != run["validation"]["commit"]


async def test_changed_task_cannot_be_promoted_using_stale_requirement_tests(tmp_path, monkeypatch):
    manager, remote, initial, _pushed = await team(tmp_path, monkeypatch)
    original = manager.git.push

    async def changed_requirements(config):
        result = await original(config)
        if config.execution.integration_validation:
            manager.tasks.save(
                "project-backend.md", "# Changed requirements\nImplement a new API contract."
            )
        return result

    monkeypatch.setattr(manager.git, "push", changed_requirements)
    await start_workers(manager)
    project = manager.store.get("projects", "project")
    assert project["integration"]["status"] == "FAILED"
    run = manager.store.get("executions", project["integration"]["execution"])
    assert run["validation"]["passed"]
    assert run["promotion"] == "FAILED" and "requirements changed" in run["detail"]
    assert (await manager.git.run(remote, "rev-parse", "refs/heads/main")).strip() == initial


async def test_simultaneous_worker_notifications_do_not_duplicate_failed_integration(
    tmp_path, monkeypatch
):
    manager, _remote, _initial, _pushed = await team(tmp_path, monkeypatch, fail_test=True)
    await start_workers(manager)
    before = len(manager.store.list("executions"))
    manager.integrations.schedule("project-backend")
    manager.integrations.schedule("project-frontend")
    await settle(manager)
    assert len(manager.store.list("executions")) == before + 1
    assert not manager.integrations.pending


async def test_conflicting_worker_docs_are_resolved_by_integration_before_promotion(
    tmp_path, monkeypatch
):
    manager, remote, initial, pushed = await team(tmp_path, monkeypatch, conflict=True, repair=True)
    await start_workers(manager)
    project = manager.store.get("projects", "project")
    assert project["integration"]["status"] == "PROMOTED", project
    run = manager.store.get("executions", project["integration"]["execution"])
    assert run["validation"]["passed"]
    assert "Backend: fixed tick" in await manager.git.run(remote, "show", "main:docs/decisions.md")
    assert "Frontend: Godot" in await manager.git.run(remote, "show", "main:docs/decisions.md")
    assert not await manager.git.merge_pending("project-integration")
    assert pushed[-1].endswith(":refs/heads/main")


async def test_retry_hands_preserved_conflict_back_to_integration_agent(tmp_path, monkeypatch):
    manager, remote, initial, _pushed = await team(tmp_path, monkeypatch, conflict=True)
    await start_workers(manager)
    assert manager.store.get("projects", "project")["integration"]["status"] == "FAILED"
    assert await manager.git.merge_pending("project-integration")
    assert (await manager.git.run(remote, "rev-parse", "main")).strip() == initial
    manager.adapter.repair = True
    manager.integrations.schedule("project-backend")
    await settle(manager)
    assert manager.store.get("projects", "project")["integration"]["status"] == "PROMOTED"

import asyncio
import importlib.util
import json
import socket
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.execution import ExecutionManager
from virtual_agent_cafe.management.sandbox import Sandbox
from virtual_agent_cafe.management.setup import ProjectSetup, SetupInput

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("setup_project", ROOT / "scripts/setup-project.py")
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


async def project(tmp_path, monkeypatch, committed=True):
    manager = ExecutionManager(tmp_path, EventBus())
    manager.workspaces.create("sample")
    await manager.git.init("sample")
    source = manager.workspaces.get("sample")
    if committed:
        (source / "README.md").write_text("# Existing project\n")
        await manager.git.stage("sample", ["README.md"])
        await manager.git.commit("sample", "feat: initial project")
    setup = ProjectSetup(manager, "codex")
    monkeypatch.setattr(setup, "command_ok", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "virtual_agent_cafe.management.setup.shutil",
        SimpleNamespace(which=lambda _name: "/usr/bin/true"),
    )
    return manager, setup, source


async def test_create_real_team_preserves_source_and_markdown_on_repeat(tmp_path, monkeypatch):
    manager, setup, source = await project(tmp_path, monkeypatch)
    (source / "README.md").write_text("# Unsaved source changes\n")
    await manager.git.set_remote("sample", "origin", "git@example.org:team/project.git")
    report = await setup.inspect("sample")
    assert report["ready"]
    assert report["dirty_warning"]
    assert report["remote"] == "git@example.org:team/project.git"
    data = SetupInput(project="sample", objective="Build an API and matching frontend.")
    first, duplicate = await asyncio.gather(setup.create(data), setup.create(data))
    assert first == duplicate
    assert first["status"] == "READY"
    assert len(manager.store.list("agents")) == 2
    assert not manager.running
    for role in ("backend", "frontend"):
        agent = manager.registry.get("sample-" + role)
        config = agent["config"]
        assert not config["git"]["allow_push"]
        assert (await manager.git.info(config["workspace"]))["branch"].startswith("agent/")
        assert (
            (manager.workspaces.get(config["workspace"]) / "README.md")
            .read_text()
            .startswith("# Existing")
        )
        assert data.objective in manager.tasks.load(config["task"])["content"]
    manager.tasks.save("sample-backend.md", "# Custom edited task\nKeep me.")
    await setup.create(data)
    assert "Keep me" in manager.tasks.load("sample-backend.md")["content"]
    assert (source / "README.md").read_text() == "# Unsaved source changes\n"
    assert setup.projects()["projects"] == ["sample"]


async def test_checks_block_missing_login_initial_commit_and_demo_mode(tmp_path, monkeypatch):
    manager, setup, _ = await project(tmp_path, monkeypatch, committed=False)
    report = await setup.inspect("sample")
    assert not report["ready"]
    with pytest.raises(ValueError, match="failed project checks"):
        await setup.create(SetupInput(project="sample", objective="Implement this project."))
    assert not manager.store.list("agents")
    setup.command_ok.side_effect = [False]
    report = await setup.inspect("sample")
    assert not next(c for c in report["checks"] if c["name"] == "codex")["ok"]
    setup.command_ok.side_effect = None
    setup.mode = "demo"
    setup.command_ok.return_value = False
    monkeypatch.setattr(
        Sandbox, "probe", AsyncMock(return_value=Sandbox.failure("Operation not permitted", 1))
    )
    setup.command_ok.reset_mock()
    report = await setup.inspect("sample")
    assert {c["name"] for c in report["checks"] if c["ok"] is False} == {"sandbox", "mode"}
    assert {c["name"] for c in report["checks"] if c.get("status") == "SKIPPED"} == {
        "codex",
        "repository",
    }
    setup.command_ok.assert_not_called()


async def test_conflicts_preserve_files_and_partial_setup_can_resume(tmp_path, monkeypatch):
    manager, setup, _ = await project(tmp_path, monkeypatch)
    data = SetupInput(project="sample", objective="Build an API with frontend.")
    manager.tasks.save("sample-backend.md", "# Existing\nKeep me")
    with pytest.raises(ValueError, match="Markdown already exists"):
        await setup.create(data)
    assert not manager.store.list("projects")
    manager.tasks.files.path("sample-backend.md").unlink()
    worktree = manager.git.worktree
    calls = 0

    async def fail_second(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise ValueError("Interrupted")
        return await worktree(*args)

    monkeypatch.setattr(manager.git, "worktree", fail_second)
    with pytest.raises(ValueError, match="Interrupted"):
        await setup.create(data)
    assert manager.store.get("projects", "sample")["status"] == "PREPARING"
    from virtual_agent_cafe.bus import EventBus
    from virtual_agent_cafe.management.execution import ExecutionManager

    # Open the actual persisted store with a fresh controller, as on container restart.
    restored = ExecutionManager(manager.contexts.root.parent, EventBus(), recover=False)
    assert len(restored.store.list("agents")) == 2
    assert restored.registry.get("sample-frontend")["state"] == "FAILED"
    assert restored.tasks.load("sample-frontend.md")["content"]
    assert restored.roles.load("sample-frontend.md")["content"]
    manager.tasks.save("sample-backend.md", "# Changed during recovery\nKeep me")
    monkeypatch.setattr(manager.git, "worktree", worktree)
    assert (await setup.create(data))["status"] == "READY"
    assert "Keep me" in manager.tasks.load("sample-backend.md")["content"]


async def test_remote_check_opt_in_no_secrets_and_no_push(tmp_path, monkeypatch):
    manager, setup, source = await project(tmp_path, monkeypatch)
    # Set malicious legacy remote config directly, not via the validating API.
    await manager.git.run(source, "remote", "add", "origin", "https://secret@example.org/repo")
    assert (await setup.inspect("sample"))["remote"] == ""
    with pytest.raises(ValueError, match="Enable remote"):
        await setup.inspect("sample", True)
    monkeypatch.setenv("VAC_ALLOW_REMOTE_GIT", "1")
    with pytest.raises(ValueError, match="credential-free"):
        await setup.inspect("sample", True)
    await manager.git.set_remote("sample", "origin", "git@example.org:team/project.git")
    original = manager.git.run
    network = []

    async def fake_network(path, *args, **kwargs):
        if args[0] == "ls-remote":
            network.append(args)
            return "abc HEAD"
        return await original(path, *args, **kwargs)

    monkeypatch.setattr(manager.git, "run", fake_network)
    assert "Remote readable" in (await setup.inspect("sample", True))["remote_status"]
    assert network == [("ls-remote", "--", "git@example.org:team/project.git", "HEAD")]


def test_setup_api_authorization_and_path_rejection(tmp_path):
    app = create_app("demo", management_root=tmp_path)
    token = app.state.management.access.token
    with TestClient(app) as client:
        assert client.get("/management/setup").status_code == 401
        headers = {"Authorization": "Bearer " + token}
        assert client.get("/management/setup", headers=headers).json()["projects"] == []
        assert (
            client.post(
                "/management/setup/team",
                headers=headers,
                json={"project": "sample", "objective": " " * 20},
            ).status_code
            == 422
        )
        for value in ["../escape", "/etc", "x;pwd"]:
            assert (
                client.post(
                    "/management/setup/check", headers=headers, json={"project": value}
                ).status_code
                == 422
            )
        assert (
            client.post(
                "/management/setup/check", headers=headers, json={"project": "missing"}
            ).status_code
            == 409
        )


def test_launcher_restricts_mounts_forwards_socket_and_keeps_keys_out(tmp_path, monkeypatch):
    repo = tmp_path / "My App"
    (repo / ".git").mkdir(parents=True)
    assert launcher.selected_project(str(repo)) == repo
    identifier = launcher.project_id(repo)
    assert identifier.startswith("my-app-") and len(identifier) <= 40
    assert identifier != launcher.project_id(tmp_path / "another" / "My App")
    monkeypatch.setenv("HOME", str(tmp_path))
    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    (ssh / "known_hosts").write_text("test fixture")
    address = tmp_path / "agent.sock"
    with socket.socket(socket.AF_UNIX) as agent:
        agent.bind(str(address))
        monkeypatch.setenv("SSH_AUTH_SOCK", str(address))
        config = launcher.override(repo, identifier, False)["services"]["backend"]
    assert config["environment"]["VAC_ALLOW_REMOTE_GIT"] == "0"
    assert len(config["volumes"]) == 3
    assert config["volumes"][0]["source"] == str(repo)
    assert all("id_ed25519" not in mount["source"] for mount in config["volumes"])
    assert config["volumes"][2]["read_only"]
    with pytest.raises(ValueError):
        launcher.selected_project(str(tmp_path))
    with pytest.raises(ValueError):
        launcher.selected_project(str(ROOT))


def test_launcher_connects_without_printing_or_persisting_token(tmp_path, monkeypatch, capsys):
    from types import SimpleNamespace

    root = tmp_path / "cafe"
    root.mkdir()
    repo = tmp_path / "External Project"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setattr(launcher.shutil, "which", lambda _name: "/usr/bin/fake")
    monkeypatch.setattr(
        "sys.argv", ["setup-project.py", "--project", str(repo), "--godot", "fake-godot"]
    )
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(
            returncode=0, stdout='{"ok": true}' if "bash" in command else "fixture-private-token\n"
        )

    monkeypatch.setattr(launcher.subprocess, "run", run)
    launcher.main()
    assert calls[-1][0] == ["fake-godot", "--path", str(root / "game")]
    assert calls[-1][1]["env"]["VAC_MANAGEMENT_TOKEN"] == "fixture-private-token"
    assert calls[-1][1]["env"]["VAC_OPEN_SETUP"] == "1"
    assert calls[-1][1]["env"]["VAC_BACKEND_URL"] == "http://127.0.0.1:8000"
    config = (root / ".runtime/setup/project.compose.json").read_text()
    assert "fixture-private-token" not in config + capsys.readouterr().out
    assert not any("privileged" in str(command) for command, _ in calls)
    assert any("--wait" in command for command, _ in calls)
    probe = next(command for command, _ in calls if "bash" in command)
    assert probe[-2:] == ["vac-sandbox-check", "/workspaces/" + launcher.project_id(repo)]
    assert '"$1"' in probe[-3]


def test_launcher_dry_run_never_invokes_docker_or_writes_config(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cafe"
    root.mkdir()
    repo = tmp_path / "Project"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setattr("sys.argv", ["setup-project.py", "--project", str(repo), "--dry-run"])
    monkeypatch.setattr(
        launcher.subprocess, "run", lambda *a, **k: pytest.fail("unexpected process")
    )
    launcher.main()
    assert str(repo) in capsys.readouterr().out
    assert not (root / ".runtime").exists()


def test_wsl_folder_picker_keeps_selected_windows_paths_out_of_shell_code(tmp_path, monkeypatch):
    repo = tmp_path / "My Project"
    (repo / ".git").mkdir(parents=True)
    calls = []
    windows_path = "C:\\Projects\\User's project $name"
    monkeypatch.setattr(launcher.shutil, "which", lambda _name: "/fake/powershell.exe")

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=windows_path if len(calls) == 1 else str(repo))

    monkeypatch.setattr(launcher.subprocess, "run", run)
    assert launcher.selected_project(None) == repo
    assert calls[0][:4] == ["powershell.exe", "-NoProfile", "-STA", "-Command"]
    assert windows_path not in calls[0][4]
    assert calls[1] == ["wslpath", "-u", windows_path]


async def test_corrupt_repository_returns_actionable_failed_check(tmp_path, monkeypatch):
    manager, setup, source = await project(tmp_path, monkeypatch)
    (source / ".git/HEAD").write_text("invalid metadata")
    report = await setup.inspect("sample")
    assert not report["ready"]
    failure = next(c for c in report["checks"] if c["name"] == "repository")
    assert not failure["ok"] and "metadata" in failure["detail"]
    with pytest.raises(ValueError, match="failed project checks"):
        await setup.create(
            SetupInput(project="sample", objective="Implement backend and frontend.")
        )
    assert not manager.store.list("agents")


async def test_project_check_timeout_is_reported_not_an_internal_error(tmp_path, monkeypatch):
    _, setup, _ = await project(tmp_path, monkeypatch)
    monkeypatch.setattr(setup, "inspect_project", AsyncMock(side_effect=TimeoutError))
    with pytest.raises(ValueError, match="Project check timed out"):
        await setup.inspect("sample")


def test_launcher_stops_before_login_and_godot_if_sandbox_fails(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cafe"
    root.mkdir()
    repo = tmp_path / "Project"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setattr(launcher.shutil, "which", lambda _name: "/usr/bin/fake")
    monkeypatch.setattr("sys.argv", ["setup-project.py", "--project", str(repo), "--privileged"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "bash" in command:
            return SimpleNamespace(
                returncode=1, stdout='{"ok": false, "detail": "Namespace denied"}'
            )
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr(launcher.subprocess, "run", run)
    with pytest.raises(ValueError, match="Codex-Login und Godot-Start"):
        launcher.main()
    assert "Namespace denied" in capsys.readouterr().out
    assert not any("codex" in command for command in calls)
    assert len(calls) == 2


async def test_real_codex_login_check_accepts_cached_auth_without_model_calls(
    tmp_path, monkeypatch
):
    import json
    import shutil

    codex = shutil.which("codex")
    if codex is None:
        pytest.skip("Codex CLI unavailable")
    manager, setup, _ = await project(tmp_path, monkeypatch)
    # Exercise the real status parser instead of the normal deterministic CLI stub.
    monkeypatch.setattr(setup, "command_ok", ProjectSetup.command_ok.__get__(setup, ProjectSetup))
    monkeypatch.setattr(
        "virtual_agent_cafe.management.setup.shutil", SimpleNamespace(which=lambda _name: codex)
    )
    auth = tmp_path / "fixture-auth"
    auth.mkdir()
    (auth / "auth.json").write_text(json.dumps({"OPENAI_API_KEY": "sk-fixture-not-a-real-key"}))
    monkeypatch.setenv("CODEX_HOME", str(auth))
    command = Sandbox.command

    def offline(self, workspace, arguments, **kwargs):
        kwargs["network"] = False
        return command(self, workspace, arguments, **kwargs)

    monkeypatch.setattr(Sandbox, "command", offline)
    report = await setup.inspect("sample")
    assert next(c for c in report["checks"] if c["name"] == "codex")["ok"] is True
    assert report["ready"] is True
    # The same executable must report missing credentials correctly as well.
    (auth / "auth.json").unlink()
    report = await setup.inspect("sample")
    assert next(c for c in report["checks"] if c["name"] == "codex")["ok"] is False
    assert not report["ready"]


async def test_existing_team_can_enable_publication_without_losing_tasks_or_history(
    tmp_path, monkeypatch
):
    manager, setup, source = await project(tmp_path, monkeypatch)
    await manager.git.set_remote("sample", "origin", "git@example.org:team/project.git")
    data = SetupInput(project="sample", objective="Implement backend and frontend.")
    await setup.create(data)
    manager.tasks.save("sample-backend.md", "# Custom task\nPreserve my changes.")
    manager.store.put("executions", "previous-run", {"detail": "Earlier task finished"})
    manager.registry.update("sample-backend", last_execution="previous-run")
    data.publish_results = True
    with pytest.raises(ValueError, match="--publish-results"):
        await setup.create(data)
    assert not manager.registry.get("sample-backend")["config"]["git"]["allow_push"]
    monkeypatch.setenv("VAC_ALLOW_REMOTE_GIT", "1")
    record = await setup.create(data)
    assert record["publish_results"]
    for identifier in record["agents"]:
        config = manager.registry.get(identifier)["config"]
        assert config["git"]["push_on_success"] and config["git"]["allow_push"]
    assert manager.registry.get("sample-backend")["last_execution"] == "previous-run"
    assert "Preserve my changes" in manager.tasks.load("sample-backend.md")["content"]
    assert (source / "README.md").read_text().startswith("# Existing")


def test_launcher_publish_flag_enables_remote_capability_without_secrets(
    tmp_path, monkeypatch, capsys
):
    import json

    repo = tmp_path / "Project"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(
        "sys.argv", ["setup-project.py", "--project", str(repo), "--publish-results", "--dry-run"]
    )
    launcher.main()
    plan = json.loads(capsys.readouterr().out)
    assert plan["services"]["backend"]["environment"]["VAC_ALLOW_REMOTE_GIT"] == "1"


def test_launcher_can_restore_original_workspace_id_mount(tmp_path, monkeypatch, capsys):
    root = tmp_path / "cafe"
    root.mkdir()
    repo = tmp_path / "SimulationWorld"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "setup-project.py",
            "--project",
            str(repo),
            "--workspace-id",
            "project-1467da4f208c3c30b8b116-fd507a6f",
            "--dry-run",
        ],
    )
    launcher.main()
    plan = json.loads(capsys.readouterr().out)
    volume = plan["services"]["backend"]["volumes"][0]
    assert volume["source"] == str(repo)
    assert volume["target"] == "/workspaces/project-1467da4f208c3c30b8b116-fd507a6f"


def test_launcher_rejects_invalid_workspace_id(tmp_path, monkeypatch):
    root = tmp_path / "cafe"
    root.mkdir()
    repo = tmp_path / "SimulationWorld"
    (repo / ".git").mkdir(parents=True)
    monkeypatch.setattr(launcher, "ROOT", root)
    monkeypatch.setattr(
        "sys.argv",
        [
            "setup-project.py",
            "--project",
            str(repo),
            "--workspace-id",
            "../escape",
            "--dry-run",
        ],
    )
    with pytest.raises(ValueError, match="Workspace-ID"):
        launcher.main()


def test_project_identity_reuses_remote_across_mount_paths_and_remembers_override(
    tmp_path, monkeypatch
):
    root = tmp_path / "cafe"
    root.mkdir()
    monkeypatch.setattr(launcher, "ROOT", root)
    first = tmp_path / "SimulationWorld"
    second = tmp_path / "Docker Desktop" / "SimulationWorld"
    for path in (first, second):
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(path),
                "remote",
                "add",
                "origin",
                "git@github.com:St3fanTh/SimulationWorld.git",
            ],
            check=True,
        )
    assert launcher.project_id(first) == launcher.project_id(second)
    legacy = "project-1467da4f208c3c30b8b116-fd507a6f"
    launcher.save_project_id(first, legacy)
    assert launcher.project_id(second) == legacy
    mapping = (root / ".runtime/setup/project-mounts.json").read_text()
    assert "github.com" not in mapping and legacy in mapping

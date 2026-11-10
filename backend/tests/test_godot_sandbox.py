"""Real offline Godot inside both the controller and nested Codex sandbox."""

import subprocess

import pytest

from virtual_agent_cafe.adapters.codex import CodexObserver
from virtual_agent_cafe.management.sandbox import Sandbox


@pytest.mark.parametrize("nested", [False, True])
def test_godot_user_data_is_writable_private_and_ephemeral(tmp_path, nested):
    workspace = tmp_path / "project"
    workspace.mkdir()
    (workspace / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Sandbox user data regression"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    (workspace / "test_user_data.gd").write_text(
        """extends SceneTree
func _initialize():
    var user_path = ProjectSettings.globalize_path("user://")
    if not user_path.begins_with("/tmp/vac-user/data/"):
        quit(1)
        return
    if FileAccess.file_exists("user://probe.txt"):
        quit(2)
        return
    var file = FileAccess.open("user://probe.txt", FileAccess.WRITE)
    if file == null:
        quit(3)
        return
    file.store_string("private state")
    file.close()
    if FileAccess.get_file_as_string("user://probe.txt") != "private state":
        quit(4)
        return
    print("USER_DATA_OK")
    quit(0)
"""
    )
    private = tmp_path / "host-private"
    private.mkdir()
    (private / "sentinel").write_text("not exposed")
    (workspace / ".git").mkdir()
    (workspace / ".git/HEAD").write_text("protected")
    command = ["godot", "--headless", "--path", str(workspace), "--script", "test_user_data.gd"]
    if nested:
        command = ["codex", "sandbox", "-c", 'sandbox_mode="workspace-write"', "--", *command]
    # A second process must get a fresh private user://, not the previous run's files.
    for _ in range(2):
        result = subprocess.run(
            Sandbox().command(workspace, command, network=False, writable_git=False),
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert result.returncode == 0, result.stderr
        assert "USER_DATA_OK" in result.stdout
        assert "ERROR:" not in result.stdout + result.stderr
    probe = (
        "from pathlib import Path; "
        f"assert not Path({str(private)!r}).exists(); "
        "assert not Path('/home/node/.codex').exists(); "
        "assert not Path('/home/agent/.codex/auth.json').exists(); "
        "assert not Path('/run/ssh-agent').exists(); "
        "p = Path('.git/HEAD'); "
        "\ntry:\n p.write_text('forbidden')\nexcept OSError:\n pass\n"
        "else:\n raise AssertionError('Git writable')"
    )
    result = subprocess.run(
        Sandbox().command(workspace, ["python3", "-c", probe], network=False, writable_git=False),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert (workspace / ".git/HEAD").read_text() == "protected"
    assert not (workspace / "probe.txt").exists()


@pytest.mark.parametrize(
    "command", ["godot --headless --script test_api.gd", "godot4 --headless", "./run-tests.sh"]
)
@pytest.mark.parametrize("exit_code", [134, 0])
def test_godot_startup_failure_blocks_completion_and_is_infrastructure(command, exit_code):
    events = []
    observer = CodexObserver(lambda *event: events.append(event))
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": command,
                "exit_code": exit_code,
                "aggregated_output": (
                    "ERROR: Could not create directory: '/home/agent/.local'.\n"
                    "ERROR: Error attempting to create data dir: /private/fixture-secret.\n"
                    "handle_crash: Program crashed with signal 11\n"
                ),
            },
        }
    )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful
    assert observer.failed_tests
    assert observer.test_runs[-1]["category"] == "ENVIRONMENT_ERROR"
    assert "writable sandbox XDG" in str(observer.test_runs[-1]["causes"])
    assert "fixture-secret" not in str(events) + str(observer.test_runs)


async def test_controller_keeps_godot_directory_failure_as_infrastructure(tmp_path, monkeypatch):
    from test_godot_validation import fixture

    from virtual_agent_cafe.management import validation

    manager, config, run, workspace, _, _ = await fixture(tmp_path)

    async def failed_start(*_):
        return {
            "exit_code": 134,
            "stdout": "",
            "stderr": "ERROR: Error attempting to create data dir: /private/fixture-secret.\n",
            "error": None,
            "truncated": False,
        }

    monkeypatch.setattr(validation, "capture_check", failed_start)
    with pytest.raises(ValueError, match="ENVIRONMENT_ERROR"):
        await validation.validate(manager, config, run, workspace)
    assert run["validation"]["state"] == "VALIDATION_INFRA_ERROR"
    assert not run["validation"]["passed"]
    assert all(
        c["diagnostics"]["category"] == "ENVIRONMENT_ERROR" for c in run["validation"]["checks"]
    )
    assert "fixture-secret" not in str(run["validation"])


@pytest.mark.parametrize("nested", [False, True])
def test_state_home_is_private_writable_and_ephemeral(tmp_path, nested):
    probe = """import os
from pathlib import Path
state = Path(os.environ['XDG_STATE_HOME'])
assert str(state) == '/tmp/vac-user/state'
assert state.stat().st_mode & 0o777 == 0o700
assert not (state / 'probe').exists()
(state / 'probe').write_text('private')
"""
    command = ["python3", "-c", probe]
    if nested:
        command = ["codex", "sandbox", "-c", 'sandbox_mode="workspace-write"', "--", *command]
    for _ in range(2):
        result = subprocess.run(
            Sandbox().command(tmp_path, command, network=False, writable_git=False),
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert result.returncode == 0, result.stderr
    assert not (tmp_path / "probe").exists()


def test_state_home_is_part_of_validation_environment_identity(monkeypatch):
    from virtual_agent_cafe.management.validation import environment_identity

    current = Sandbox.runtime_environment()
    before = environment_identity()
    assert current["XDG_STATE_HOME"] == "/tmp/vac-user/state"
    monkeypatch.setattr(
        Sandbox,
        "runtime_environment",
        staticmethod(lambda: {k: v for k, v in current.items() if k != "XDG_STATE_HOME"}),
    )
    assert environment_identity()["sha256"] != before["sha256"]

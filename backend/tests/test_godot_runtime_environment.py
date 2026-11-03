"""Real engine/font/socket probes; no model, external networking or test suppression."""

import subprocess

import pytest
from test_godot_validation import fixture

from virtual_agent_cafe.adapters.codex import CodexObserver
from virtual_agent_cafe.management import validation
from virtual_agent_cafe.management.sandbox import Sandbox

SCRIPT = """extends SceneTree
func _initialize():
    var font = SystemFont.new()
    font.font_names = ["sans-serif"]
    assert(font.get_string_size("runtime regression").x > 0)
    var server = TCPServer.new()
    var result = server.listen(0, "127.0.0.1")
    print("LISTEN_RESULT=", result)
    server.stop()
    print("PASS")
    quit(0)
"""


def project(tmp_path):
    (tmp_path / "project.godot").write_text("config_version=5\n")
    (tmp_path / "test_states.gd").write_text(SCRIPT)


def command(workspace, nested, inner):
    if nested:
        inner = ["codex", "sandbox", "-c", 'sandbox_mode="workspace-write"', "--", *inner]
    return Sandbox().command(workspace, inner, network=False, writable_git=False)


@pytest.mark.parametrize("nested", [False, True])
def test_runtime_directory_and_system_fonts_are_available(tmp_path, nested):
    project(tmp_path)
    probe = """
import json, os, pathlib, stat, subprocess
runtime = pathlib.Path(os.environ["XDG_RUNTIME_DIR"])
assert runtime.is_dir()
assert stat.S_IMODE(runtime.stat().st_mode) == 0o700
assert runtime.stat().st_uid == os.getuid()
(runtime / "probe").write_text("private")
assert os.environ["HOME"] == "/home/agent"
assert pathlib.Path(os.environ["FONTCONFIG_FILE"]).is_file()
print("ENVIRONMENT_OK")
"""
    result = subprocess.run(
        command(tmp_path, nested, ["python3", "-c", probe]),
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    assert "ENVIRONMENT_OK" in result.stdout
    assert not (tmp_path / "probe").exists()


@pytest.mark.parametrize("nested", [False, True])
def test_socket_failure_is_nested_policy_not_xdg_or_fonts(tmp_path, nested):
    project(tmp_path)
    # Same environment, files and Godot binary. Only nested Codex policy differs.
    probe = """
import errno, socket, subprocess
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.close()
    print("SOCKET_OK")
except OSError as error:
    print("SOCKET_ERRNO=" + str(error.errno))
result = subprocess.run(["godot", "--headless", "--path", ".", "--script", "test_states.gd"])
raise SystemExit(result.returncode)
"""
    result = subprocess.run(
        command(tmp_path, nested, ["python3", "-c", probe]),
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0
    assert "PASS" in result.stdout
    assert "Fontconfig error" not in result.stdout + result.stderr
    observer = CodexObserver(lambda *_: None)
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": "godot --headless --path . --script test_states.gd",
                "exit_code": result.returncode,
                "aggregated_output": result.stdout + result.stderr,
            },
        }
    )
    observer.consume({"type": "turn.completed"})
    if nested:
        assert "SOCKET_ERRNO=1" in result.stdout  # EPERM, not a filesystem failure.
        assert "_sock == -1" in result.stderr
        assert not observer.successful
        assert observer.test_runs[-1]["category"] == "UNCLASSIFIED_ERROR"
        assert "sandbox network permissions" in str(observer.test_runs[-1]["causes"])
    else:
        assert "SOCKET_OK" in result.stdout and "LISTEN_RESULT=0" in result.stdout
        assert "ERROR:" not in result.stdout + result.stderr
        assert observer.successful


async def test_controller_validates_real_font_and_local_socket_test(tmp_path):
    manager, config, run, workspace, _, _ = await fixture(tmp_path)
    script = workspace / "frontend/tests/test_frontend.gd"
    script.write_text(SCRIPT.replace('print("LISTEN_RESULT=", result)', "assert(result == OK)"))
    await manager.git.stage("integration", ["frontend/tests/test_frontend.gd"])
    await manager.git.commit("integration", "test: exercise system fonts and loopback")
    report = await validation.validate(manager, config, run, workspace)
    assert report["passed"]
    result = report["checks"][1]
    assert result["passed"] and result["exit_code"] == 0
    env = result["context"]["runtime_environment"]
    assert env["XDG_RUNTIME_DIR"] == "/tmp/vac-user/runtime"
    assert env["FONTCONFIG_FILE"] == "/etc/fonts/fonts.conf"
    output = manager.store.get("validation_outputs", run["id"] + ":test_frontend")
    assert "ERROR:" not in output["stdout"] + output["stderr"]
    assert "Fontconfig error" not in output["stderr"]
    assert report["commit"] == (await manager.git.run(workspace, "rev-parse", "HEAD")).strip()

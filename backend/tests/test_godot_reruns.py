"""Godot environment repairs resolve only the same observed test scope."""

import pytest

from virtual_agent_cafe.adapters.codex import CodexObserver

COMMAND = "godot --headless --path frontend --script res://tests/test_states.gd"


def record(observer, command, output, cwd="/project"):
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": command,
                "cwd": cwd,
                "exit_code": 0,
                "aggregated_output": output,
            },
        }
    )
    observer.consume({"type": "turn.completed"})


@pytest.mark.parametrize("env_prefix", ["", "env "])
def test_clean_godot_rerun_after_environment_repair_resolves_prior_errors(env_prefix):
    observer = CodexObserver(lambda *_: None)
    record(observer, COMMAND, 'ERROR: Condition "_sock == -1" is true.')
    record(observer, "XDG_DATA_HOME=/tmp/old " + COMMAND, "ERROR: Runtime failure")
    assert not observer.successful
    record(
        observer,
        env_prefix
        + (
            "XDG_DATA_HOME=/tmp/new XDG_CONFIG_HOME=/tmp/config XDG_CACHE_HOME=/tmp/cache "
            "XDG_RUNTIME_DIR=/tmp/runtime FONTCONFIG_FILE=frontend/fonts.conf "
            "FONTCONFIG_PATH=frontend "
        )
        + COMMAND,
        "PASS",
    )
    assert observer.successful
    assert not observer.failed_frameworks
    assert all(run.get("superseded") for run in observer.test_runs[:-1])
    assert len(observer.test_runs) == 3  # Keep failed attempts as historical evidence.


@pytest.mark.parametrize(
    "command,cwd",
    [
        (COMMAND.replace("test_states", "test_protocol"), "/project"),
        (COMMAND, "/other-project"),
        (COMMAND.replace("--path frontend", "--path backend"), "/project"),
        ("TEST_FILTER=smoke " + COMMAND, "/project"),
        (COMMAND + " -- --filter smoke", "/project"),
        (COMMAND.replace("godot", "/other/godot", 1), "/project"),
    ],
)
def test_environment_repair_cannot_clear_other_scopes(command, cwd):
    observer = CodexObserver(lambda *_: None)
    record(observer, COMMAND, "SCRIPT ERROR: Assertion failed")
    record(observer, "FONTCONFIG_FILE=frontend/fonts.conf " + command, "PASS", cwd)
    assert not observer.successful
    assert not observer.test_runs[0].get("superseded")


def test_zero_exit_godot_errors_still_block_after_environment_repair():
    observer = CodexObserver(lambda *_: None)
    record(observer, COMMAND, "ERROR: Runtime failure")
    record(
        observer,
        "FONTCONFIG_FILE=frontend/fonts.conf " + COMMAND,
        "PASS\nSCRIPT ERROR: Assertion failed",
    )
    assert not observer.successful
    assert len(observer.failed_frameworks) == 1

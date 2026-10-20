import asyncio
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from virtual_agent_cafe.management import sandbox as sandbox_module
from virtual_agent_cafe.management.sandbox import Sandbox

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "stderr,code",
    [
        ("bwrap: Creating new namespace failed: Operation not permitted", "namespace_denied"),
        ("bwrap: No permissions to create new namespace", "namespace_denied"),
        ("bwrap: mount read-only file system", "mount_failed"),
        ("bwrap: execvp true: No such file or directory", "runtime_missing"),
        ("bwrap: Creating new namespace failed: No space left on device", "namespace_limit"),
        ("bwrap: unexpected failure /private/project fixture-secret", "sandbox_failed"),
    ],
)
async def test_probe_classifies_errors_without_returning_raw_stderr(
    tmp_path, monkeypatch, stderr, code
):
    command = [sys.executable, "-c", f"import sys; sys.stderr.write({stderr!r}); sys.exit(1)"]
    monkeypatch.setattr(Sandbox, "command", lambda *args, **kwargs: command)
    result = await Sandbox().probe(tmp_path)
    assert result["code"] == code and result["ok"] is False
    assert "fixture-secret" not in json.dumps(result)
    assert "/private/project" not in json.dumps(result)
    with pytest.raises(ValueError, match=result["detail"].split(".")[0]):
        await Sandbox().validate(tmp_path)


async def test_probe_missing_binary_and_launch_failure(tmp_path, monkeypatch):
    def missing():
        raise ValueError("Install bubblewrap")

    monkeypatch.setattr(sandbox_module, "bubblewrap", missing)
    assert (await Sandbox().probe(tmp_path))["code"] == "runtime_missing"
    monkeypatch.setattr(Sandbox, "command", lambda *a, **k: [str(tmp_path / "nonexistent")])
    assert (await Sandbox().probe(tmp_path))["code"] == "launch_failed"


async def test_probe_timeout_reaps_process(tmp_path, monkeypatch):
    children = []
    original_spawn = asyncio.create_subprocess_exec

    async def spawn(*args, **kwargs):
        child = await original_spawn(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(
        Sandbox, "command", lambda *a, **k: [sys.executable, "-c", "import time; time.sleep(60)"]
    )
    monkeypatch.setattr(
        sandbox_module,
        "asyncio",
        SimpleNamespace(
            create_subprocess_exec=spawn,
            subprocess=asyncio.subprocess,
            timeout=lambda _seconds: asyncio.timeout(0.1),
        ),
    )
    assert (await Sandbox().probe(tmp_path))["code"] == "timeout"
    assert len(children) == 1 and children[0].returncode is not None


async def test_probe_bounds_error_output(tmp_path, monkeypatch):
    monkeypatch.setattr(
        Sandbox,
        "command",
        lambda *a, **k: [
            sys.executable,
            "-c",
            "import sys,time; sys.stderr.write('x'*200000); sys.stderr.flush(); time.sleep(60)",
        ],
    )
    result = await Sandbox().probe(tmp_path)
    assert result["code"] == "sandbox_failed"
    assert "x" * 100 not in json.dumps(result)


def test_real_diagnostic_cli_reports_namespace_result_without_credentials(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/sandbox-diagnostics.py"),
            "--workspace",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    report = json.loads(result.stdout)
    assert report["code"] in {
        "ready",
        "namespace_denied",
        "namespace_limit",
        "mount_failed",
        "runtime_missing",
        "launch_failed",
        "sandbox_failed",
        "timeout",
    }, report
    # Hosted CI may prohibit user namespaces. In that case the diagnostic must
    # fail closed with a classified result instead of making the test depend on
    # a runner-level capability. Isolation tests exercise the real sandbox when
    # the host permits it.
    assert report["ok"] is (report["code"] == "ready"), report
    assert result.returncode == (0 if report["ok"] else 1)
    assert "auth.json" not in result.stdout
    assert all(isinstance(v, int) for v in report["namespace_settings"].values())

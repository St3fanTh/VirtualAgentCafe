import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("godot") is None, reason="Godot CLI unavailable")
def test_godot_task_ui_to_cli_process_and_back(tmp_path):
    cli = tmp_path / "fixture-codex"
    cli.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys, time\n"
        "prompt = sys.stdin.read()\n"
        "workspace = pathlib.Path(sys.argv[sys.argv.index('-C') + 1])\n"
        "def send(data):\n    print(json.dumps(data), flush=True)\n"
        "send({'type': 'turn.started'})\n"
        "if 'fixture: wait' in prompt: time.sleep(60)\n"
        "(workspace / 'result.txt').write_text('fixture output')\n"
        "send({'type': 'item.completed', 'item': {'type': 'file_change', 'status': 'completed'}})\n"
        "time.sleep(0.05)\n"
        "send({'type': 'item.started', 'item': {'type': 'command_execution', "
        "'command': 'pytest -q'}})\n"
        "time.sleep(0.05)\n"
        "send({'type': 'item.completed', 'item': {'type': 'command_execution', "
        "'command': 'pytest -q', 'exit_code': 0}})\n"
        "send({'type': 'turn.completed'})\n"
    )
    cli.chmod(0o755)
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "VAC_FIXTURE_CLI": str(cli),
        "VAC_FIXTURE_ROOT": str(tmp_path / "work"),
        "VAC_BACKEND_URL": url,
    }
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "runtime_app:app",
            "--app-dir",
            str(ROOT / "backend/tests/fixtures"),
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while True:
            assert server.poll() is None, "Fixture backend exited"
            try:
                with urllib.request.urlopen(url + "/health", timeout=0.5):
                    break
            except (urllib.error.URLError, TimeoutError):
                assert time.monotonic() < deadline, "Fixture backend readiness timeout"
                time.sleep(0.05)
        result = subprocess.run(
            [
                "godot",
                "--headless",
                "--path",
                str(ROOT / "game"),
                "--script",
                "res://tests/test_tasks.gd",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 0, output
        assert "ERROR:" not in output, output
        assert "tests: PASS" in output, output
        assert (tmp_path / "work/ada/result.txt").read_text() == "fixture output"
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()

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
def test_native_management_ui_to_isolated_runtime(tmp_path):
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = {
        **os.environ,
        "VAC_MANAGEMENT_TOKEN": "fixture-management-token-32-characters",
        "VAC_FIXTURE_ROOT": str(tmp_path / "work"),
        "VAC_BACKEND_URL": url,
    }
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "managed_runtime_app:app",
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
                "res://tests/test_management.gd",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=35,
            check=False,
        )
        output = result.stdout + result.stderr
        assert result.returncode == 0, output
        assert "ERROR:" not in output, output
        assert "tests: PASS" in output, output
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()

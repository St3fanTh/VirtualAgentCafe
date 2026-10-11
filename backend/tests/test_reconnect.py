import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(shutil.which("godot") is None, reason="Godot CLI unavailable")
def test_godot_recovers_after_backend_restart(tmp_path):
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    env = {
        **os.environ,
        "VAC_MODE": "demo",
        "VAC_DEMO_INTERVAL": "0.03",
        "VAC_BACKEND_URL": f"http://127.0.0.1:{port}",
        "VAC_TEST_MARKERS": str(tmp_path),
    }

    def start_server():
        return subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "virtual_agent_cafe.main:app",
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

    def stop(process):
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

    server = start_server()
    game = subprocess.Popen(
        [
            "godot",
            "--headless",
            "--path",
            str(ROOT / "game"),
            "--script",
            "res://tests/test_reconnect.gd",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        for marker in ["connected", "offline"]:
            deadline = time.monotonic() + 10
            while not (tmp_path / marker).exists():
                assert game.poll() is None, game.communicate()[0]
                assert time.monotonic() < deadline, "Missing Godot marker " + marker
                time.sleep(0.05)
            if marker == "connected":
                stop(server)
        server = start_server()
        output, _ = game.communicate(timeout=15)
        assert game.returncode == 0, output
        assert "ERROR:" not in output, output
        assert "tests: PASS" in output, output
    finally:
        stop(server)
        if game.poll() is None:
            stop(game)

#!/usr/bin/env python3
"""Actual Uvicorn process → WebSocket → Godot; no pre-existing server required."""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "VAC_MODE": "demo", "VAC_DEMO_INTERVAL": "0.03"}
    server = subprocess.Popen(
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
    try:
        deadline = time.monotonic() + 10
        while True:
            if server.poll() is not None:
                raise RuntimeError("Backend exited before readiness")
            try:
                with urllib.request.urlopen(url + "/health", timeout=0.5) as response:
                    assert response.status == 200
                    break
            except (urllib.error.URLError, TimeoutError):
                if time.monotonic() > deadline:
                    raise RuntimeError("Backend readiness timed out") from None
                time.sleep(0.05)
        result = subprocess.run(
            [
                "godot",
                "--headless",
                "--path",
                str(ROOT / "game"),
                "--script",
                "res://tests/test_live.gd",
            ],
            env={**env, "VAC_BACKEND_URL": url},
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        output = result.stdout + result.stderr
        print(output, end="")
        if result.returncode or "ERROR:" in output or "tests: PASS" not in output:
            raise RuntimeError("Godot live integration failed")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


if __name__ == "__main__":
    main()

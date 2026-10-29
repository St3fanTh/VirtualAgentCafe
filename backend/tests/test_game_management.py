import json
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
@pytest.mark.parametrize(
    "script, saved_connection",
    [
        ("test_management.gd", False),
        ("test_log_scrolling.gd", False),
        ("test_management.gd", True),
        ("test_agent_deletion.gd", False),
        ("test_gui_input.gd", False),
        ("test_setup_input.gd", False),
        ("test_setup_input_blocked.gd", False),
    ],
)
def test_native_management_ui_to_isolated_runtime(tmp_path, script, saved_connection):
    setup_test = script.startswith("test_setup_input")
    with socket.socket() as reserve:
        reserve.bind(("127.0.0.1", 0))
        port = reserve.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    import_file = tmp_path / "instructions.md"
    import_file.write_text("Imported project agents\nUse the shared API contract and run tests.")
    env = {
        **os.environ,
        "VAC_MANAGEMENT_TOKEN": "fixture-management-token-32-characters",
        "VAC_FIXTURE_ROOT": str(tmp_path / "work"),
        "VAC_BACKEND_URL": url,
        "VAC_GUI_IMPORT_FILE": str(import_file),
        "VAC_OPEN_SETUP": "1" if setup_test else "",
        "VAC_SETUP_PROJECT": "wizard-project" if setup_test else "",
        "VAC_SANDBOX_BLOCKED": "1" if script == "test_setup_input_blocked.gd" else "0",
        "VAC_SETUP_FIXTURE": "1" if setup_test else "0",
        "VAC_GUI_DELAY": "0.5" if script == "test_gui_input.gd" else "0",
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
        display_args = ["--headless"]
        if (script in {"test_gui_input.gd", "test_agent_deletion.gd"} or setup_test) and os.getenv(
            "VAC_GUI_RENDERED"
        ) == "1":
            display_args = [
                "--audio-driver",
                "Dummy",
                "--rendering-method",
                "gl_compatibility",
                "--resolution",
                os.getenv("VAC_GUI_RESOLUTION", "1920x1080"),
            ]
        client_env = env.copy()
        if saved_connection:
            connection = tmp_path / "connection.json"
            connection.write_text(
                json.dumps(
                    {
                        "backend_url": url,
                        "token": env["VAC_MANAGEMENT_TOKEN"],
                    }
                )
            )
            client_env.pop("VAC_MANAGEMENT_TOKEN")
            client_env["VAC_CONNECTION_FILE"] = str(connection)
        result = subprocess.run(
            [
                "godot",
                *display_args,
                "--path",
                str(ROOT / "game"),
                "--script",
                "res://tests/" + script,
            ],
            env=client_env,
            capture_output=True,
            text=True,
            timeout=270 if os.getenv("VAC_GUI_RENDERED") == "1" else 60,
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

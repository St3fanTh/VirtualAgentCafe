#!/usr/bin/env python3
"""Rendered Cafe UI -> real API/controller/Git -> independent product assertion.

Requires DISPLAY (e.g. Xvfb). Only model production and remote transport use
fixtures; no credentials, external network or existing project are used.
"""

import asyncio
import json
import os
import socket
import sys
import tempfile
from contextlib import AsyncExitStack
from pathlib import Path

import pytest
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/tests"))
from fixtures.pipeline_runtime import prepare  # noqa: E402
from virtual_agent_cafe.main import create_app  # noqa: E402


async def main():
    if not os.environ.get("DISPLAY"):
        raise SystemExit("DISPLAY required: run scripts/pipeline-gui.sh with Xvfb")
    artifacts = await asyncio.to_thread(
        Path(
            os.environ.get("VAC_PIPELINE_ARTIFACTS", ROOT / ".runtime/checks/pipeline-gui")
        ).resolve
    )
    artifacts.mkdir(parents=True, exist_ok=True)
    for name in (
        "gui-result.json",
        "result.json",
        "downloaded-logs.json",
        "01-cafe.png",
        "02-project-ready.png",
        "03-running.png",
        "04-integration-complete.png",
        "05-download-dialog.png",
        "06-changelog.png",
    ):
        (artifacts / name).unlink(missing_ok=True)
    with (
        tempfile.TemporaryDirectory(prefix="vac-pipeline-gui-") as directory,
        pytest.MonkeyPatch.context() as patch,
    ):
        temporary = Path(directory)
        patch.setenv("VAC_MANAGEMENT_TOKEN", "pipeline-test-local-capability-000000")
        app = create_app(
            "codex", management_root=temporary / "controller", workspace_root=temporary / "jobs"
        )
        async with AsyncExitStack() as cleanup:
            cleanup.push_async_callback(app.state.management.close)
            await run_fixture(app, temporary, patch, artifacts)


async def run_fixture(app, temporary, patch, artifacts):
    fixture = await prepare(app, temporary, patch)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    process = None
    try:
        async with asyncio.timeout(15):
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("Fixture HTTP server failed")
                await asyncio.sleep(0.02)
        environment = dict(
            os.environ,
            VAC_BACKEND_URL=f"http://127.0.0.1:{port}",
            VAC_SETUP_PROJECT="counter",
            VAC_PIPELINE_ARTIFACTS=str(artifacts),
        )
        environment.pop("VAC_OPEN_SETUP", None)
        with (artifacts / "godot.log").open("w") as log:
            process = await asyncio.create_subprocess_exec(
                "godot",
                "--path",
                str(ROOT / "game"),
                "--audio-driver",
                "Dummy",
                "--rendering-method",
                "gl_compatibility",
                "--script",
                "res://tests/test_pipeline_gui.gd",
                env=environment,
                stdout=log,
                stderr=asyncio.subprocess.STDOUT,
            )
            async with asyncio.timeout(200):
                code = await process.wait()
        output = (artifacts / "godot.log").read_text()
        if code or "ERROR:" in output or "SCRIPT ERROR:" in output:
            raise RuntimeError(f"Rendered GUI failed (exit {code}):\n{output[-12000:]}")
        result = json.loads((artifacts / "gui-result.json").read_text())
        manager = fixture["manager"]
        remote_head = (
            await manager.git.run(fixture["remote"], "rev-parse", "refs/heads/main")
        ).strip()
        assert result["commit"] == remote_head != fixture["initial"]
        product = temporary / "independent-product"
        product.mkdir()
        for filename in ("counter.py", "controls.py"):
            source = await manager.git.run(fixture["remote"], "show", f"main:{filename}")
            (product / filename).write_text(source)
        probe = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            "from controls import CounterControls; c=CounterControls(); "
            "assert c.counter.value==0; assert c.click('plus')=='1'; "
            "assert c.click('minus')=='0'; assert c.click('minus')=='-1'; "
            "assert c.click('reset')=='0'",
            cwd=product,
        )
        try:
            async with asyncio.timeout(10):
                assert await probe.wait() == 0, (
                    "Published product failed independent behavior probe"
                )
        finally:
            if probe.returncode is None:
                probe.kill()
                await probe.wait()
        result["independent_product_verified"] = True
        result["remote_main_verified"] = remote_head
        (artifacts / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"Rendered pipeline and independent published product: PASS; evidence {artifacts}")
    finally:
        if process and process.returncode is None:
            process.kill()
            await process.wait()
        server.should_exit = True
        try:
            async with asyncio.timeout(15):
                await serving
        finally:
            await app.state.management.close()
            sock.close()


if __name__ == "__main__":
    asyncio.run(main())

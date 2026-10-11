#!/usr/bin/env python3
"""Opt-in real LLM smoke: isolated workspace, actual files and test command."""

import asyncio
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from virtual_agent_cafe.adapters.codex import CodexAdapter
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.jobs import JobManager
from virtual_agent_cafe.models import EventType


async def main():
    task_root = Path(os.getenv("VAC_SMOKE_ROOT", tempfile.gettempdir()))
    with tempfile.TemporaryDirectory(prefix="vac-codex-", dir=task_root) as temporary:
        bus = EventBus()
        jobs = JobManager(bus, CodexAdapter(timeout=120), Path(temporary))
        queue = bus.subscribe()
        prompt = (
            "In this working directory only, create greeting.py with a greet(name) function "
            "returning 'Hello ' + name. Create test_greeting.py using Python unittest to assert "
            "greet('Cafe') equals 'Hello Cafe'. Execute python3 -m unittest -v. "
            "Do not access files outside this directory or perform Git commits/pushes."
        )
        record = jobs.submit("ada", prompt)
        seen = set()
        while True:
            async with asyncio.timeout(130):
                frame = await queue.get()
            if frame["kind"] == "event":
                event = frame["event"]
                kind = event["type"]
                seen.add(kind)
                print(f"{event['sequence']}: {kind} — {event['payload']['detail']}")
                if kind in {EventType.FINISHED, EventType.ERROR}:
                    # Intermediate command errors are not necessarily final.
                    if jobs.history[record["task_id"]]["status"] != "running":
                        break
        await jobs.close()
        if jobs.history[record["task_id"]]["status"] != "finished":
            raise RuntimeError("Real Codex smoke failed; check login and sandbox")
        assert {EventType.CODING, EventType.TESTING, EventType.FINISHED} <= seen
        workspace = Path(record["workspace"])
        assert (workspace / "greeting.py").is_file()
        assert (workspace / "test_greeting.py").is_file()
        process = await asyncio.create_subprocess_exec(
            "python3",
            "-m",
            "unittest",
            "-v",
            cwd=workspace,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert await process.wait() == 0
        bus.emit("turing", EventType.WAITING, uuid4(), detail="Smoke complete")
        print("Real Codex smoke: PASS")


if __name__ == "__main__":
    asyncio.run(main())

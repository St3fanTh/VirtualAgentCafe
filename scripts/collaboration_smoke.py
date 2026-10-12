#!/usr/bin/env python3
"""Opt-in two real Codex agents exchanging explicit public messages."""

import asyncio
import json
import tempfile
from pathlib import Path

from virtual_agent_cafe.adapters.codex import CodexAdapter
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.jobs import JobManager


async def main():
    with tempfile.TemporaryDirectory(prefix="vac-collaboration-") as temporary:
        bus = EventBus(queue_limit=128)
        queue = bus.subscribe()
        jobs = JobManager(bus, CodexAdapter(timeout=120), Path(temporary))
        try:
            jobs.submit(
                "ada",
                "Use the public helper to send turing exactly: "
                "API contract: GET /health returns status ok. "
                "This is an explicitly public collaboration probe. "
                "Do not edit project files or run unrelated commands.",
            )
            async with asyncio.timeout(180):
                while jobs.running:
                    await asyncio.gather(*list(jobs.running.values()))
            messages = []
            while not queue.empty():
                frame = queue.get_nowait()
                if frame["kind"] != "event":
                    continue
                event = frame["event"]
                print(f"{event['agent_id']}: {event['type']} — {event['payload']['detail']}")
                if event["type"] == "agent.message" and event["payload"]["recipient"]:
                    messages.append(event)
            assert len(jobs.history) == 2, "Expected one backend task and one frontend reply"
            assert all(task["status"] == "finished" for task in jobs.history.values())
            assert len(messages) == 4, "Expected sent/received events in both directions"
            for agent in ["ada", "turing"]:
                lines = (Path(temporary) / agent / ".cafe/inbox.jsonl").read_text().splitlines()
                assert json.loads(lines[-1])["sender"] != agent
            print("Real backend/frontend collaboration smoke: PASS")
        finally:
            await jobs.close()


if __name__ == "__main__":
    asyncio.run(main())

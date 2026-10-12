import asyncio
import json
import sys

import pytest
from fastapi.testclient import TestClient

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.adapters.codex import CodexObserver
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.jobs import BusyError, JobManager
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.messaging import PeerMessage
from virtual_agent_cafe.models import EventType


class TalkingAdapter:
    """Execute the actual public-message helper; no external LLM used in CI."""

    def __init__(self):
        self.prompts = []

    async def run(self, prompt, workspace, emit):
        self.prompts.append((workspace.name, prompt))
        sender = workspace.name
        peer = "turing" if sender == "ada" else "ada"
        text = "API ready: /health" if sender == "ada" else "Frontend will use /health"
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            ".cafe/send_message.py",
            peer,
            text,
            cwd=workspace,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        assert await process.wait() == 0
        return RunResult(True, "Fixture turn completed")


async def wait_until_idle(jobs):
    async with asyncio.timeout(5):
        while jobs.running:
            await asyncio.gather(*list(jobs.running.values()))


def test_api_publishes_fixed_backend_frontend_roles(tmp_path):
    with TestClient(create_app(mode="codex", workspace_root=tmp_path)) as client:
        agents = client.get("/agents").json()["agents"]
        assert [(a["agent_id"], a["role"]) for a in agents] == [
            ("ada", "backend"),
            ("turing", "frontend"),
        ]


async def test_real_helper_delivery_and_single_peer_reply(tmp_path):
    bus = EventBus()
    queue = bus.subscribe()
    queue.get_nowait()
    adapter = TalkingAdapter()
    jobs = JobManager(bus, adapter, tmp_path)
    jobs.submit("ada", "Implement the API")
    await wait_until_idle(jobs)
    assert len(jobs.history) == 2, "A reply must not create an infinite dialogue"
    assert len(adapter.prompts) == 2
    assert "backend engineer" in adapter.prompts[0][1]
    assert "frontend engineer" in adapter.prompts[1][1]
    assert "peer reply task" in adapter.prompts[1][1]
    inbox = json.loads((tmp_path / "ada/.cafe/inbox.jsonl").read_text().splitlines()[-1])
    assert inbox["sender"] == "turing"
    assert inbox["text"] == "Frontend will use /health"
    frames = []
    while not queue.empty():
        frames.append(queue.get_nowait())
    messages = [f["event"] for f in frames if f["event"]["type"] == "agent.message"]
    assert len(messages) == 4
    assert all(m["payload"]["source"] == "codex" for m in messages)
    assert messages[0]["payload"]["recipient"] == "turing"
    assert messages[0]["correlation_id"] == messages[1]["correlation_id"]
    assert "Implement the API" not in json.dumps(frames)
    reply = PeerMessage.model_validate_json((tmp_path / "turing/.cafe/outbox.jsonl").read_text())
    assert reply.reply is True
    await jobs.close()


async def test_completed_cli_returns_to_observable_idle(tmp_path):
    class DoneAdapter:
        async def run(self, prompt, workspace, emit):
            return RunResult(True, "Done")

    bus = EventBus()
    jobs = JobManager(bus, DoneAdapter(), tmp_path, idle_delay=0.01)
    jobs.submit("ada", "Task")
    await wait_until_idle(jobs)
    assert bus.agents["ada"].status == EventType.FINISHED
    await asyncio.sleep(0.03)
    assert bus.agents["ada"].status == EventType.WAITING
    assert bus.agents["ada"].detail.startswith("Idle")
    await jobs.close()


def test_test_activity_reveals_framework_and_result_without_arguments():
    events = []
    observer = CodexObserver(lambda kind, detail: events.append((kind, detail)))
    command = "python3 -m pytest --private-token SECRET"
    observer.consume(
        {"type": "item.started", "item": {"type": "command_execution", "command": command}}
    )
    observer.consume(
        {
            "type": "item.completed",
            "item": {
                "type": "command_execution",
                "command": command,
                "exit_code": 0,
                "aggregated_output": "SECRET",
            },
        }
    )
    assert events[0] == (EventType.TESTING, "CLI: python -m pytest · RUNNING")
    assert events[1] == (EventType.TESTING, "CLI: python -m pytest · PASS (exit 0)")
    assert "SECRET" not in repr(events)


async def test_reply_waits_for_busy_recipient_and_cancel_discards_queue(tmp_path):
    class BlockingAdapter:
        async def run(self, prompt, workspace, emit):
            await asyncio.Event().wait()

    jobs = JobManager(EventBus(), BlockingAdapter(), tmp_path)
    jobs.submit("turing", "Busy task")
    await jobs.send_message("ada", "turing", "API contract ready", request_reply=True)
    assert len(jobs.pending["turing"]) == 1
    assert await jobs.cancel("turing")
    assert not jobs.pending["turing"]
    assert not jobs.running
    await jobs.close()


def test_other_test_framework_cannot_hide_failing_suite():
    observer = CodexObserver(lambda *_: None)
    for command, code in [("pytest", 1), ("python3 -m unittest", 0)]:
        observer.consume(
            {
                "type": "item.completed",
                "item": {"type": "command_execution", "command": command, "exit_code": code},
            }
        )
    observer.consume({"type": "turn.completed"})
    assert not observer.successful
    observer.consume(
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "python3 -m pytest", "exit_code": 0},
        }
    )
    assert observer.successful


async def test_silent_model_response_is_not_claimed_as_peer_exchange(tmp_path):
    class SilentAdapter:
        async def run(self, prompt, workspace, emit):
            return RunResult(True, "Text response only")

    jobs = JobManager(EventBus(), SilentAdapter(), tmp_path)
    await jobs.send_message("ada", "turing", "Please confirm the API", request_reply=True)
    await wait_until_idle(jobs)
    record = next(iter(jobs.history.values()))
    assert record["status"] == "error"
    assert "did not publish" in record["detail"]
    await jobs.close()


async def test_full_reply_queue_rejects_new_request_without_losing_old_requests(tmp_path):
    class BlockingAdapter:
        async def run(self, prompt, workspace, emit):
            await asyncio.Event().wait()

    jobs = JobManager(EventBus(), BlockingAdapter(), tmp_path)
    jobs.submit("turing", "Busy task")
    for index in range(4):
        await jobs.send_message("ada", "turing", f"Question {index}", request_reply=True)
    with pytest.raises(BusyError):
        await jobs.send_message("ada", "turing", "Overflow question", request_reply=True)
    assert len(jobs.pending["turing"]) == 4
    assert "Question 0" in jobs.pending["turing"][0][1]
    assert "Overflow" not in (tmp_path / "turing/.cafe/inbox.jsonl").read_text()
    await jobs.close()

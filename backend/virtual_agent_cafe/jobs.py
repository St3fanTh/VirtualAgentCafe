import asyncio
from collections import OrderedDict, deque
from pathlib import Path
from uuid import UUID, uuid4

from .adapters.base import AgentAdapter, RunResult
from .bus import EventBus
from .messaging import ROLES, PeerMessage, deliver_inbox, prepare_helper, read_outbox
from .models import EventType


class BusyError(Exception):
    pass


class JobManager:
    def __init__(self, bus: EventBus, adapter: AgentAdapter, root: Path, idle_delay: float = 3):
        self.bus = bus
        self.adapter = adapter
        self.root = root.resolve()
        self.running: dict[str, asyncio.Task] = {}
        self.history: OrderedDict[str, dict] = OrderedDict()
        self.pending = {agent: deque(maxlen=4) for agent in ROLES}
        self.closing = False
        self.idle_delay = idle_delay
        self.idle_tasks: dict[str, asyncio.Task] = {}

    def submit(self, agent_id: str, prompt: str, *, reply_to: str | None = None) -> dict:
        if agent_id in self.running:
            raise BusyError("Agent already has a running task")
        if agent_id not in self.bus.agents:
            raise ValueError("Unknown agent")
        idle = self.idle_tasks.pop(agent_id, None)
        if idle:
            idle.cancel()
        correlation = uuid4()
        record = {
            "task_id": str(correlation),
            "agent_id": agent_id,
            "role": ROLES[agent_id],
            "status": "running",
            "workspace": str(self.root / agent_id),
            "response_file": str(self.root / agent_id / ".cafe" / "last-response.md"),
        }
        self.history[str(correlation)] = record
        while len(self.history) > 100:
            self.history.popitem(last=False)
        self.running[agent_id] = asyncio.create_task(
            self.execute(agent_id, prompt, correlation, reply_to)
        )
        self.running[agent_id].add_done_callback(lambda completed: self.forget(agent_id, completed))
        self.bus.emit(
            agent_id, EventType.STARTED, correlation, source="codex", detail="Codex task accepted"
        )
        return record.copy()

    async def execute(
        self, agent_id: str, prompt: str, correlation: UUID, reply_to: str | None = None
    ) -> None:
        def emit(kind: EventType, detail: str):
            self.bus.emit(agent_id, kind, correlation, source="codex", detail=detail)

        watcher = None
        offset = 0
        seen_messages = set()

        async def drain():
            nonlocal offset
            offset, messages = await asyncio.to_thread(read_outbox, self.root, agent_id, offset)
            for raw in messages:
                try:
                    message = PeerMessage.model_validate(raw)
                except ValueError:
                    continue
                if message.task_id != correlation or message.message_id in seen_messages:
                    continue
                if message.recipient == agent_id or len(seen_messages) >= 4:
                    continue
                seen_messages.add(message.message_id)
                await self.send_message(
                    agent_id,
                    message.recipient,
                    message.text,
                    correlation=correlation,
                    source="codex",
                    request_reply=not message.reply,
                )

        async def watch():
            while True:
                await drain()
                await asyncio.sleep(0.15)

        try:
            workspace = self.root / agent_id
            # Resolve and reject symlink escape, including an existing per-agent directory.
            if not workspace.resolve().is_relative_to(self.root):
                raise ValueError("Invalid workspace")
            workspace.mkdir(parents=True, exist_ok=True)
            if not (workspace / ".git").exists():
                init = await asyncio.create_subprocess_exec(
                    "git",
                    "init",
                    "-q",
                    str(workspace),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                if await init.wait() != 0:
                    raise RuntimeError("Could not initialize task workspace")
            offset = await asyncio.to_thread(
                prepare_helper, self.root, agent_id, correlation, reply_to is not None
            )
            watcher = asyncio.create_task(watch())
            peer = "turing" if agent_id == "ada" else "ada"
            context = (
                f"You are {agent_id.capitalize()}, the {ROLES[agent_id]} engineer. "
                "Work on your assigned task in this workspace. Use file-edit tools for changes. "
                "Run relevant tests. .cafe/inbox.jsonl contains explicitly public peer messages. "
                f"To collaborate, run python3 .cafe/send_message.py {peer} 'short public message'. "
                "Messages are public: never include secrets, private prompts or raw outputs. "
                "Only send messages when useful. Do not commit or push task artifacts.\n"
            )
            if reply_to:
                context += (
                    f"This is a peer reply task: respond once to {reply_to} using the helper "
                    "and --reply. Do not ask follow-up questions or change project files.\n"
                )
            result = await self.adapter.run(context + "Assigned task:\n" + prompt, workspace, emit)
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            watcher = None
            await drain()
            if reply_to and result.success and not seen_messages:
                result = RunResult(False, "Peer reply did not publish a public message")
            record = self.history.get(str(correlation))
            if record is not None:
                record["status"] = "finished" if result.success else "error"
                record["detail"] = result.reason
            emit(EventType.FINISHED if result.success else EventType.ERROR, result.reason)
        except asyncio.CancelledError:
            record = self.history.get(str(correlation))
            if record is not None:
                record["status"] = "cancelled"
            if record is None or record.get("detail") != "Codex task cancelled":
                emit(EventType.ERROR, "Codex task cancelled")
            raise
        except Exception:
            record = self.history.get(str(correlation))
            if record is not None:
                record["status"] = "error"
                record["detail"] = "Task execution failed"
            emit(EventType.ERROR, "Task execution failed")
        finally:
            if watcher:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            self.forget(agent_id, asyncio.current_task())

    def forget(self, agent_id: str, completed: asyncio.Task) -> None:
        if self.running.get(agent_id) is completed:
            self.running.pop(agent_id, None)
            if not self.closing:
                if self.pending[agent_id]:
                    sender, text = self.pending[agent_id].popleft()
                    self.submit(agent_id, text, reply_to=sender)
                elif self.bus.agents[agent_id].status == EventType.FINISHED:
                    self.idle_tasks[agent_id] = asyncio.create_task(self.become_idle(agent_id))

    async def become_idle(self, agent_id: str):
        correlation = self.bus.agents[agent_id].correlation_id
        await asyncio.sleep(self.idle_delay)
        if (
            agent_id not in self.running
            and self.bus.agents[agent_id].correlation_id == correlation
            and self.bus.agents[agent_id].status in {EventType.FINISHED, EventType.MESSAGE}
        ):
            self.bus.emit(
                agent_id,
                EventType.WAITING,
                correlation,
                detail="Idle — ready for tasks",
                source="system",
            )

    async def send_message(
        self,
        sender: str,
        recipient: str,
        text: str,
        *,
        correlation: UUID | None = None,
        source: str = "system",
        request_reply: bool = False,
    ) -> UUID:
        if sender == recipient or sender not in ROLES or recipient not in ROLES:
            raise ValueError("Choose the other agent")
        if not text.strip() or len(text) > 256:
            raise ValueError("Invalid public message")
        correlation = correlation or uuid4()
        await asyncio.to_thread(deliver_inbox, self.root, recipient, sender, text, correlation)
        self.bus.emit(
            sender, EventType.MESSAGE, correlation, source=source, detail=text, recipient=recipient
        )
        self.bus.emit(
            recipient,
            EventType.MESSAGE,
            correlation,
            source=source,
            detail=f"{sender.capitalize()}: {text}"[:256],
            recipient=sender,
        )
        if request_reply and not self.closing:
            prompt = f"Public message from {sender} ({ROLES[sender]}): {text}"
            if recipient in self.running:
                self.pending[recipient].append((sender, prompt))
            else:
                self.submit(recipient, prompt, reply_to=sender)
        for agent in (sender, recipient):
            if agent not in self.running and not self.closing:
                previous = self.idle_tasks.pop(agent, None)
                if previous:
                    previous.cancel()
                self.idle_tasks[agent] = asyncio.create_task(self.become_idle(agent))
        return correlation

    async def cancel(self, agent_id: str) -> bool:
        task = self.running.get(agent_id)
        if task is None:
            return False
        record = next(
            (
                r
                for r in reversed(self.history.values())
                if r["agent_id"] == agent_id and r["status"] == "running"
            ),
            None,
        )
        if record is not None:
            record["status"] = "cancelled"
            record["detail"] = "Codex task cancelled"
            self.bus.emit(
                agent_id,
                EventType.ERROR,
                UUID(record["task_id"]),
                source="codex",
                detail="Codex task cancelled",
            )
        self.pending[agent_id].clear()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.forget(agent_id, task)
        return True

    async def close(self) -> None:
        self.closing = True
        await asyncio.gather(*(self.cancel(agent) for agent in list(self.running)))
        for task in self.idle_tasks.values():
            task.cancel()
        await asyncio.gather(*self.idle_tasks.values(), return_exceptions=True)

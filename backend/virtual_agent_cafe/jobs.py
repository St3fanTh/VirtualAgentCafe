import asyncio
from collections import OrderedDict
from pathlib import Path
from uuid import UUID, uuid4

from .adapters.base import AgentAdapter
from .bus import EventBus
from .models import EventType


class BusyError(Exception):
    pass


class JobManager:
    def __init__(self, bus: EventBus, adapter: AgentAdapter, root: Path):
        self.bus = bus
        self.adapter = adapter
        self.root = root.resolve()
        self.running: dict[str, asyncio.Task] = {}
        self.history: OrderedDict[str, dict] = OrderedDict()

    def submit(self, agent_id: str, prompt: str) -> dict:
        if agent_id in self.running:
            raise BusyError("Agent already has a running task")
        if agent_id not in self.bus.agents:
            raise ValueError("Unknown agent")
        correlation = uuid4()
        record = {
            "task_id": str(correlation),
            "agent_id": agent_id,
            "status": "running",
            "workspace": str(self.root / agent_id),
            "response_file": str(self.root / agent_id / ".cafe" / "last-response.md"),
        }
        self.history[str(correlation)] = record
        while len(self.history) > 100:
            self.history.popitem(last=False)
        self.running[agent_id] = asyncio.create_task(self.execute(agent_id, prompt, correlation))
        self.running[agent_id].add_done_callback(lambda completed: self.forget(agent_id, completed))
        self.bus.emit(
            agent_id, EventType.STARTED, correlation, source="codex", detail="Codex task accepted"
        )
        return record.copy()

    async def execute(self, agent_id: str, prompt: str, correlation: UUID) -> None:
        def emit(kind: EventType, detail: str):
            self.bus.emit(agent_id, kind, correlation, source="codex", detail=detail)

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
            result = await self.adapter.run(prompt, workspace, emit)
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
            self.forget(agent_id, asyncio.current_task())

    def forget(self, agent_id: str, completed: asyncio.Task) -> None:
        if self.running.get(agent_id) is completed:
            self.running.pop(agent_id, None)

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
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        self.forget(agent_id, task)
        return True

    async def close(self) -> None:
        await asyncio.gather(*(self.cancel(agent) for agent in list(self.running)))

import asyncio
import json
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .adapters.base import AgentAdapter
from .adapters.codex import CodexAdapter
from .bus import EventBus
from .jobs import BusyError, JobManager
from .simulator import simulate


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str = Field(min_length=1, max_length=8000)

    @field_validator("prompt")
    @classmethod
    def meaningful(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Prompt is empty")
        return value.strip()


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recipient: str = Field(pattern="^(ada|turing)$")
    text: str = Field(min_length=1, max_length=256)
    request_reply: bool = False

    @field_validator("text")
    @classmethod
    def meaningful(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message is empty")
        return value.strip()


async def validated_body(request: Request, model: type[BaseModel]):
    if request.headers.get("origin") is not None:
        raise HTTPException(403, "Browser task submission is disabled")
    if request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
        raise HTTPException(415, "Expected application/json")
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > 32768:
            raise HTTPException(413, "Request exceeds 32 KiB")
        chunks.extend(chunk)
    try:
        return model.model_validate(json.loads(chunks))
    except (ValueError, ValidationError):
        # Do not include user input in validation errors or access logs.
        raise HTTPException(422, "Invalid request fields or size") from None


def create_app(
    mode: str = "demo",
    interval: float = 1.0,
    *,
    adapter: AgentAdapter | None = None,
    workspace_root: Path | None = None,
) -> FastAPI:
    if mode not in {"demo", "codex"}:
        raise ValueError("mode must be demo or codex")
    if interval <= 0:
        raise ValueError("interval must be positive")
    bus = EventBus()
    jobs = JobManager(
        bus,
        adapter or CodexAdapter(timeout=float(os.getenv("VAC_TASK_TIMEOUT", "300"))),
        workspace_root or Path(os.getenv("VAC_TASK_ROOT", ".runtime/workspaces")),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        demo = asyncio.create_task(simulate(bus, interval)) if mode == "demo" else None
        try:
            yield
        finally:
            await jobs.close()
            if demo:
                demo.cancel()
                with suppress(asyncio.CancelledError):
                    await demo

    app = FastAPI(title="VirtualAgentCafe", lifespan=lifespan)
    app.state.bus = bus
    app.state.mode = mode
    app.state.jobs = jobs
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
    )

    def live_agent(agent_id: str):
        if agent_id not in bus.agents:
            raise HTTPException(404, "Unknown agent")
        if mode != "codex":
            raise HTTPException(409, "Start backend in Codex mode to submit tasks")

    @app.post("/agents/{agent_id}/tasks", status_code=202)
    async def submit_task(agent_id: str, request: Request):
        live_agent(agent_id)
        data = await validated_body(request, TaskInput)
        try:
            return jobs.submit(agent_id, data.prompt)
        except BusyError:
            raise HTTPException(409, "Agent already has a running task") from None

    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str):
        record = jobs.history.get(task_id)
        if record is None:
            raise HTTPException(404, "Task not found")
        return record.copy()

    @app.post("/agents/{agent_id}/cancel")
    async def cancel_task(agent_id: str, request: Request):
        live_agent(agent_id)
        if request.headers.get("origin") is not None:
            raise HTTPException(403, "Browser task submission is disabled")
        if not await jobs.cancel(agent_id):
            raise HTTPException(409, "Agent has no running task")
        return {"status": "cancelled"}

    @app.post("/agents/{agent_id}/messages", status_code=202)
    async def send_message(agent_id: str, request: Request):
        live_agent(agent_id)
        data = await validated_body(request, MessageInput)
        if data.recipient == agent_id:
            raise HTTPException(422, "Choose the other agent")
        try:
            correlation = await jobs.send_message(
                agent_id, data.recipient, data.text, request_reply=data.request_reply
            )
        except BusyError:
            raise HTTPException(429, "Peer reply queue is full") from None
        return {"status": "delivered", "correlation_id": str(correlation)}

    @app.get("/health")
    async def health():
        return {"status": "ok", "mode": mode, "protocol_version": 1}

    @app.get("/agents")
    async def agents():
        return bus.snapshot()

    @app.websocket("/ws/events")
    async def events(socket: WebSocket):
        # Native Godot has no Origin; browser access is intentionally restricted.
        origin = socket.headers.get("origin")
        if origin is not None:
            await socket.close(code=1008)
            return
        await socket.accept()
        queue = bus.subscribe()

        async def send():
            while True:
                frame = await queue.get()
                async with asyncio.timeout(10):
                    await socket.send_json(frame)

        async def receive():
            while True:
                # No inbound commands or private prompts over this public activity stream.
                await socket.receive_text()

        sender = asyncio.create_task(send())
        receiver = asyncio.create_task(receive())
        try:
            done, _ = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        except (WebSocketDisconnect, TimeoutError, RuntimeError, asyncio.CancelledError):
            pass
        finally:
            sender.cancel()
            receiver.cancel()
            bus.unsubscribe(queue)
            with suppress(asyncio.CancelledError):
                await asyncio.gather(sender, receiver, return_exceptions=True)

    return app


app = create_app(os.getenv("VAC_MODE", "demo"), float(os.getenv("VAC_DEMO_INTERVAL", "1")))

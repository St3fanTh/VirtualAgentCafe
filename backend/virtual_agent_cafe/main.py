import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .bus import EventBus
from .simulator import simulate


def create_app(mode: str = "demo", interval: float = 1.0) -> FastAPI:
    if mode not in {"demo", "codex"}:
        raise ValueError("mode must be demo or codex")
    if interval <= 0:
        raise ValueError("interval must be positive")
    bus = EventBus()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        demo = asyncio.create_task(simulate(bus, interval)) if mode == "demo" else None
        yield
        if demo:
            demo.cancel()
            with suppress(asyncio.CancelledError):
                await demo

    app = FastAPI(title="VirtualAgentCafe", lifespan=lifespan)
    app.state.bus = bus
    app.state.mode = mode

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
        except (WebSocketDisconnect, TimeoutError, RuntimeError):
            pass
        finally:
            sender.cancel()
            receiver.cancel()
            await asyncio.gather(sender, receiver, return_exceptions=True)
            bus.unsubscribe(queue)

    return app


app = create_app(os.getenv("VAC_MODE", "demo"), float(os.getenv("VAC_DEMO_INTERVAL", "1")))

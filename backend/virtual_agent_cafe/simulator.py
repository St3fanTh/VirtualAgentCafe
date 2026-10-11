import asyncio
from uuid import uuid4

from .bus import EventBus
from .models import EventType

DEMO = [
    ("ada", EventType.STARTED, "Demo task started", None),
    ("turing", EventType.STARTED, "Demo review started", None),
    ("ada", EventType.THINKING, "Demo model call", None),
    ("turing", EventType.WAITING, "Waiting for Ada", None),
    ("ada", EventType.CODING, "Editing demo module", None),
    ("ada", EventType.TESTING, "Running demo tests", None),
    ("ada", EventType.MESSAGE, "Tests passed. Please review!", "turing"),
    ("turing", EventType.MESSAGE, "Review received. Checking now.", "ada"),
    ("turing", EventType.TESTING, "Checking demo changes", None),
    ("ada", EventType.FINISHED, "Demo implementation complete", None),
    ("turing", EventType.FINISHED, "Demo review complete", None),
]


async def simulate(bus: EventBus, interval: float = 1.0, repeat: bool = True) -> None:
    if interval <= 0:
        raise ValueError("interval must be positive")
    while True:
        correlation = uuid4()
        for agent, kind, detail, recipient in DEMO:
            bus.emit(agent, kind, correlation, source="demo", detail=detail, recipient=recipient)
            await asyncio.sleep(interval)
        if not repeat:
            return
        await asyncio.sleep(interval * 3)

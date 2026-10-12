import asyncio
from collections import deque
from uuid import UUID

from .models import AgentState, Event, EventType, Payload


class EventBus:
    """Single event-loop owner; publish and subscribe never yield or block producers."""

    def __init__(self, queue_limit: int = 64):
        if queue_limit < 1:
            raise ValueError("queue_limit must be positive")
        self.queue_limit = queue_limit
        self.sequence = 0
        self.agents = {
            "ada": AgentState(agent_id="ada", name="Ada", role="backend"),
            "turing": AgentState(agent_id="turing", name="Turing", role="frontend"),
        }
        self.subscribers: set[asyncio.Queue] = set()
        self.recent_ids: deque[UUID] = deque(maxlen=1024)
        self.seen: set[UUID] = set()

    def snapshot(self) -> dict:
        return {
            "kind": "snapshot",
            "version": 1,
            "sequence": self.sequence,
            "agents": [a.model_dump(mode="json") for a in self.agents.values()],
        }

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=self.queue_limit)
        self.subscribers.add(queue)
        queue.put_nowait(self.snapshot())
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self.subscribers.discard(queue)

    def emit(self, agent_id: str, kind: EventType, correlation_id: UUID, **payload) -> Event:
        event = Event(
            agent_id=agent_id,
            type=kind,
            sequence=self.sequence + 1,
            correlation_id=correlation_id,
            payload=Payload(**payload),
        )
        self.publish(event)
        return event

    def publish(self, event: Event) -> bool:
        if event.event_id in self.seen:
            return False
        if event.sequence != self.sequence + 1:
            raise ValueError("Events must have consecutive global sequence numbers")
        self.sequence = event.sequence
        if len(self.recent_ids) == self.recent_ids.maxlen:
            self.seen.remove(self.recent_ids[0])
        self.recent_ids.append(event.event_id)
        self.seen.add(event.event_id)
        state = self.agents[event.agent_id]
        self.agents[event.agent_id] = state.model_copy(
            update={
                "status": event.type,
                "sequence": event.sequence,
                "correlation_id": event.correlation_id,
                "detail": event.payload.detail,
                "source": event.payload.source,
                "recipient": event.payload.recipient,
            }
        )
        frame = {"kind": "event", "version": 1, "event": event.model_dump(mode="json")}
        for queue in self.subscribers:
            if queue.full():
                # Drop transient history, recover authoritative state without blocking producers.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(self.snapshot())
            else:
                queue.put_nowait(frame)
        return True

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.models import Event, EventType, Payload
from virtual_agent_cafe.simulator import DEMO, simulate


def event(sequence=1, **values):
    return Event(
        agent_id="ada", type="agent.coding", sequence=sequence, correlation_id=uuid4(), **values
    )


@pytest.mark.parametrize(
    "values",
    [
        {"agent_id": "unknown"},
        {"type": "random"},
        {"sequence": 0},
        {"payload": {"detail": "x" * 257}},
        {"payload": {"secret": "hidden"}},
        {"unknown": True},
    ],
)
def test_invalid_events(values):
    data = event().model_dump()
    data.update(values)
    with pytest.raises(ValidationError):
        Event.model_validate(data)


def test_payload_is_bounded_and_typed():
    assert Payload(source="codex", recipient="ada").source == "codex"
    with pytest.raises(ValidationError):
        Payload(source="invented")


def test_order_duplicates_states_and_overflow():
    bus = EventBus(queue_limit=2)
    queue = bus.subscribe()
    assert queue.get_nowait()["kind"] == "snapshot"
    first = event()
    assert bus.publish(first)
    assert not bus.publish(first)
    with pytest.raises(ValueError):
        bus.publish(event(3))
    bus.publish(event(2))
    bus.publish(event(3))
    snapshot = queue.get_nowait()
    assert snapshot["kind"] == "snapshot"
    assert snapshot["sequence"] == 3
    assert snapshot["agents"][0]["status"] == "agent.coding"
    assert queue.qsize() == 0
    bus.unsubscribe(queue)
    assert not bus.subscribers


@pytest.mark.parametrize("kind", list(EventType))
def test_every_state_transition(kind):
    bus = EventBus()
    bus.emit("ada", kind, uuid4())
    assert bus.agents["ada"].status == kind


async def test_simulator_end_to_end_order():
    bus = EventBus()
    queue = bus.subscribe()
    queue.get_nowait()
    await simulate(bus, interval=0.001, repeat=False)
    frames = [queue.get_nowait() for _ in DEMO]
    assert [f["event"]["sequence"] for f in frames] == list(range(1, len(DEMO) + 1))
    assert [f["event"]["type"] for f in frames] == [entry[1] for entry in DEMO]
    assert bus.agents["turing"].status == EventType.FINISHED


def test_api_websocket_and_reconnect():
    app = create_app(mode="codex")
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert len(client.get("/agents").json()["agents"]) == 2
        with client.websocket_connect("/ws/events") as ws:
            assert ws.receive_json()["kind"] == "snapshot"
            client.portal.call(app.state.bus.emit, "ada", EventType.CODING, uuid4())
            assert ws.receive_json()["event"]["type"] == "agent.coding"
        with client.websocket_connect("/ws/events") as ws:
            assert ws.receive_json()["agents"][0]["status"] == "agent.coding"
    assert not app.state.bus.subscribers


def test_live_demo_websocket():
    with TestClient(create_app(interval=0.005)) as client:
        with client.websocket_connect("/ws/events") as ws:
            assert ws.receive_json()["kind"] == "snapshot"
            types = set()
            for _ in range(30):
                types.add(ws.receive_json()["event"]["type"])
                if {"agent.coding", "agent.testing", "agent.message", "agent.finished"} <= types:
                    break
            assert {"agent.coding", "agent.testing", "agent.message", "agent.finished"} <= types


def test_timestamp_requires_timezone():
    with pytest.raises(ValidationError):
        event(timestamp="2026-10-11T12:00:00")


def test_event_burst_keeps_memory_and_subscriber_queues_bounded():
    bus = EventBus(queue_limit=4)
    queues = [bus.subscribe() for _ in range(4)]
    correlation = uuid4()
    for _ in range(5000):
        bus.emit("ada", EventType.CODING, correlation, source="demo")
    assert bus.sequence == 5000
    assert len(bus.seen) == len(bus.recent_ids) == 1024
    assert all(queue.qsize() <= 4 for queue in queues)
    snapshot = bus.snapshot()
    assert snapshot["agents"][0]["sequence"] == 5000

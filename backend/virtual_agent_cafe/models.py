from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EventType(StrEnum):
    STARTED = "agent.started"
    THINKING = "agent.thinking"
    CODING = "agent.coding"
    TESTING = "agent.testing"
    MESSAGE = "agent.message"
    WAITING = "agent.waiting"
    ERROR = "agent.error"
    FINISHED = "agent.finished"


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source: Literal["demo", "codex", "system"] = "system"
    detail: str = Field(default="", max_length=256)
    recipient: Literal["ada", "turing"] | None = None


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: UUID = Field(default_factory=uuid4)
    agent_id: Literal["ada", "turing"]
    type: EventType
    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    sequence: int = Field(ge=1)
    correlation_id: UUID
    payload: Payload = Field(default_factory=Payload)


class AgentState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    agent_id: Literal["ada", "turing"]
    name: str
    status: EventType = EventType.WAITING
    sequence: int = 0
    correlation_id: UUID | None = None
    detail: str = "Ready"
    source: Literal["demo", "codex", "system"] = "system"
    recipient: Literal["ada", "turing"] | None = None

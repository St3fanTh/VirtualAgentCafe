from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from ..models import EventType

Emit = Callable[[EventType, str], None]


@dataclass(frozen=True)
class RunResult:
    success: bool
    reason: str


class AgentAdapter(Protocol):
    async def run(self, prompt: str, workspace: Path, emit: Emit) -> RunResult: ...

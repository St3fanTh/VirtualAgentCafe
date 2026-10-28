from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
MarkdownRef = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}\.md$")]


class State(StrEnum):
    CREATED = "CREATED"
    CONFIGURED = "CONFIGURED"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TaskState(StrEnum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GitConfig(StrictModel):
    enabled: bool = False
    repository: Identifier | None = None
    branch: str | None = Field(default=None, max_length=160)
    worktree: bool = True
    remote_name: str = Field(default="origin", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
    auto_commit: Literal[False] = False
    allow_push: bool = False
    push_on_success: bool = False
    allow_pull: bool = False
    allow_fetch: bool = False

    @model_validator(mode="after")
    def connected(self):
        if self.enabled and not self.repository:
            raise ValueError("Git requires a repository workspace")
        if self.push_on_success and not (self.enabled and self.allow_push):
            raise ValueError("Publishing requires Git enabled and explicit push permission")
        return self


class ExecutionConfig(StrictModel):
    integration_validation: bool = False
    repair_attempts: int = Field(default=3, ge=1, le=5)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_retries: int = Field(default=0, ge=0, le=2)


class AgentConfig(StrictModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=80)
    provider: Literal["codex"] = "codex"
    workspace: Identifier
    task: MarkdownRef | None = None
    roles: list[MarkdownRef] = Field(default_factory=list, max_length=16)
    git: GitConfig = Field(default_factory=GitConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)

    @model_validator(mode="after")
    def reserved(self):
        if self.id in {"ada", "turing"}:
            raise ValueError("Legacy café IDs are reserved")
        if len(self.roles) != len(set(self.roles)):
            raise ValueError("Duplicate role")
        if self.git.enabled and not self.git.worktree and self.git.repository != self.workspace:
            raise ValueError("Ordinary Git workspace must be its configured repository")
        return self


class MarkdownInput(StrictModel):
    content: str = Field(min_length=1, max_length=16000)


class WorkspaceInput(StrictModel):
    id: Identifier


class ReviewInput(StrictModel):
    accepted: bool
    note: str = Field(min_length=1, max_length=256)

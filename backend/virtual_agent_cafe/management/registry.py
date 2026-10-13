import json

from .config import AgentConfig, State, TaskState
from .files import ApprovedFiles, MarkdownManager, WorkspaceManager
from .storage import Store


class AgentRegistry:
    def __init__(
        self,
        store: Store,
        configs: ApprovedFiles,
        tasks: MarkdownManager,
        roles: MarkdownManager,
        workspaces: WorkspaceManager,
    ):
        self.store, self.configs = store, configs
        self.tasks, self.roles, self.workspaces = tasks, roles, workspaces

    def save(self, config: AgentConfig) -> dict:
        try:
            previous = self.store.get("agents", config.id)
        except KeyError:
            previous = None
        if previous and previous["state"] == State.RUNNING:
            raise ValueError("Stop the agent before changing its configuration")
        self.workspaces.get(config.workspace)
        for role in config.roles:
            self.roles.load(role)
        if config.task:
            self.tasks.load(config.task)
        if config.git.enabled:
            self.workspaces.get(config.git.repository)
        record = {
            "config": config.model_dump(mode="json"),
            "state": State.CONFIGURED,
            "task_state": TaskState.ASSIGNED if config.task else TaskState.PENDING,
        }
        # Human-readable configuration export contains references, never credentials.
        path = self.configs.path(config.id + ".json")
        path.write_text(json.dumps(record["config"], indent=2) + "\n", encoding="utf-8")
        self.store.put("agents", config.id, record)
        return record

    def get(self, identifier: str) -> dict:
        return self.store.get("agents", identifier)

    def update(self, identifier: str, **changes) -> dict:
        record = self.get(identifier)
        record.update(changes)
        self.store.put("agents", identifier, record)
        return record

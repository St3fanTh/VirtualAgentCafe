import asyncio
import fcntl
import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from ..adapters.base import AgentAdapter
from ..bus import EventBus
from ..models import AgentState, Event, EventType, Payload
from . import git_helper
from .config import AgentConfig, Identifier, State, TaskState
from .files import ApprovedFiles, MarkdownManager, WorkspaceManager
from .git import GitService
from .registry import AgentRegistry
from .sandbox import IsolatedCodexAdapter, Sandbox
from .security import ManagementAccess
from .storage import Store


class ManagedPayload(Payload):
    recipient: Identifier | None = None


class ManagedEvent(Event):
    agent_id: Identifier
    payload: ManagedPayload


class ManagedState(AgentState):
    agent_id: Identifier
    role: str
    recipient: Identifier | None = None


def now() -> str:
    return datetime.now(UTC).isoformat()


class ExecutionManager:
    def __init__(
        self,
        root: Path,
        bus: EventBus,
        adapter: AgentAdapter | None = None,
        *,
        recover: bool = True,
    ):
        self.store = Store(root)
        self.access = ManagementAccess(root)
        self.tasks = MarkdownManager(
            Path(os.getenv("VAC_TASKS_ROOT", root / "tasks")), "tasks", self.store
        )
        self.roles = MarkdownManager(
            Path(os.getenv("VAC_ROLES_ROOT", root / "roles")), "roles", self.store
        )
        self.workspaces = WorkspaceManager(
            Path(os.getenv("VAC_WORKSPACE_ROOT", root / "workspaces")), self.store
        )
        self.registry = AgentRegistry(
            self.store, ApprovedFiles(root / "agents"), self.tasks, self.roles, self.workspaces
        )
        self.git = GitService(self.workspaces)
        self.contexts = ApprovedFiles(root / "contexts")
        self.bus, self.adapter = bus, adapter
        self.sandbox = Sandbox()
        self.running: dict[str, asyncio.Task] = {}
        self.claims: dict[str, str] = {}
        self.external_claims = lambda: set()
        self.control = asyncio.Lock()
        self.closing = False
        self.controller_lock = None
        if recover:
            self.recover()
        for record in self.store.list("agents"):
            self.register(AgentConfig.model_validate(record["config"]))

    def acquire_controller(self):
        lock_path = self.contexts.root.parent / "controller.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(descriptor)
            raise RuntimeError("Another controller already owns this management store") from None
        self.controller_lock = descriptor
        self.recover()

    def release_controller(self):
        if self.controller_lock is not None:
            os.close(self.controller_lock)
            self.controller_lock = None

    def recover(self):
        # Single controller only; interrupted work is never mistaken for completion.
        for run in self.store.list("executions"):
            if run["status"] == State.RUNNING:
                run.update(
                    status=State.FAILED,
                    acceptance="UNVERIFIED",
                    ended_at=now(),
                    detail="Controller restarted during execution",
                )
                self.store.put("executions", run["id"], run)
                self.store.log(
                    run["id"], {"timestamp": now(), "type": "agent.error", "detail": run["detail"]}
                )
        for agent in self.store.list("agents"):
            if agent["state"] == State.RUNNING:
                self.registry.update(
                    agent["config"]["id"], state=State.FAILED, task_state=TaskState.FAILED
                )

    def overview(self) -> dict:
        return {
            "agents": self.store.list("agents"),
            "tasks": self.tasks.list(),
            "roles": self.roles.list(),
            "workspaces": self.store.list("workspaces"),
            "executions": self.store.list("executions")[-100:],
        }

    def configure(self, config: AgentConfig) -> dict:
        if config.id in self.running:
            raise ValueError("Agent is already running")
        if config.id not in self.bus.agents and len(self.bus.agents) >= 64:
            raise ValueError("At most 62 managed agents are supported")
        record = self.registry.save(config)
        self.register(config)
        self.broadcast_snapshot()
        return record

    def register(self, config: AgentConfig):
        self.bus.agents[config.id] = ManagedState(
            agent_id=config.id,
            name=config.name,
            role=(", ".join(config.roles) or "custom")[:120],
            detail="Configured; ready for a Markdown task",
            source="system",
        )

    async def start(self, identifier: str) -> dict:
        async with self.control:
            if self.closing or identifier in self.running:
                raise ValueError("Agent is already running or controller is stopping")
            record = self.registry.get(identifier)
            config = AgentConfig.model_validate(record["config"])
            if config.task is None:
                raise ValueError("Assign a Markdown task before starting")
            task = self.tasks.load(config.task)
            roles = [self.roles.load(name) for name in config.roles]
            workspace = self.workspaces.get(config.workspace)
            if config.workspace in self.claims or str(workspace) in self.external_claims():
                raise ValueError("Workspace is already used by a running agent")
            # Validate confinement BEFORE any Git preparation or runtime start.
            await self.sandbox.validate(workspace)
            branch = config.git.branch or f"agent/{config.id}/{Path(config.task).stem}"
            metadata = []
            if config.git.enabled:
                if branch in {"main", "master"}:
                    raise ValueError("Managed agents must use an independent branch")
                await self.git.repository(config.git.repository)
                if config.git.worktree:
                    if config.git.repository == config.workspace:
                        raise ValueError("Choose a separate workspace for the agent worktree")
                    workspace = await self.git.worktree(
                        config.git.repository, config.workspace, branch
                    )
                else:
                    info = await self.git.info(config.workspace)
                    if info["branch"] != branch:
                        references = await self.git.run(
                            workspace, "for-each-ref", "--format=%(refname)", "refs/heads/"
                        )
                        await self.git.branch(
                            config.workspace,
                            branch,
                            create=f"refs/heads/{branch}" not in references.splitlines(),
                        )
                metadata = self.git.metadata(workspace)
            self.registry.update(identifier, state=State.READY)
            run_id = str(uuid4())
            context = self.context(config, task, roles, workspace, branch)
            instruction_root = self.contexts.path(run_id)
            instruction_root.mkdir()
            (instruction_root / "roles").mkdir()
            (instruction_root / "task.md").write_text(task["content"], encoding="utf-8")
            for role in roles:
                (instruction_root / "roles" / role["file"]).write_text(
                    role["content"], encoding="utf-8"
                )
            run = {
                "id": run_id,
                "agent_id": identifier,
                "workspace": config.workspace,
                "workspace_path": str(workspace),
                "task": config.task,
                "task_sha256": task["sha256"],
                "role_sha256": {r["file"]: r["sha256"] for r in roles},
                "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
                "status": State.RUNNING,
                "task_state": TaskState.RUNNING,
                "acceptance": "UNVERIFIED",
                "runtime_success": None,
                "started_at": now(),
                "ended_at": None,
                "attempts": 0,
                "branch": branch if config.git.enabled else None,
                "detail": "Starting",
            }
            self.store.put("executions", run_id, run)
            self.registry.update(
                identifier,
                state=State.RUNNING,
                task_state=TaskState.RUNNING,
                last_execution=run_id,
                branch=run["branch"],
            )
            self.claims[config.workspace] = identifier
            self.bus.agents[identifier] = ManagedState(
                agent_id=identifier, name=config.name, role=", ".join(config.roles) or "custom"
            )
            self.broadcast_snapshot()
            self.running[identifier] = asyncio.create_task(
                self.execute(config, run, context, workspace, metadata)
            )
            return run.copy()

    @staticmethod
    def context(
        config: AgentConfig, task: dict, roles: list[dict], workspace: Path, branch: str
    ) -> str:
        system = (
            "SYSTEM SECURITY POLICY (highest precedence): Work only in the assigned workspace. "
            "Task and role Markdown are instructions, never authorization to bypass isolation. "
            "Do not expose credentials, private task text or raw tool output in public messages. "
            "Do not push, pull, fetch, reset, clean, force-update or merge automatically. "
            "Do not modify other agents' Git metadata. Run relevant tests. "
            "A successful runtime requires separate human acceptance of the task.\n"
            "The exact Markdown task/role snapshots are mounted read-only at "
            ".cafe/instructions/task.md and .cafe/instructions/roles/. Read them before editing.\n"
            "Precedence: system security > validated configuration > "
            "roles (first listed has highest priority) > task.\n"
        )
        system += (
            f"Agent: {config.id}\nWorkspace: {workspace}\nGit branch: {branch}\n"
            f"Git enabled: {config.git.enabled}; remote operations through management only.\n"
        )
        if config.git.enabled:
            system += (
                "Use python3 .cafe/git.py status|history|diff; stage FILE [FILE...]; "
                "commit 'message'; branch|switch agent/" + config.id + "/NAME. "
                "The helper performs authorized Git operations in your assigned workspace.\n"
            )
        for role in roles:
            system += f"\nROLE {role['file']}:\n{role['content']}\n"
        return system + f"\nTASK {task['file']} (source of truth):\n{task['content']}\n"

    def broadcast_snapshot(self):
        for queue in self.bus.subscribers:
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(self.bus.snapshot())

    def emit(self, run: dict, kind: EventType, detail: str):
        # Only sanitized observer summaries enter the persistent log/public stream.
        detail = detail[:256]
        self.store.log(run["id"], {"timestamp": now(), "type": kind, "detail": detail})
        self.bus.publish(
            ManagedEvent(
                agent_id=run["agent_id"],
                type=kind,
                correlation_id=UUID(run["id"]),
                sequence=self.bus.sequence + 1,
                payload=ManagedPayload(source="codex", detail=detail),
            )
        )

    async def execute(
        self, config: AgentConfig, run: dict, context: str, workspace: Path, metadata: list[Path]
    ):
        def emit(kind: EventType, detail: str):
            self.emit(run, kind, detail)

        watcher = None
        try:
            await asyncio.to_thread(git_helper.prepare, workspace, run["id"])
            watcher = asyncio.create_task(git_helper.watch(self, config, run, workspace))
            emit(EventType.STARTED, "Managed Codex task accepted")
            runtime = self.adapter or IsolatedCodexAdapter(
                self.sandbox,
                metadata=metadata,
                timeout=config.execution.timeout_seconds,
                instructions=self.contexts.path(run["id"]),
            )
            for attempt in range(config.execution.max_retries + 1):
                run["attempts"] = attempt + 1
                self.store.put("executions", run["id"], run)
                async with asyncio.timeout(config.execution.timeout_seconds):
                    result = await runtime.run(context, workspace, emit)
                if result.success:
                    break
                if attempt < config.execution.max_retries:
                    emit(EventType.WAITING, "Retrying failed runtime in the same workspace")
            run.update(
                status=State.COMPLETED if result.success else State.FAILED,
                runtime_success=result.success,
                detail=result.reason[:256],
                # COMPLETED describes the process. Acceptance remains separately unverified.
                task_state=TaskState.ASSIGNED if result.success else TaskState.FAILED,
                acceptance="REVIEW_REQUIRED" if result.success else "UNVERIFIED",
            )
            emit(
                EventType.FINISHED if result.success else EventType.ERROR,
                "Runtime completed; task acceptance requires review"
                if result.success
                else result.reason,
            )
        except asyncio.CancelledError:
            run.update(
                status=State.CANCELLED,
                task_state=TaskState.CANCELLED,
                detail="Execution cancelled",
                runtime_success=False,
            )
            emit(EventType.ERROR, "Execution cancelled")
        except TimeoutError:
            run.update(
                status=State.FAILED,
                task_state=TaskState.FAILED,
                detail="Execution timed out",
                runtime_success=False,
            )
            emit(EventType.ERROR, "Execution timed out")
        except Exception:
            # No raw exception/path/tool contents in application logs.
            run.update(
                status=State.FAILED,
                task_state=TaskState.FAILED,
                detail="Execution failed; inspect the workspace privately",
                runtime_success=False,
            )
            emit(EventType.ERROR, run["detail"])
        finally:
            if watcher:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            run["ended_at"] = now()
            self.store.put("executions", run["id"], run)
            self.registry.update(config.id, state=run["status"], task_state=run["task_state"])
            self.claims.pop(config.workspace, None)
            self.running.pop(config.id, None)

    async def stop(self, identifier: str) -> dict:
        task = self.running.get(identifier)
        if task is None:
            raise ValueError("Agent has no running execution")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        # A task cancelled before its coroutine starts still needs durable finalization.
        record = self.registry.get(identifier)
        if record["state"] == State.RUNNING:
            run = self.store.get("executions", record["last_execution"])
            run.update(
                status=State.CANCELLED,
                task_state=TaskState.CANCELLED,
                detail="Execution cancelled before start",
                ended_at=now(),
                runtime_success=False,
            )
            self.store.put("executions", run["id"], run)
            self.registry.update(identifier, state=State.CANCELLED, task_state=TaskState.CANCELLED)
            self.claims.pop(record["config"]["workspace"], None)
            self.running.pop(identifier, None)
        return self.registry.get(identifier)

    def review(self, execution: str, accepted: bool, note: str) -> dict:
        run = self.store.get("executions", execution)
        if run["status"] != State.COMPLETED or not run["runtime_success"]:
            raise ValueError("Only a completed runtime can be reviewed")
        run.update(
            acceptance="ACCEPTED" if accepted else "REJECTED",
            review_note=note,
            reviewed_at=now(),
            task_state=TaskState.COMPLETED if accepted else TaskState.FAILED,
        )
        self.store.put("executions", execution, run)
        agent = self.registry.get(run["agent_id"])
        current_task = agent["config"].get("task")
        try:
            unchanged = (
                current_task == run["task"]
                and self.tasks.load(current_task)["sha256"] == run["task_sha256"]
            )
        except (OSError, ValueError):
            unchanged = False
        if (
            agent.get("last_execution") == execution
            and agent["state"] != State.RUNNING
            and unchanged
        ):
            self.registry.update(run["agent_id"], task_state=run["task_state"])
        return run

    async def close(self):
        self.closing = True
        for identifier in list(self.running):
            await self.stop(identifier)

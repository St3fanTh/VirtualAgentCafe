import asyncio
import fcntl
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import TypeAdapter

from ..adapters.base import AgentAdapter, RunResult
from ..bus import EventBus
from ..models import AgentState, Event, EventType, Payload
from . import git_helper, validation
from .config import AgentConfig, Identifier, State, TaskState
from .conversations import Conversations
from .files import ApprovedFiles, MarkdownManager, WorkspaceManager
from .git import GitOperationError, GitService
from .integration import Integrations
from .project_documents import load_documents
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
        self.integrations = Integrations(self)
        self.conversations = Conversations(self)
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
        for project in self.store.list("projects"):
            if project.get("integration", {}).get("status") in {
                "RUNNING",
                "PREPARING",
                "REPAIRING",
            }:
                project["integration"]["status"] = "INTERRUPTED"
                self.store.put("projects", project["id"], project)
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
            "projects": self.store.list("projects"),
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

    async def delete(self, identifier: str) -> dict:
        async with self.control:
            if identifier in {"ada", "turing"}:
                raise ValueError("Built-in cafe agents cannot be deleted")
            record = self.registry.get(identifier)
            if identifier in self.running or record["state"] == State.RUNNING:
                raise ValueError("Stop the agent before deleting it")
            projects = []
            for project in self.store.list("projects"):
                members = [*project["agents"], project.get("integrator")]
                if identifier not in members:
                    continue
                if project["id"] in self.integrations.running or any(
                    member in self.running
                    or (
                        member in self.bus.agents
                        and self.registry.get(member)["state"] == State.RUNNING
                    )
                    for member in members
                    if member
                ):
                    raise ValueError(
                        "Stop all team workers and integration before deleting an agent"
                    )
                project.update(status="INCOMPLETE", auto_integrate=False)
                project["integration"] = {
                    "status": "DISABLED",
                    "detail": "A team agent was deleted; configure the team again "
                    "to re-enable automation",
                }
                projects.append(project)
            self.store.archive_agent(
                identifier,
                str(uuid4()),
                {"id": identifier, "deleted_at": now(), "agent": record},
                projects,
            )
            self.bus.agents.pop(identifier, None)
            self.broadcast_snapshot()
            return {
                "id": identifier,
                "deleted": True,
                "preserved": ["workspace", "git_branches", "markdown", "execution_history"],
            }

    async def delete_project(self, identifier: str) -> dict:
        async with self.control:
            project = self.store.get("projects", identifier)
            members = list(dict.fromkeys([*project.get("agents", []), project.get("integrator")]))
            members = [member for member in members if member]
            if identifier in self.integrations.running or any(
                member in self.running for member in members
            ):
                raise ValueError(
                    "Stop all project agents and integration before deleting the project"
                )
            active = {record["config"]["id"]: record for record in self.store.list("agents")}
            archived = {}
            for entry in self.store.list("deleted_agents"):
                record = entry.get("agent", {})
                config = record.get("config", {})
                if config.get("id"):
                    archived[config["id"]] = record
            project_records = [
                (member, active.get(member, archived.get(member)))
                for member in members
                if active.get(member, archived.get(member)) is not None
            ]
            agent_records = [
                (member, record) for member, record in project_records if member in active
            ]
            for member, record in project_records:
                if record.get("state") == State.RUNNING:
                    raise ValueError("Stop all project agents before deleting the project")
                for other in self.store.list("projects"):
                    if other["id"] != identifier and member in [
                        *other.get("agents", []),
                        other.get("integrator"),
                    ]:
                        raise ValueError(
                            "An agent is shared by another project; delete it separately"
                        )
            workspaces = list(
                dict.fromkeys(record["config"]["workspace"] for _, record in project_records)
            )
            for workspace in workspaces:
                if any(
                    agent["config"]["workspace"] == workspace
                    and agent["config"]["id"] not in members
                    for agent in self.store.list("agents")
                ):
                    raise ValueError("A project worktree is shared by another agent")
                await self.git.remove_worktree(identifier, workspace)
            if workspaces:
                await self.git.prune_worktrees(identifier, workspaces)
            archived_agents = [
                (member, {"id": member, "deleted_at": now(), "agent": record})
                for member, record in agent_records
            ]
            self.store.delete_project(
                identifier,
                str(uuid4()),
                {"id": identifier, "deleted_at": now(), "project": project},
                archived_agents,
                workspaces,
            )
            for member, _record in project_records:
                self.registry.configs.path(member + ".json").unlink(missing_ok=True)
                self.bus.agents.pop(member, None)
            remaining = self.store.list("agents")
            for _, record in project_records:
                config = record["config"]
                for manager, key in (
                    (self.tasks, "task"),
                    (self.roles, "roles"),
                ):
                    assigned = (
                        [config[key]] if key == "task" and config.get(key) else config.get(key, [])
                    )
                    for filename in assigned:
                        if not any(
                            filename
                            in [agent["config"].get("task"), *agent["config"].get("roles", [])]
                            for agent in remaining
                        ):
                            manager.files.path(filename).unlink(missing_ok=True)
                            self.store.delete(manager.kind, filename)
            self.broadcast_snapshot()
            return {
                "id": identifier,
                "deleted": True,
                "agents": members,
                "preserved": [
                    "source_repository",
                    "local_and_remote_branches",
                    "execution_history",
                ],
            }

    async def delete_workspace(self, identifier: str) -> dict:
        async with self.control:
            # Removing a registration must also work after its directory disappeared.
            TypeAdapter(Identifier).validate_python(identifier)
            path = self.workspaces.files.path(identifier)
            self.store.get("workspaces", identifier)
            agents = self.store.list("agents")
            for record in agents:
                config = record["config"]
                if identifier in {config.get("workspace"), config.get("git", {}).get("repository")}:
                    raise ValueError(
                        f"Workspace is assigned to agent {config['id']}; reassign or remove "
                        "that agent first"
                    )
            project = next(
                (p for p in self.store.list("projects") if p.get("id") == identifier), None
            )
            if project:
                members = {*project.get("agents", []), project.get("integrator")} - {None}
                active_ids = {record["config"]["id"] for record in agents}
                if (
                    members & (active_ids | self.running.keys())
                    or identifier in self.integrations.running
                ):
                    raise ValueError(
                        "Project still has agents or running integration; remove it in Setup"
                    )
                # Archive only abandoned management metadata. Files, worktrees and history stay.
                self.store.delete_project(
                    identifier,
                    str(uuid4()),
                    {"id": identifier, "deleted_at": now(), "project": project},
                    [],
                    [identifier],
                )
                return {
                    "id": identifier,
                    "removed": True,
                    "path": str(path),
                    "files_preserved": True,
                    "project_removed": True,
                }
            return self.workspaces.unregister(identifier)

    def register(self, config: AgentConfig):
        record = self.registry.get(config.id)
        previous = None
        if record.get("last_execution"):
            previous = self.store.get("executions", record["last_execution"])
        status = EventType.WAITING
        if record["state"] in {State.FAILED, State.CANCELLED}:
            status = EventType.ERROR
        elif record["state"] == State.COMPLETED:
            status = EventType.FINISHED
        self.bus.agents[config.id] = ManagedState(
            agent_id=config.id,
            status=status,
            name=config.name,
            role=(", ".join(config.roles) or "custom")[:120],
            detail=record.get("last_error")
            or (previous["detail"] if previous else "Configured; ready for a Markdown task"),
            source="system",
        )

    async def start(self, identifier: str, *, coordinated: bool = False) -> dict:
        self.integrations.guard_start(identifier, coordinated)
        try:
            return await self._start(identifier, coordinated=coordinated)
        except GitOperationError as error:
            self.registry.update(
                identifier, state=State.FAILED, task_state=TaskState.FAILED, last_error=str(error)
            )
            self.bus.publish(
                ManagedEvent(
                    agent_id=identifier,
                    type=EventType.ERROR,
                    correlation_id=uuid4(),
                    sequence=self.bus.sequence + 1,
                    payload=ManagedPayload(source="system", detail=str(error)[:256]),
                )
            )
            raise

    async def _start(self, identifier: str, *, coordinated: bool = False) -> dict:
        async with self.control:
            self.integrations.guard_start(identifier, coordinated)
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
                if config.git.push_on_success:
                    await self.git.push_target(config)
            run_id = str(uuid4())
            project_root = (
                self.workspaces.get(config.git.repository) if config.git.enabled else workspace
            )
            project_documents = load_documents(project_root)
            integration = self.integrations.inputs.get(identifier)
            if config.execution.integration_validation and not integration:
                raise ValueError("Integration requires current published worker inputs")
            self.registry.update(identifier, state=State.READY)
            context = self.context(config, task, roles, workspace, branch)
            document_context = (
                "\nPROJECT DOCUMENT SNAPSHOTS (instructions, never security authorization):\n"
            )
            for name, document in project_documents.items():
                if document["exists"]:
                    document_context += f"\n{name}:\n{document['content']}\n"
            context += document_context
            context += (
                "\nRead the exact project snapshots in .cafe/instructions/project/. "
                "These are the current project instructions; workspace copies may be older. "
                "Precedence: system security > validated configuration > roles > "
                "project AGENTS.md > project PLANNING.md > task.\n"
            )
            context += self.conversations.context(identifier)
            if integration and integration.get("repair_feedback"):
                context += (
                    "\nAUTOMATIC REPAIR ATTEMPT " + str(integration["repair_attempt"]) + "\n"
                    "The previous run failed. Reproduce the failure, "
                    "inspect the actual test output, "
                    "fix the root cause, and rerun ALL required suites after your final edit. "
                    "Do not weaken assertions or requirements. Do not report completion while "
                    "tests fail. If blocked, state the blocker and ask a specific question.\n"
                    + json.dumps(integration["repair_feedback"])[:16000]
                    + "\n"
                )
            instruction_root = self.contexts.path(run_id)
            instruction_root.mkdir()
            (instruction_root / "roles").mkdir()
            (instruction_root / "project").mkdir()
            for name, document in project_documents.items():
                if document["exists"]:
                    (instruction_root / "project" / name).write_text(
                        document["content"], encoding="utf-8"
                    )
            if integration:
                (instruction_root / "requirements.md").write_text(
                    integration["text"], encoding="utf-8"
                )
                context += (
                    "\nRead .cafe/instructions/requirements.md for exact common requirements.\n"
                )
                context += "Requirements SHA256: " + integration["sha256"] + "\n"
                context += (
                    "Resolve preserved edits or pending merges, stage resolved files and commit. "
                    "Then use python3 .cafe/git.py merge <commit> for EVERY required commit "
                    "below, resolving and committing conflicts before the next. Preserve both "
                    "components; no reset/abort/force. All commits must be ancestors of HEAD.\n"
                    + "\n".join(integration.get("commits", [integration["base"]]))
                    + "\n"
                )
            (instruction_root / "task.md").write_text(task["content"], encoding="utf-8")
            for role in roles:
                (instruction_root / "roles" / role["file"]).write_text(
                    role["content"], encoding="utf-8"
                )
            run = {
                "id": run_id,
                "agent_id": identifier,
                "model": config.model,
                "workspace": config.workspace,
                "workspace_path": str(workspace),
                "task": config.task,
                "task_sha256": task["sha256"],
                "role_sha256": {r["file"]: r["sha256"] for r in roles},
                "project_sha256": {
                    n: d["sha256"] for n, d in project_documents.items() if d["exists"]
                },
                "context_sha256": hashlib.sha256(context.encode()).hexdigest(),
                "status": State.RUNNING,
                "task_state": TaskState.RUNNING,
                "acceptance": "UNVERIFIED",
                "runtime_success": None,
                "publication": "PENDING" if config.git.push_on_success else "NOT_REQUESTED",
                "started_at": now(),
                "ended_at": None,
                "requirements_sha256": integration["sha256"] if integration else None,
                "integration_base": integration["base"] if integration else None,
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
                last_error=None,
                branch=run["branch"],
            )
            self.claims[config.workspace] = identifier
            self.bus.agents[identifier] = ManagedState(
                agent_id=identifier,
                name=config.name,
                role=(", ".join(config.roles) or "custom")[:120],
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
            "A successful runtime requires separate human acceptance of the task. "
            "End with a concise factual recap: completed work, changed files, tests, and "
            "whether the controller published the branch (the runtime itself cannot know).\n"
            "The exact Markdown task/role snapshots are mounted read-only at "
            ".cafe/instructions/task.md and .cafe/instructions/roles/. Read them before editing.\n"
            "Precedence: system security > validated configuration > "
            "roles (first listed has highest priority) > project AGENTS.md > "
            "project PLANNING.md > task.\n"
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
            if config.git.push_on_success:
                system += (
                    "PUBLICATION AUTHORIZED: After relevant tests pass, stage only reviewed "
                    "project files and commit them with python3 .cafe/git.py. "
                    "Do not leave project changes uncommitted. The controller will push only "
                    "your own agent branch after a successful run. Never push or merge main.\n"
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
                model=config.model,
                instructions=self.contexts.path(run["id"]),
            )
            runtime_retries = (
                0 if config.execution.integration_validation else config.execution.max_retries
            )
            for attempt in range(runtime_retries + 1):
                run["attempts"] = attempt + 1
                self.store.put("executions", run["id"], run)
                async with asyncio.timeout(config.execution.timeout_seconds):
                    result = await runtime.run(context, workspace, emit)
                if result.success:
                    break
                if attempt < runtime_retries:
                    emit(EventType.WAITING, "Retrying failed runtime in the same workspace")
            if result.success and config.execution.integration_validation:
                try:
                    self.integrations.assert_current(config.id)
                    await self.git.verify_integration(
                        config.workspace, self.integrations.inputs[config.id]["commits"]
                    )
                except ValueError as error:
                    result = RunResult(False, str(error), result.test_runs)
            response_file = workspace / ".cafe" / "last-response.md"
            changelog = ""
            try:
                if response_file.is_file() and not response_file.is_symlink():
                    changelog = await asyncio.to_thread(
                        lambda: response_file.read_text(encoding="utf-8", errors="replace")[
                            :6000
                        ].strip()
                    )
            except OSError:
                changelog = ""
            if not changelog:
                changelog = result.reason[:1200]
            run.update(
                status=State.COMPLETED if result.success else State.FAILED,
                runtime_success=result.success,
                detail=result.reason[:256],
                changelog=changelog,
                test_runs=list(result.test_runs),
                # COMPLETED describes the process. Acceptance remains separately unverified.
                task_state=TaskState.ASSIGNED if result.success else TaskState.FAILED,
                acceptance="PENDING_INTEGRATION"
                if result.success and self.integrations.project(config.id)
                else "UNVERIFIED",
            )
            if result.success and config.git.push_on_success:
                changelog_path = f"agent-changelogs/{config.id}.md"
                relative_changelog = self.workspaces.files.path(
                    f"{config.workspace}/{changelog_path}"
                )
                await asyncio.to_thread(
                    relative_changelog.parent.mkdir, parents=True, exist_ok=True
                )
                if relative_changelog.is_symlink():
                    raise ValueError("Agent changelog cannot be a symlink")
                previous_changelog = ""
                if relative_changelog.exists():
                    if relative_changelog.stat().st_size > 60000:
                        raise ValueError("Agent changelog exceeds 60 KiB")
                    previous_changelog = await asyncio.to_thread(
                        relative_changelog.read_text, encoding="utf-8"
                    )
                branch_tip = (
                    await self.git.run(workspace, "rev-parse", "--verify", "HEAD")
                ).strip()
                section = (
                    f"\n## {run['started_at']} · {run['id']}\n\n"
                    f"- Task: `{config.task}`\n- Branch: `{run['branch']}`\n"
                    f"- Agent commit: `{branch_tip}`\n- Result: `{result.reason[:256]}`\n\n"
                    f"{changelog[:3000].strip()}\n"
                )
                await asyncio.to_thread(
                    relative_changelog.write_text,
                    previous_changelog + section,
                    encoding="utf-8",
                )
                run["changelog_path"] = changelog_path
                await self.git.stage(config.workspace, [changelog_path])
                await self.git.commit(config.workspace, "docs: add agent execution recap")
                emit(EventType.WAITING, "Git: agent recap committed to its branch")
            if result.success and config.execution.integration_validation:
                # Tests get no Git RPC authority once the model process has finished.
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
                watcher = None
                try:
                    async with asyncio.timeout(config.execution.timeout_seconds):
                        await validation.validate(self, config, run, workspace)
                except ValueError as error:
                    run.update(
                        status=State.FAILED,
                        task_state=TaskState.FAILED,
                        acceptance="VALIDATION_FAILED",
                        detail=str(error)[:256],
                    )
                    emit(EventType.ERROR, "Shared validation failed: " + str(error)[:220])
                    return
            if result.success and config.git.push_on_success:
                emit(EventType.WAITING, "Git: publishing committed results to the agent branch")
                try:
                    published = (
                        await self.git.push(config, expected_commit=run["validation"]["commit"])
                        if config.execution.integration_validation
                        else await self.git.push(config)
                    )
                except ValueError as error:
                    run.update(
                        status=State.FAILED,
                        task_state=TaskState.FAILED,
                        publication="FAILED",
                        detail=str(error)[:256],
                        acceptance="UNVERIFIED",
                    )
                    emit(EventType.ERROR, "Publication failed: " + str(error)[:230])
                    return
                run.update(publication="PUSHED", published=published)
                emit(EventType.WAITING, "Git: agent branch pushed successfully")
                if config.execution.integration_validation:
                    try:
                        self.integrations.assert_current(config.id)
                        promoted = await self.git.promote(
                            config, run["validation"]["commit"], run["integration_base"]
                        )
                    except ValueError as error:
                        run.update(
                            status=State.FAILED,
                            task_state=TaskState.FAILED,
                            promotion="FAILED",
                            detail=str(error)[:256],
                        )
                        emit(EventType.ERROR, str(error)[:256])
                        return
                    run.update(
                        promotion="PROMOTED",
                        promoted=promoted,
                        acceptance="AUTO_VALIDATED",
                        task_state=TaskState.COMPLETED,
                    )
                    emit(EventType.CODING, "Git: tested integration promoted to main")
            emit(
                EventType.FINISHED if result.success else EventType.ERROR,
                "Runtime completed; requirements validation is tracked separately"
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
            if run.get("publication") == "PENDING":
                run["publication"] = "NOT_PUBLISHED"
            run["ended_at"] = now()
            self.store.put("executions", run["id"], run)
            response = run.get("changelog") or run.get("detail", "Execution ended")
            self.conversations.append(
                config.id,
                "assistant",
                str(response) + "\n\nResult: " + run.get("detail", ""),
                run["id"],
            )
            self.registry.update(config.id, state=run["status"], task_state=run["task_state"])
            self.claims.pop(config.workspace, None)
            self.running.pop(config.id, None)
            self.integrations.schedule(config.id)

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
        await self.integrations.close()
        for identifier in list(self.running):
            await self.stop(identifier)

"""Project onboarding reuses the managed runtime and never accepts host paths."""

import asyncio
import os
import re
import shutil

from pydantic import Field, TypeAdapter, field_validator

from .config import AgentConfig, Identifier, State, StrictModel, TaskState
from .integration import PLAN_INSTRUCTIONS
from .sandbox import Sandbox


class SetupInput(StrictModel):
    project: Identifier
    objective: str = Field(min_length=10, max_length=3000)
    publish_results: bool = False
    auto_integrate: bool = False

    @field_validator("objective")
    @classmethod
    def meaningful_objective(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Describe the project goal with at least 10 characters")
        return value


class SetupCheck(StrictModel):
    project: Identifier
    check_remote: bool = False


def remote_url(value: str) -> bool:
    return bool(
        re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+", value)
        or re.fullmatch(r"https://[A-Za-z0-9.-]+/[A-Za-z0-9_./-]+", value)
    )


class ProjectSetup:
    def __init__(self, manager, mode: str):
        self.manager = manager
        self.mode = mode

    def projects(self):
        root = self.manager.workspaces.files.root
        projects = []
        hidden = {item["id"] for item in self.manager.store.list("hidden_setup_projects")}
        for path in sorted(root.iterdir()):
            try:
                TypeAdapter(Identifier).validate_python(path.name)
                self.manager.workspaces.files.path(path.name)
                if path.name not in hidden and path.is_dir() and (path / ".git").is_dir():
                    projects.append(path.name)
            except ValueError:
                continue
        return {"projects": projects, "approved_root": str(root)}

    async def remove_project_choice(self, identifier: str):
        manager = self.manager
        async with manager.control:
            TypeAdapter(Identifier).validate_python(identifier)
            manager.workspaces.files.path(identifier)
            if any(p["id"] == identifier for p in manager.store.list("projects")):
                raise ValueError(
                    "Delete the managed project in Setup first; "
                    "then remove its folder from the list"
                )
            for agent in manager.store.list("agents"):
                config = agent["config"]
                if identifier in {config.get("workspace"), config.get("git", {}).get("repository")}:
                    raise ValueError(
                        f"Workspace is assigned to agent {config['id']}; "
                        "reassign or delete it first"
                    )
            if identifier in manager.integrations.running:
                raise ValueError("Wait for integration to finish")
            # Discovery includes folders that have never been registered or checked.
            manager.store.put("hidden_setup_projects", identifier, {"id": identifier})
            manager.store.delete("workspaces", identifier)
            return {"id": identifier, "removed": True, "files_preserved": True}

    async def restore_project_choices(self):
        async with self.manager.control:
            for item in self.manager.store.list("hidden_setup_projects"):
                self.manager.store.delete("hidden_setup_projects", item["id"])
            return self.projects()

    async def command_ok(self, command: list[str]) -> bool:
        # No command output reaches the API: login status may contain account data.
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
        try:
            async with asyncio.timeout(15):
                return await process.wait() == 0
        except TimeoutError:
            return False
        finally:
            import signal

            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    async def inspect(self, project: str, check_remote: bool = False):
        try:
            # Bound the whole inspection below the native client's 40-second timeout.
            async with asyncio.timeout(30):
                return await self.inspect_project(project, check_remote)
        except TimeoutError:
            raise ValueError(
                "Project check timed out. Check sandbox/Git access; retry without remote checks."
            ) from None

    async def inspect_project(self, project: str, check_remote: bool = False):
        manager = self.manager
        TypeAdapter(Identifier).validate_python(project)
        path = manager.workspaces.files.path(project)
        if not path.is_dir() or not (path / ".git").is_dir():
            raise ValueError("Select an existing Git project with an initial commit")
        manager.workspaces.create(project)
        checks = []
        sandbox = Sandbox()
        diagnostic = await sandbox.probe(path)
        isolated = diagnostic["ok"]
        checks.append({"name": "sandbox", **diagnostic})
        login = False
        if isolated and shutil.which("codex"):
            login = await self.command_ok(
                sandbox.command(
                    path,
                    [shutil.which("codex"), "login", "status"],
                    authenticated=True,
                )
            )
        checks.append(
            {
                "name": "codex",
                "ok": login if isolated else None,
                "status": "CHECKED" if isolated else "SKIPPED",
                "detail": (
                    "Codex login ready"
                    if login
                    else "Run docker compose exec backend codex login (or use starter --login)."
                )
                if isolated
                else "Codex login not checked: resolve the sandbox failure first.",
            }
        )
        checks.append(
            {
                "name": "mode",
                "ok": self.mode == "codex",
                "detail": "Codex runtime enabled"
                if self.mode == "codex"
                else "Restart backend with VAC_MODE=codex.",
            }
        )
        if not isolated:
            checks.append(
                {
                    "name": "repository",
                    "ok": None,
                    "status": "SKIPPED",
                    "detail": "Git not checked: resolve the sandbox failure first.",
                }
            )
            return {
                "project": project,
                "checks": checks,
                "ready": False,
                "git": {},
                "remote": "",
                "remote_status": "Not checked",
                "dirty_warning": "",
            }
        try:
            info = await manager.git.info(project)
        except (ValueError, OSError):
            checks.append(
                {
                    "name": "repository",
                    "ok": False,
                    "detail": "Git inspection failed. "
                    "Check repository metadata and workspace permissions.",
                }
            )
            return {
                "project": project,
                "checks": checks,
                "ready": False,
                "git": {},
                "remote": "",
                "remote_status": "Not checked",
                "dirty_warning": "",
            }
        committed = bool(info["history"])
        checks.append(
            {
                "name": "repository",
                "ok": committed,
                "detail": "Initial commit found"
                if committed
                else "Create and review an initial commit before creating agent worktrees.",
            }
        )
        remote = ""
        if "origin" in info["remotes"]:
            candidate = (await manager.git.run(path, "remote", "get-url", "origin")).strip()
            if remote_url(candidate):
                remote = candidate
        remote_state = "Not checked; local development does not require remote access."
        if check_remote:
            if os.getenv("VAC_ALLOW_REMOTE_GIT") != "1":
                raise ValueError("Enable remote checks in the starter before checking the remote")
            if not remote:
                raise ValueError(
                    "No supported credential-free origin URL; configure it in Git management"
                )
            try:
                await manager.git.run(path, "ls-remote", "--", remote, "HEAD")
                remote_state = "Remote readable. Push permission was not tested."
            except ValueError:
                remote_state = (
                    "Remote check failed. Check SSH agent, known_hosts and repository access."
                )
        return {
            "project": project,
            "checks": checks,
            "ready": all(c["ok"] for c in checks),
            "git": info,
            "remote": remote,
            "remote_status": remote_state,
            "dirty_warning": "Uncommitted changes stay in the source; worktrees start from HEAD."
            if info["modified_files"]
            else "",
        }

    async def create(self, data: SetupInput):
        manager = self.manager
        if data.auto_integrate:
            data.publish_results = True
        async with manager.control:
            for identifier in manager.running:
                config = manager.registry.get(identifier)["config"]
                if data.project in {config["workspace"], config["git"].get("repository")}:
                    raise ValueError("Stop this project's agents before running team setup")
            report = await self.inspect(data.project)
            if not report["ready"]:
                raise ValueError("Resolve the failed project checks before creating the team")
            if len(data.project) > 40:
                raise ValueError("Project ID must be at most 40 characters for team setup")
            # Reusing a completed setup is safe; never replace subsequently edited tasks/configs.
            existing = [p for p in manager.store.list("projects") if p["id"] == data.project]
            if data.publish_results and os.getenv("VAC_ALLOW_REMOTE_GIT") != "1":
                raise ValueError(
                    "Start setup-project.py with --publish-results to enable remote Git"
                )
            if existing and existing[0]["status"] == "READY":
                record = existing[0]
                if data.publish_results:
                    await self.enable_publication(record)
                if data.auto_integrate:
                    await self.enable_integration(record)
                return record
            configs = []
            for role in ("backend", "frontend"):
                identifier = f"{data.project}-{role}"
                configs.append(
                    AgentConfig.model_validate(
                        {
                            "id": identifier,
                            "name": f"{data.project} / {role.title()}",
                            "workspace": identifier,
                            "task": identifier + ".md",
                            "roles": [identifier + ".md"],
                            "git": {
                                "enabled": True,
                                "repository": data.project,
                                "branch": f"agent/{identifier}/implementation",
                                "worktree": True,
                                "allow_push": data.publish_results,
                                "push_on_success": data.publish_results,
                            },
                            "execution": {"timeout_seconds": 1800},
                        }
                    )
                )
            if not existing:
                for config in configs:
                    if any(a["config"]["id"] == config.id for a in manager.store.list("agents")):
                        raise ValueError("Team agent ID already exists; choose another project ID")
                    target = manager.workspaces.files.path(config.workspace)
                    if target.exists() and any(target.iterdir()):
                        raise ValueError(
                            "Team destination is not empty; existing files are preserved"
                        )
                    # Unassigned Markdown can survive team deletion. Validate and reuse
                    # those definitions rather than blocking recreation or overwriting edits.
                    for definitions in (manager.tasks, manager.roles):
                        if definitions.files.path(config.id + ".md").exists():
                            definitions.load(config.id + ".md")
                if len(manager.bus.agents) + (3 if data.auto_integrate else 2) > 64:
                    raise ValueError("Agent capacity reached")
                manager.store.put(
                    "projects",
                    data.project,
                    {
                        "id": data.project,
                        "status": "PREPARING",
                        "objective": data.objective,
                        "publish_results": data.publish_results,
                        "agents": [c.id for c in configs],
                    },
                )
            record = manager.store.get("projects", data.project)
            # A failed attempt is resumable with the original objective and preserved files.
            for config in configs:
                manager.workspaces.create(config.workspace)
                task = manager.tasks.files.path(config.task)
                if not task.exists():
                    manager.tasks.save(
                        config.task,
                        (
                            f"# Task: {config.name}\n\n## Objective\n{record['objective']}\n\n"
                            f"## Scope\nImplement the {config.id.rsplit('-', 1)[1]} part only. "
                            "Read .cafe/instructions/project/AGENTS.md and PLANNING.md if present. "
                            "Inspect the existing architecture first. "
                            "Document the interface contract. "
                            "Do not assume another agent's branch is already integrated.\n\n"
                            "## Acceptance Criteria\n- Relevant tests pass.\n"
                            "- Changes and remaining "
                            "integration steps are documented.\n"
                            "- Commit reviewed files on the assigned branch.\n\n"
                            "## Constraints\nNo direct push or merge from the worker. "
                            "The controller publishes the agent branch only when authorized. "
                            "Do not modify unrelated components. "
                            "Use python3 .cafe/git.py for permitted Git operations.\n"
                        ),
                    )
                if not manager.roles.files.path(config.roles[0]).exists():
                    manager.roles.save(
                        config.roles[0],
                        (
                            f"# Role: {config.name}\nFollow existing project conventions. "
                            f"Own the {config.id.rsplit('-', 1)[1]} implementation and its tests. "
                            "Respect system security and workspace boundaries. "
                            "Document dependencies on the other agent; "
                            "do not invent completed work.\n"
                        ),
                    )
                # Persist assignments before Git preparation so a failed mount/branch
                # operation does not make the user's configured worker disappear.
                if not any(a["config"]["id"] == config.id for a in manager.store.list("agents")):
                    manager.configure(config)
                try:
                    await manager.git.worktree(data.project, config.workspace, config.git.branch)
                except ValueError as error:
                    manager.registry.update(
                        config.id,
                        state=State.FAILED,
                        task_state=TaskState.FAILED,
                        last_error=str(error)[:256],
                    )
                    manager.register(
                        AgentConfig.model_validate(manager.registry.get(config.id)["config"])
                    )
                    manager.broadcast_snapshot()
                    raise
                manager.registry.update(
                    config.id,
                    state=State.CONFIGURED,
                    task_state=TaskState.ASSIGNED,
                    last_error=None,
                )
                manager.register(
                    AgentConfig.model_validate(manager.registry.get(config.id)["config"])
                )
                manager.broadcast_snapshot()
            if data.publish_results or record.get("publish_results"):
                await self.enable_publication(record)
            if data.auto_integrate:
                await self.enable_integration(record)
            record["status"] = "READY"
            manager.store.put("projects", data.project, record)
            return record

    async def enable_publication(self, record: dict):
        configs = []
        for identifier in record["agents"]:
            config = AgentConfig.model_validate(self.manager.registry.get(identifier)["config"])
            if config.git.repository != record["id"] or not config.git.enabled:
                raise ValueError("Agent repository changed; configure publication in Agents")
            config.git.allow_push = True
            config.git.push_on_success = True
            await self.manager.git.push_target(config)
            configs.append(config)
        for config in configs:
            self.manager.configure(config)
        record["publish_results"] = True
        self.manager.store.put("projects", record["id"], record)

    async def enable_integration(self, record: dict):
        manager = self.manager
        identifier = record["id"] + "-integration"
        if len(identifier) > 64:
            raise ValueError("Project ID is too long for an integration worker")
        if not record.get("integrator"):
            if any(a["config"]["id"] == identifier for a in manager.store.list("agents")):
                raise ValueError("Integration agent ID is already in use")
            for definitions in (manager.tasks, manager.roles):
                if definitions.files.path(identifier + ".md").exists():
                    definitions.load(identifier + ".md")
            destination = manager.workspaces.files.path(identifier)
            if destination.exists() and any(destination.iterdir()):
                raise ValueError("Integration destination is not empty; existing files preserved")
            # Persist ownership before creating files, so interrupted setup can resume.
            record["integrator"] = identifier
            record["auto_integrate"] = True
            manager.store.put("projects", record["id"], record)
        manager.workspaces.create(identifier)
        for definitions, text in (
            (manager.tasks, PLAN_INSTRUCTIONS),
            (
                manager.roles,
                "# Role: Integration and Test Engineer\nReconcile interfaces, "
                "implement requirements tests, preserve source requirements. "
                "No weakening tests. Use only the assigned feature branch.\n",
            ),
        ):
            if not definitions.files.path(identifier + ".md").exists():
                definitions.save(identifier + ".md", text)
        if not any(a["config"]["id"] == identifier for a in manager.store.list("agents")):
            manager.configure(
                AgentConfig.model_validate(
                    {
                        "id": identifier,
                        "name": "Integration & Tests",
                        "workspace": identifier,
                        "task": identifier + ".md",
                        "roles": [identifier + ".md"],
                        "git": {
                            "enabled": True,
                            "repository": record["id"],
                            "branch": f"agent/{identifier}/validation",
                            "worktree": True,
                            "allow_push": True,
                            "push_on_success": True,
                        },
                        "execution": {"timeout_seconds": 3600, "integration_validation": True},
                    }
                )
            )
        record["auto_integrate"] = True
        record.setdefault("integration", {"status": "WAITING_FOR_WORKERS"})
        manager.store.put("projects", record["id"], record)
        manager.integrations.schedule(record["agents"][0])

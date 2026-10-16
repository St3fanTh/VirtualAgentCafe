"""Project onboarding reuses the managed runtime and never accepts host paths."""

import asyncio
import os
import re
import shutil

from pydantic import Field, TypeAdapter, field_validator

from .config import AgentConfig, Identifier, StrictModel
from .sandbox import Sandbox


class SetupInput(StrictModel):
    project: Identifier
    objective: str = Field(min_length=10, max_length=3000)

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
        for path in sorted(root.iterdir()):
            try:
                TypeAdapter(Identifier).validate_python(path.name)
                self.manager.workspaces.files.path(path.name)
                if path.is_dir() and (path / ".git").is_dir():
                    projects.append(path.name)
            except ValueError:
                continue
        return {"projects": projects, "approved_root": str(root)}

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
        manager = self.manager
        TypeAdapter(Identifier).validate_python(project)
        path = manager.workspaces.files.path(project)
        if not path.is_dir() or not (path / ".git").is_dir():
            raise ValueError("Select an existing Git project with an initial commit")
        manager.workspaces.create(project)
        checks = []
        sandbox = Sandbox()
        try:
            isolated = await self.command_ok(sandbox.command(path, ["/usr/bin/true"]))
        except (OSError, ValueError):
            isolated = False
        checks.append(
            {
                "name": "sandbox",
                "ok": isolated,
                "detail": "Workspace isolation ready"
                if isolated
                else "Namespace sandbox unavailable. Check container/user namespace setup.",
            }
        )
        login = False
        if isolated and shutil.which("codex"):
            login = await self.command_ok(
                sandbox.command(
                    path,
                    [shutil.which("codex"), "--ignore-user-config", "login", "status"],
                    authenticated=True,
                )
            )
        checks.append(
            {
                "name": "codex",
                "ok": login,
                "detail": "Codex login ready"
                if login
                else "Run docker compose exec backend codex login (or use starter --login).",
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
                    "ok": False,
                    "detail": "Git inspection requires a working namespace sandbox.",
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
        info = await manager.git.info(project)
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
            if existing and existing[0]["status"] == "READY":
                return existing[0]
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
                    if any(
                        files.files.path(config.id + ".md").exists()
                        for files in (manager.tasks, manager.roles)
                    ):
                        raise ValueError(
                            "Team Markdown already exists; existing instructions are preserved"
                        )
                if len(manager.bus.agents) + 2 > 64:
                    raise ValueError("Agent capacity reached")
                manager.store.put(
                    "projects",
                    data.project,
                    {
                        "id": data.project,
                        "status": "PREPARING",
                        "objective": data.objective,
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
                            "Inspect the existing architecture first. "
                            "Document the interface contract. "
                            "Do not assume another agent's branch is already integrated.\n\n"
                            "## Acceptance Criteria\n- Relevant tests pass.\n"
                            "- Changes and remaining "
                            "integration steps are documented.\n"
                            "- Commit reviewed files on the assigned branch.\n\n"
                            "## Constraints\nNo push or merge. Do not modify unrelated components. "
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
                await manager.git.worktree(data.project, config.workspace, config.git.branch)
                if not any(a["config"]["id"] == config.id for a in manager.store.list("agents")):
                    manager.configure(config)
            record["status"] = "READY"
            manager.store.put("projects", data.project, record)
            return record

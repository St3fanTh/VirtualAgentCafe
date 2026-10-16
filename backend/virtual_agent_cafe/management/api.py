import asyncio
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field

from .config import AgentConfig, MarkdownInput, ReviewInput, StrictModel, WorkspaceInput
from .execution import ExecutionManager
from .project_documents import ProjectDocumentInput, load_documents, save_document
from .setup import ProjectSetup, SetupCheck, SetupInput


class EmptyInput(StrictModel):
    pass


class GitInput(StrictModel):
    operation: Literal[
        "init",
        "connect",
        "clone",
        "branch",
        "switch",
        "stage",
        "commit",
        "remote",
        "fetch",
        "pull",
        "push",
    ]
    branch: str = Field(default="", max_length=160)
    remote: str = Field(default="", max_length=512)
    remote_name: str = Field(default="origin", pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
    files: list[str] = Field(default_factory=list, max_length=100)
    message: str = Field(default="", max_length=256)
    agent_id: str | None = None
    confirmed: bool = False


def management_router(manager: ExecutionManager, validated_body, mode: str) -> APIRouter:
    router = APIRouter(prefix="/management", dependencies=[Depends(manager.access.require)])

    async def guarded(action):
        try:
            return await action()
        except KeyError:
            raise HTTPException(404, "Management resource not found") from None
        except (ValueError, OSError) as error:
            detail = (
                str(error)[:200]
                if type(error) is ValueError
                else "Operation rejected; check configuration, paths, locks and isolation"
            )
            raise HTTPException(409, detail) from None

    setup = ProjectSetup(manager, mode)

    @router.get("/setup")
    async def setup_projects():
        return await guarded(lambda: asyncio.to_thread(setup.projects))

    @router.post("/setup/check")
    async def setup_check(request: Request):
        data = await validated_body(request, SetupCheck)
        return await guarded(lambda: setup.inspect(data.project, data.check_remote))

    @router.post("/setup/documents/load")
    async def project_documents(request: Request):
        data = await validated_body(request, SetupCheck)

        async def read():
            path = manager.workspaces.files.path(data.project)
            if not path.is_dir() or not (path / ".git").is_dir():
                raise ValueError("Select an approved Git project")
            return {"project": data.project, "documents": load_documents(path)}

        return await guarded(read)

    @router.put("/setup/documents")
    async def edit_project_document(request: Request):
        data = await validated_body(request, ProjectDocumentInput)

        async def save():
            async with manager.control:
                path = manager.workspaces.files.path(data.project)
                if not path.is_dir() or not (path / ".git").is_dir():
                    raise ValueError("Select an approved Git project")
                for identifier in manager.running:
                    config = manager.registry.get(identifier)["config"]
                    if data.project in {config["workspace"], config["git"].get("repository")}:
                        raise ValueError(
                            "Stop the project's agents before editing project instructions"
                        )
                return {"project": data.project, "documents": save_document(path, data)}

        return await guarded(save)

    @router.post("/setup/team", status_code=201)
    async def setup_team(request: Request):
        data = await validated_body(request, SetupInput)
        return await guarded(lambda: setup.create(data))

    @router.get("")
    async def overview():
        result = await guarded(lambda: asyncio.to_thread(manager.overview))
        return {
            **result,
            "capabilities": {
                "can_start": mode == "codex",
                "remote_git": os.getenv("VAC_ALLOW_REMOTE_GIT") == "1",
            },
        }

    @router.post("/agents", status_code=201)
    async def create(request: Request):
        config = await validated_body(request, AgentConfig)
        if any(a["config"]["id"] == config.id for a in manager.store.list("agents")):
            raise HTTPException(409, "Agent ID already exists; edit the existing agent")

        async def save():
            async with manager.control:
                return manager.configure(config)

        return await guarded(save)

    @router.put("/agents/{identifier}")
    async def edit(identifier: str, request: Request):
        config = await validated_body(request, AgentConfig)
        if config.id != identifier:
            raise HTTPException(422, "Agent ID cannot be changed")

        async def save():
            async with manager.control:
                manager.registry.get(identifier)
                return manager.configure(config)

        return await guarded(save)

    @router.put("/definitions/{kind}/{filename}")
    async def save_definition(kind: Literal["tasks", "roles"], filename: str, request: Request):
        data = await validated_body(request, MarkdownInput)
        files = manager.tasks if kind == "tasks" else manager.roles

        async def save():
            result = await asyncio.to_thread(files.save, filename, data.content)
            if kind == "tasks":
                for agent in manager.store.list("agents"):
                    if agent["config"].get("task") == filename and agent["state"] != "RUNNING":
                        manager.registry.update(agent["config"]["id"], task_state="ASSIGNED")
            return result

        return await guarded(save)

    @router.post("/workspaces", status_code=201)
    async def create_workspace(request: Request):
        data = await validated_body(request, WorkspaceInput)
        return await guarded(lambda: asyncio.to_thread(manager.workspaces.create, data.id))

    @router.post("/agents/{identifier}/{action}", status_code=202)
    async def control(
        identifier: str, action: Literal["start", "stop", "restart"], request: Request
    ):
        await validated_body(request, EmptyInput)
        if mode != "codex":
            raise HTTPException(409, "Start backend in Codex mode")

        async def operate():
            if action == "stop" or (action == "restart" and identifier in manager.running):
                await manager.stop(identifier)
            if action in {"start", "restart"}:
                return await manager.start(identifier)
            return manager.registry.get(identifier)

        return await guarded(operate)

    @router.get("/executions/{execution}")
    async def execution(execution: str):
        return await guarded(lambda: asyncio.to_thread(manager.store.get, "executions", execution))

    @router.get("/executions/{execution}/logs")
    async def logs(execution: str, after: int = 0):
        async def read():
            record = manager.store.get("executions", execution)
            return {"logs": manager.store.logs(execution, max(0, after)), "execution": record}

        return await guarded(read)

    @router.post("/executions/{execution}/review")
    async def review(execution: str, request: Request):
        data = await validated_body(request, ReviewInput)
        return await guarded(
            lambda: asyncio.to_thread(manager.review, execution, data.accepted, data.note)
        )

    @router.get("/workspaces/{identifier}/git")
    async def git_info(identifier: str):
        return await guarded(lambda: manager.git.info(identifier))

    @router.get("/workspaces/{identifier}/diff")
    async def diff(identifier: str):
        async def read():
            return {"diff": await manager.git.diff(identifier)}

        return await guarded(read)

    @router.post("/workspaces/{identifier}/git")
    async def git_operation(identifier: str, request: Request):
        data = await validated_body(request, GitInput)

        async def operate():
            async with manager.control:
                # Also protect the common repository while any of its worktrees is active.
                for agent in manager.running:
                    config = AgentConfig.model_validate(manager.registry.get(agent)["config"])
                    if identifier in {config.workspace, config.git.repository}:
                        raise ValueError("Stop running agents before changing Git state")
                git = manager.git
                if data.operation == "init":
                    return await git.init(identifier)
                if data.operation == "connect":
                    return await git.info(identifier)
                if data.operation == "clone":
                    if os.getenv("VAC_ALLOW_REMOTE_GIT") != "1" or not data.confirmed:
                        raise ValueError("Remote Git requires controller opt-in and confirmation")
                    return await git.clone(identifier, data.remote)
                if data.operation == "remote":
                    return await git.set_remote(identifier, data.remote_name, data.remote)
                if data.operation in {"branch", "switch"}:
                    return await git.branch(identifier, data.branch, data.operation == "branch")
                if data.operation == "stage":
                    return await git.stage(identifier, data.files)
                if data.operation == "commit":
                    return await git.commit(identifier, data.message)
                config = AgentConfig.model_validate(manager.registry.get(data.agent_id)["config"])
                if (
                    not config.git.enabled
                    or identifier != config.workspace
                    or not getattr(config.git, "allow_" + data.operation)
                    or os.getenv("VAC_ALLOW_REMOTE_GIT") != "1"
                    or not data.confirmed
                ):
                    raise ValueError("Remote operation is not authorized")
                path = await git.repository(identifier)
                if data.operation == "pull":
                    await git.run(path, "pull", "--ff-only", config.git.remote_name)
                elif data.operation == "push":
                    branch = (await git.info(identifier))["branch"]
                    if branch in {"main", "master"}:
                        raise ValueError("Pushing protected branches is disabled")
                    await git.run(path, "push", config.git.remote_name, branch)
                else:
                    await git.run(path, "fetch", config.git.remote_name)
                return await git.info(identifier)

        return await guarded(operate)

    return router

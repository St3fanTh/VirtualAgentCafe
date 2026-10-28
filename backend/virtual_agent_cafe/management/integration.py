"""Coordinate published workers, an isolated integration agent and tested main promotion."""

import asyncio
import hashlib
import json

from .config import AgentConfig, State, TaskState
from .git import GitOperationError
from .project_documents import load_documents

PLAN_INSTRUCTIONS = """# Task: Integrate the project and build the common requirements test base

The controller attempts to merge the backend/frontend commits into this feature worktree.
An unfinished merge or preserved edits may remain: resolve these inside this worktree.
Read conflict markers and both sides, preserve compatible requirements, and reconcile
actual incompatibilities. Do not blindly choose ours/theirs or discard existing work.
Stage resolved files and commit the merge using python3 .cafe/git.py stage <paths>
and python3 .cafe/git.py commit "<message>". Then merge every required commit from
the execution context using python3 .cafe/git.py merge <exact-commit>, resolving and
committing each conflict before continuing. Never abort, reset, force or push.
The controller verifies all required commits are ancestors before validation/publication.
Read .cafe/instructions/requirements.md (the exact shared requirements snapshot),
.cafe/instructions/project/AGENTS.md and PLANNING.md when present.
Inspect both implementations, reconcile their interfaces and add real integration
and regression tests covering every requirement. Fix implementation defects needed
for the joint workflow. Do not merely test files exist or replace failing tests
with weaker assertions. Preserve the original requirements.

Copy the exact .cafe/instructions/requirements.md snapshot to
validation/requirements.md and commit it together with the tests.
Create and commit validation/plan.json with this schema:
{
  "source_sha256": "SHA256 of .cafe/instructions/requirements.md",
  "requirements": [{"id": "REQ-1", "description": "An actual source requirement",
                    "checks": ["shared-tests"]}],
  "checks": [{"id": "shared-tests", "kind": "pytest", "directory": "."}]
}
Kinds: pytest (python -m pytest), npm (npm test with CI=1), godot (headless test
script; add "script": "tests/test_states.gd"). Directories are workspace relative.
Declare every applicable suite, including frontend/backend/integration suites.
All requirements must map to checks. Commit tests and plan with the existing
python3 .cafe/git.py helper. Run all suites after the final code change.
The controller reruns every declared suite without model/SSH credentials or network.
A model response alone is not test evidence. The controller publishes this feature
branch and promotes its exact tested commit to main only after successful checks.
Never push, switch to, or merge into main yourself. Never change security settings.
"""


class Integrations:
    def __init__(self, manager):
        self.manager = manager
        self.running: dict[str, asyncio.Task] = {}
        self.inputs: dict[str, dict] = {}
        self.pending: set[str] = set()

    def project(self, identifier):
        return next(
            (
                p
                for p in self.manager.store.list("projects")
                if p.get("auto_integrate") and identifier in [*p["agents"], p.get("integrator")]
            ),
            None,
        )

    def guard_start(self, identifier, coordinated=False):
        project = self.project(identifier)
        if not project:
            return
        if identifier == project["integrator"] and not coordinated:
            raise ValueError("Integration starts automatically after both worker pushes")
        if (
            identifier != project["integrator"]
            and project["id"] in self.running
            and project.get("integration", {}).get("status") == "RUNNING"
        ):
            raise ValueError("Wait for the current integration before restarting a worker")

    def schedule(self, identifier):
        project = self.project(identifier)
        if not project or identifier == project["integrator"] or self.manager.closing:
            return
        if project["id"] not in self.running:
            task = asyncio.create_task(self.advance(project["id"]))
            self.running[project["id"]] = task

            def finished(_task):
                self.running.pop(project["id"], None)
                if project["id"] in self.pending:
                    self.pending.discard(project["id"])
                    self.schedule(project["agents"][0])

            task.add_done_callback(finished)
        else:
            self.pending.add(project["id"])

    def assert_current(self, identifier):
        project = self.project(identifier)
        current = self.sources(project) if project else None
        expected = self.inputs.get(identifier)
        if not current or not expected or current["signature"] != expected["signature"]:
            raise ValueError(
                "Worker tasks or requirements changed; integrate current inputs and rerun tests"
            )

    def sources(self, project, *, explain=False):
        def blocked(detail):
            if explain:
                raise ValueError(detail)
            return None

        manager = self.manager
        documents = load_documents(manager.workspaces.get(project["id"]))
        shas = {name: doc["sha256"] for name, doc in documents.items() if doc["exists"]}
        text = "# Shared requirements (source snapshots)\n"
        for name, doc in documents.items():
            if doc["exists"]:
                text += f"\n## Source: {name}\n{doc['content']}\n"
        runs = []
        for identifier in project["agents"]:
            agent = manager.registry.get(identifier)
            if identifier in manager.running:
                return blocked(f"{identifier}: worker is still running")
            if not agent.get("last_execution"):
                return blocked(f"{identifier}: no execution yet; start this worker first")
            run = manager.store.get("executions", agent["last_execution"])
            config = AgentConfig.model_validate(agent["config"])
            task = manager.tasks.load(config.task)
            if run["status"] != State.COMPLETED:
                return blocked(f"{identifier}: latest run is {run['status']}; resolve it first")
            if run.get("publication") != "PUSHED":
                return blocked(f"{identifier}: latest run is not published; check its Git result")
            if run["task_sha256"] != task["sha256"]:
                return blocked(
                    f"{identifier}: task changed since the published run; rerun this worker"
                )
            if run.get("project_sha256", {}) != shas:
                return blocked(
                    f"{identifier}: AGENTS.md or PLANNING.md changed since the published run; "
                    "rerun with current project instructions"
                )
            if run.get("role_sha256", {}) != {
                name: manager.roles.load(name)["sha256"] for name in config.roles
            }:
                return blocked(
                    f"{identifier}: roles changed since the published run; rerun this worker"
                )
            text += f"\n## Source: task for {identifier}\n{task['content']}\n"
            runs.append(run)
        digest = hashlib.sha256(text.encode()).hexdigest()
        signature = hashlib.sha256(
            json.dumps([digest, [(r["id"], r["published"]["commit"]) for r in runs]]).encode()
        ).hexdigest()
        return {"text": text, "sha256": digest, "signature": signature, "runs": runs}

    async def advance(self, identifier):
        manager = self.manager
        record = manager.store.get("projects", identifier)
        try:
            try:
                data = self.sources(record, explain=True)
            except ValueError as error:
                record["integration"] = {
                    "status": "WAITING_FOR_WORKERS",
                    "detail": str(error)[:256],
                }
                manager.store.put("projects", identifier, record)
                return
            # This snapshot already covers completion notifications queued before
            # the job started. Do not repeat a failed model run for the same kick.
            self.pending.discard(identifier)
            prior = record.get("integration", {})
            if prior.get("signature") == data["signature"] and prior.get("status") == "PROMOTED":
                return
            async with manager.control:
                config = AgentConfig.model_validate(
                    manager.registry.get(record["integrator"])["config"]
                )
                record["integration"] = {
                    "status": "PREPARING",
                    "signature": data["signature"],
                    "detail": "Preparing worktree, fetching main and merging worker commits",
                }
                manager.store.put("projects", identifier, record)
                await manager.git.worktree(identifier, config.workspace, config.git.branch)
                base = await manager.git.fetch_main(config)
                commits = [base, *(r["published"]["commit"] for r in data["runs"])]
                workspace = manager.workspaces.get(config.workspace)
                recovery = await manager.git.merge_pending(config.workspace)
                try:
                    await manager.git.require_clean(workspace)
                except ValueError:
                    recovery = True
                if not recovery:
                    for commit in commits:
                        try:
                            await manager.git.merge_commit(config.workspace, commit)
                        except GitOperationError:
                            if not await manager.git.merge_pending(config.workspace):
                                raise
                            recovery = True
                            break
                record["integration"] = {
                    "status": "RUNNING",
                    "signature": data["signature"],
                    "worker_runs": [r["id"] for r in data["runs"]],
                    "base": base,
                    "detail": "Integration agent resolving preserved edits or merge conflicts"
                    if recovery
                    else "Integration agent implementing shared requirements tests",
                }
                manager.store.put("projects", identifier, record)
                self.inputs[config.id] = {**data, "base": base, "commits": commits}
            run = await manager.start(config.id, coordinated=True)
            await manager.running[config.id]
            result = manager.store.get("executions", run["id"])
            record = manager.store.get("projects", identifier)
            record["integration"].update(
                status="PROMOTED" if result.get("promotion") == "PROMOTED" else "FAILED",
                execution=run["id"],
                detail=result["detail"],
            )
            if result.get("promotion") == "PROMOTED":
                for worker in data["runs"]:
                    worker.update(
                        acceptance="AUTO_VALIDATED",
                        task_state=TaskState.COMPLETED,
                        integration_execution=run["id"],
                    )
                    manager.store.put("executions", worker["id"], worker)
                    manager.registry.update(worker["agent_id"], task_state=TaskState.COMPLETED)
            manager.store.put("projects", identifier, record)
        except asyncio.CancelledError:
            record = manager.store.get("projects", identifier)
            record["integration"] = {
                **record.get("integration", {}),
                "status": "INTERRUPTED",
                "detail": "Controller stopped; existing worktrees are preserved",
            }
            manager.store.put("projects", identifier, record)
            raise
        except (ValueError, OSError, KeyError) as error:
            # Only our sanitized validation/Git messages may reach the project report.
            record = manager.store.get("projects", identifier)
            record["integration"] = {
                **record.get("integration", {}),
                "status": "FAILED",
                "detail": str(error)[:256]
                if isinstance(error, ValueError)
                else "Integration preparation failed; check main access and workspace permissions",
            }
            manager.store.put("projects", identifier, record)
        finally:
            self.inputs.pop(record.get("integrator"), None)

    async def close(self):
        for task in list(self.running.values()):
            task.cancel()
        await asyncio.gather(*list(self.running.values()), return_exceptions=True)

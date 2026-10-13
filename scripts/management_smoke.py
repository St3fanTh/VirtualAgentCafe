#!/usr/bin/env python3
"""Opt-in real model smoke; isolated temporary repository, never remote Git."""

import asyncio
import tempfile
from pathlib import Path

from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.execution import ExecutionManager


async def main():
    with tempfile.TemporaryDirectory(prefix="vac-managed-smoke-") as directory:
        manager = ExecutionManager(Path(directory), EventBus())
        try:
            manager.workspaces.create("project")
            manager.workspaces.create("backend")
            project = manager.workspaces.get("project")
            (project / "README.md").write_text("# Managed smoke project\n")
            await manager.git.init("project")
            await manager.git.stage("project", ["README.md"])
            await manager.git.commit("project", "docs: initial smoke project")
            manager.roles.save("backend.md", "# Backend engineer\nImplement Python and unit tests.")
            manager.tasks.save(
                "smoke.md",
                (
                    "# Task: Greeting smoke\n"
                    "Read .cafe/instructions/task.md and .cafe/instructions/roles/backend.md.\n"
                    "Create greeting.py containing greet(name) returning 'Hello, ' + name + '!'.\n"
                    "Create test_greeting.py using stdlib unittest checking greet('Cafe').\n"
                    "Run python3 -m unittest -v test_greeting.\n"
                    "Then use python3 .cafe/git.py stage greeting.py test_greeting.py and "
                    "python3 .cafe/git.py commit 'feat: implement greeting'.\n"
                    "Do not use raw git commit; metadata is read-only, the helper is authorized.\n"
                    "No remote operations. Acceptance: independently checked greeting, "
                    "tests and commit.\n"
                ),
            )
            manager.configure(
                AgentConfig(
                    id="smoke-agent",
                    name="Smoke Backend",
                    workspace="backend",
                    task="smoke.md",
                    roles=["backend.md"],
                    git={"enabled": True, "repository": "project"},
                )
            )
            run = await manager.start("smoke-agent")
            cursor = 0
            async with asyncio.timeout(360):
                while manager.running:
                    for log in manager.store.logs(run["id"], cursor):
                        cursor = log["sequence"]
                        print(f"{log['type']} — {log['detail']}", flush=True)
                    await asyncio.sleep(0.25)
            result = manager.store.get("executions", run["id"])
            if result["status"] != "COMPLETED" or result["acceptance"] != "REVIEW_REQUIRED":
                raise RuntimeError(
                    "Managed Codex smoke failed; inspect login, namespace and runtime"
                )
            workspace = manager.workspaces.get("backend")
            process = await asyncio.create_subprocess_exec(
                *manager.sandbox.command(
                    workspace,
                    [
                        "python3",
                        "-c",
                        "import greeting, unittest; "
                        "assert greeting.greet('Cafe') == 'Hello, Cafe!'; "
                        "assert unittest.TextTestRunner().run(unittest.defaultTestLoader."
                        "loadTestsFromName('test_greeting')).wasSuccessful()",
                    ],
                    network=False,
                ),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            if await process.wait() != 0:
                raise RuntimeError("Independent greeting/test verification failed")
            info = await manager.git.info("backend")
            if len(info["history"]) != 2 or (await manager.git.info("project"))["branch"] != "main":
                raise RuntimeError("Assigned branch commit verification failed")
            manager.review(
                run["id"], True, "Independent greeting, unittest and branch commit passed"
            )
            print(
                "Real managed Codex Markdown/worktree/isolation/tests/commit smoke: PASS",
                flush=True,
            )
        finally:
            await manager.close()


if __name__ == "__main__":
    asyncio.run(main())

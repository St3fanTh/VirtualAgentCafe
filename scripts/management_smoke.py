#!/usr/bin/env python3
"""Opt-in real model smoke; isolated temporary repository, never remote Git."""

import argparse
import asyncio
import json
import tempfile
from pathlib import Path

from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.diagnostics import export, redact
from virtual_agent_cafe.management.execution import ExecutionManager


def verify_runtime(result):
    if result.get("status") != "COMPLETED" or result.get("runtime_success") is not True:
        raise RuntimeError(
            "Managed Codex smoke failed: " + str(redact(result.get("detail", "No runtime detail")))
        )
    if result.get("acceptance") != "UNVERIFIED":
        raise RuntimeError("Unexpected acceptance before independent verification")


async def main(model, deadline_seconds=360, evidence_dir=Path(".runtime/checks/managed-smoke")):
    with tempfile.TemporaryDirectory(prefix="vac-managed-smoke-") as directory:
        manager = ExecutionManager(Path(directory), EventBus())
        run = None
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
                    model=model,
                    task="smoke.md",
                    roles=["backend.md"],
                    git={"enabled": True, "repository": "project"},
                )
            )
            run = await manager.start("smoke-agent")
            cursor = 0
            async with asyncio.timeout(deadline_seconds):
                while manager.running:
                    for log in manager.store.logs(run["id"], cursor):
                        cursor = log["sequence"]
                        print(f"{log['type']} — {log['detail']}", flush=True)
                    await asyncio.sleep(0.25)
            result = manager.store.get("executions", run["id"])
            verify_runtime(result)
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
            try:
                async with asyncio.timeout(30):
                    code = await process.wait()
            except TimeoutError:
                process.kill()
                await process.wait()
                raise
            if code != 0:
                raise RuntimeError("Independent greeting/test verification failed")
            info = await manager.git.info("backend")
            committed = await manager.git.run(workspace, "ls-tree", "--name-only", "HEAD")
            tracked_diff = await manager.git.run(
                workspace, "diff", "HEAD", "--", "greeting.py", "test_greeting.py"
            )
            if (
                bool(tracked_diff.strip())
                or "greeting.py" not in committed.splitlines()
                or "test_greeting.py" not in committed.splitlines()
                or not info["branch"].startswith("agent/")
                or (await manager.git.info("project"))["branch"] != "main"
            ):
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
            if run is not None:
                evidence_dir.mkdir(parents=True, exist_ok=True)
                target = evidence_dir / (run["id"] + ".json")
                target.write_text(json.dumps(export(manager.store, run["id"]), indent=2))
                target.chmod(0o600)
                print(f"Redacted diagnostics: {target}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--timeout", type=int, default=360)
    parser.add_argument("--evidence-dir", type=Path, default=Path(".runtime/checks/managed-smoke"))
    args = parser.parse_args()
    if not 1 <= args.timeout <= 1800:
        parser.error("timeout must be between 1 and 1800 seconds")
    asyncio.run(main(args.model, args.timeout, args.evidence_dir))

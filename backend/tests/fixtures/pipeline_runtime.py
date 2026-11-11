"""Deterministic producer for Cafe pipeline tests; never invokes an LLM or remote host.

Only the producer and Git transport are fixtures. Management, worktrees, committed
requirements validation, subprocess pytest, persistence and publication are real.
"""

import json
from unittest.mock import AsyncMock

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.management.git import GitService
from virtual_agent_cafe.management.setup import ProjectSetup
from virtual_agent_cafe.models import EventType

OBJECTIVE = "Build a counter starting at zero with increment, decrement and reset operations."
COUNTER = """class Counter:
    def __init__(self):
        self.value = 0

    def increment(self):
        self.value += 1

    def decrement(self):
        self.value -= 1

    def reset(self):
        self.value = 0
"""
FRONTEND = """from counter import Counter

class CounterControls:
    def __init__(self):
        self.counter = Counter()

    def click(self, button):
        {"plus": self.counter.increment, "minus": self.counter.decrement,
         "reset": self.counter.reset}[button]()
        return str(self.counter.value)
"""
CONTRACT_TEST = """from controls import CounterControls

def test_counter_user_journey():
    ui = CounterControls()
    assert ui.counter.value == 0
    assert ui.click("plus") == "1"
    assert ui.click("plus") == "2"
    assert ui.click("minus") == "1"
    assert ui.click("reset") == "0"
    assert ui.click("minus") == "-1"
"""


class CounterRuntime:
    """Produces a known product so orchestration can be tested reproducibly."""

    def __init__(self, manager, fail_product=False):
        self.manager = manager
        self.fail_product = fail_product
        self.calls = []

    async def run(self, context, workspace, emit):
        self.calls.append(workspace.name)
        emit(EventType.CODING, "Deterministic counter fixture is writing its assigned component")
        if workspace.name.endswith("integration"):
            inputs = self.manager.integrations.inputs[workspace.name]
            assert "Read .cafe/instructions/requirements.md" in context
            (workspace / "tests").mkdir(exist_ok=True)
            (workspace / "tests/test_counter.py").write_text(CONTRACT_TEST)
            (workspace / "validation").mkdir(exist_ok=True)
            (workspace / "validation/requirements.md").write_text(inputs["text"])
            (workspace / "validation/plan.json").write_text(
                json.dumps(
                    {
                        "source_sha256": inputs["sha256"],
                        "requirements": [
                            {
                                "id": "COUNTER-1",
                                "description": OBJECTIVE,
                                "checks": ["counter-behavior"],
                            }
                        ],
                        "checks": [{"id": "counter-behavior", "kind": "pytest", "directory": "."}],
                    }
                )
            )
            # Deliberate product defect, not a weakened or swapped acceptance test.
            source = (
                COUNTER.replace("self.value = 0\n", "self.value = 7\n")
                if self.fail_product
                else COUNTER
            )
            (workspace / "counter.py").write_text(source)
            files = [
                "counter.py",
                "tests/test_counter.py",
                "validation/requirements.md",
                "validation/plan.json",
            ]
        else:
            name, source = (
                ("counter.py", COUNTER)
                if workspace.name.endswith("backend")
                else ("controls.py", FRONTEND)
            )
            (workspace / name).write_text(source)
            files = [name]
        git = self.manager.git
        await git.stage(workspace.name, files)
        if (await git.run(workspace, "diff", "--cached", "--name-only")).strip():
            await git.commit(workspace.name, "test: produce deterministic counter component")
        return RunResult(True, "Deterministic fixture finished; controller must verify behavior")


async def prepare(app, root, monkeypatch, *, fail_product=False):
    """Seed a local source + bare remote; leave setup/start to API or GUI callers."""
    monkeypatch.setenv("VAC_ALLOW_REMOTE_GIT", "1")
    monkeypatch.setattr(ProjectSetup, "command_ok", AsyncMock(return_value=True))
    manager = app.state.management
    for name in ("counter", "remote"):
        manager.workspaces.create(name)
    source = manager.workspaces.get("counter")
    remote = manager.workspaces.get("remote")
    git = manager.git
    await git.init("counter")
    (source / "PLANNING.md").write_text("# Counter requirements\n" + OBJECTIVE + "\n")
    await git.stage("counter", ["PLANNING.md"])
    await git.commit("counter", "test: seed counter requirement")
    await git.run(remote, "init", "--bare", "-q")
    await git.run(
        source,
        "-c",
        "protocol.file.allow=always",
        "push",
        str(remote),
        "HEAD:refs/heads/main",
        extra_mounts=(remote,),
    )
    initial = (await git.run(source, "rev-parse", "HEAD")).strip()
    await git.set_remote("counter", "origin", "git@example.invalid:fixture/counter.git")
    original = git.run
    pushed = []

    async def local_transport(path, *arguments, **kwargs):
        operation = GitService.operation(arguments)
        if operation in {"push", "fetch", "ls-remote"}:
            if operation == "push":
                pushed.append(arguments[-1])
            offset = arguments.index(operation)
            arguments = (
                *arguments[:offset],
                "-c",
                "protocol.file.allow=always",
                *arguments[offset:-2],
                str(remote),
                arguments[-1],
            )
            kwargs["extra_mounts"] = (remote,)
        return await original(path, *arguments, **kwargs)

    monkeypatch.setattr(git, "run", local_transport)
    runtime = CounterRuntime(manager, fail_product)
    manager.adapter = runtime
    return {
        "manager": manager,
        "remote": remote,
        "initial": initial,
        "runtime": runtime,
        "pushed": pushed,
    }

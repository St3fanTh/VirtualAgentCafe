"""Execute a requirements-linked test plan in an unauthenticated filesystem sandbox."""

import asyncio
import hashlib
import os
import signal
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from ..adapters.diagnostics import test_diagnostic
from ..models import EventType
from .config import StrictModel
from .files import ApprovedFiles
from .sandbox import Sandbox


class Check(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    kind: Literal["pytest", "godot", "npm"]
    directory: str = Field(default=".", max_length=256)
    script: str | None = Field(default=None, max_length=256)


class Requirement(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=10, max_length=2000)
    checks: list[str] = Field(min_length=1, max_length=20)


class TestPlan(StrictModel):
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    requirements: list[Requirement] = Field(min_length=1, max_length=100)
    checks: list[Check] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def coverage(self):
        names = {check.id for check in self.checks}
        if len(names) != len(self.checks) or len({r.id for r in self.requirements}) != len(
            self.requirements
        ):
            raise ValueError("Duplicate check or requirement ID")
        if {name for requirement in self.requirements for name in requirement.checks} != names:
            raise ValueError(
                "Every requirement must reference existing checks; every check must be used"
            )
        return self


async def validate(manager, config, run: dict, workspace: Path) -> dict:
    files = ApprovedFiles(workspace)
    path = files.path("validation/plan.json")
    if not path.is_file() or path.stat().st_size > 65536:
        raise ValueError("Create validation/plan.json with requirements and executable checks")
    try:
        plan = TestPlan.model_validate_json(path.read_text())
    except ValidationError:
        raise ValueError("Invalid shared test plan schema or requirement/check coverage") from None
    if plan.source_sha256 != run.get("requirements_sha256"):
        raise ValueError("Test plan does not reference the current requirements snapshot")
    head = (await manager.git.run(workspace, "rev-parse", "HEAD")).strip()
    # The plan and tests must be in the commit that will actually be published.
    tracked = set((await manager.git.run(workspace, "ls-files", "-z")).split("\0"))
    if not {"validation/plan.json", "validation/requirements.md"}.issubset(tracked):
        raise ValueError("Commit the shared requirements, test plan and tests before validation")
    source = files.path("validation/requirements.md")
    if (
        not source.is_file()
        or source.stat().st_size > 131072
        or hashlib.sha256(source.read_bytes()).hexdigest() != run.get("requirements_sha256")
    ):
        raise ValueError("Committed requirements must match the exact shared requirements snapshot")
    results = []
    for check in plan.checks:
        directory = files.path(check.directory)
        if not directory.is_dir():
            raise ValueError("Validation directory does not exist")
        relative = directory.relative_to(workspace).as_posix()
        prefix = "" if relative == "." else relative + "/"
        if check.kind == "pytest":
            if not any(
                name.startswith(prefix)
                and Path(name).name.startswith("test")
                and name.endswith(".py")
                for name in tracked
            ):
                raise ValueError("Pytest validation requires committed test files")
            command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        elif check.kind == "godot":
            script = check.script or "tests/test_states.gd"
            target = files.path(str(Path(check.directory) / script))
            if (
                not target.is_file()
                or not target.name.startswith("test")
                or target.suffix != ".gd"
                or target.relative_to(workspace).as_posix() not in tracked
            ):
                raise ValueError("Godot validation requires a committed test script")
            command = [
                "godot",
                "--headless",
                "--path",
                str(directory),
                "--script",
                "res://" + script,
            ]
        else:
            package = files.path(str(Path(check.directory) / "package.json"))
            if prefix + "package.json" not in tracked or not package.is_file():
                raise ValueError("npm validation requires a committed package.json")
            command = ["npm", "test"]
        manager.emit(run, EventType.TESTING, f"Shared check {check.id}: {check.kind} RUNNING")
        sandbox = Sandbox().command(
            workspace,
            ["/usr/bin/env", "CI=1", "PYTHONDONTWRITEBYTECODE=1", *command],
            metadata=manager.git.metadata(workspace),
            writable_git=False,
            network=False,
        )
        # Sandbox root remains the entire integration workspace; chdir is explicit.
        sandbox[sandbox.index("--chdir") + 1] = str(directory)
        process = await asyncio.create_subprocess_exec(
            *sandbox,
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        digest = hashlib.sha256()
        tail = b""
        try:
            async with asyncio.timeout(min(config.execution.timeout_seconds, 300)):
                size = 0
                while chunk := await process.stdout.read(65536):
                    size += len(chunk)
                    if size > 1024 * 1024:
                        raise ValueError("Shared test output exceeds limit")
                    digest.update(chunk)
                    tail = (tail + chunk)[-65536:]
                code = await process.wait()
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
        results.append(
            {
                "id": check.id,
                "kind": check.kind,
                "exit_code": code,
                "output_sha256": digest.hexdigest(),
                "diagnostics": test_diagnostic(check.kind, code, tail.decode(errors="replace")),
            }
        )
        manager.emit(
            run,
            EventType.TESTING if code == 0 else EventType.ERROR,
            f"Shared check {check.id}: {'PASS' if code == 0 else 'FAIL'} (exit {code})",
        )
    report = {
        "commit": head,
        "source_sha256": plan.source_sha256,
        "plan_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "requirements": [r.model_dump() for r in plan.requirements],
        "checks": results,
        "passed": all(check["exit_code"] == 0 for check in results),
    }
    run["validation"] = report
    manager.store.put("executions", run["id"], run)
    if not report["passed"]:
        raise ValueError("Shared requirements tests failed; main was not changed")
    if (await manager.git.run(workspace, "rev-parse", "HEAD")).strip() != head:
        raise ValueError("Integration commit changed during validation; rerun tests")
    return report

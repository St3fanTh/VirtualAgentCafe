"""Execute a requirements-linked test plan in an unauthenticated filesystem sandbox."""

import asyncio
import hashlib
import json
import os
import re
import signal
import sys
from datetime import UTC, datetime
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


class ValidationRuleError(ValueError):
    pass


class ValidationTrace:
    """Persist diagnostic metadata in authenticated management logs, never public events."""

    def __init__(self, manager, run, workspace):
        self.manager, self.run = manager, run
        self.context = {"selected_ref": "HEAD", "repository_root": str(workspace)}
        self.report = {**self.context, "passed": False, "checks": [], "diagnostics": []}
        self.rule = "git.snapshot"
        run["validation"] = self.report  # Never retain a previous successful validation.
        self.save()

    def save(self):
        self.manager.store.put("executions", self.run["id"], self.run)

    def record(self, rule, **values):
        entry = {**self.context, "rule": rule, **values}
        self.report["diagnostics"].append(entry)
        self.manager.store.log(
            self.run["id"],
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "type": "validation.diagnostic",
                "detail": json.dumps(entry, sort_keys=True),
            },
        )
        self.save()

    def reject(self, rule, message):
        self.report.update(passed=False, failed_rule=rule)
        self.record(rule, outcome="failed")
        raise ValidationRuleError(f"{rule}: {message}")

    def require(self, condition, rule, message):
        if not condition:
            self.reject(rule, message)


async def validate(manager, config, run: dict, workspace: Path) -> dict:
    workspace = await asyncio.to_thread(workspace.resolve)
    trace = ValidationTrace(manager, run, workspace)
    try:
        return await _validate(manager, config, run, workspace, trace)
    except ValidationRuleError:
        raise
    except ValueError as error:
        trace.reject(trace.rule, str(error))
    except OSError:
        trace.reject(trace.rule, "Validation filesystem or executable access failed")
    except TimeoutError:
        trace.reject(trace.rule, "Validation timed out")


async def _validate(manager, config, run, workspace, trace):
    files = ApprovedFiles(workspace)
    root = (await manager.git.run(workspace, "rev-parse", "--show-toplevel")).strip()
    head = (await manager.git.run(workspace, "rev-parse", "--verify", "HEAD^{commit}")).strip()
    ref = (await manager.git.run(workspace, "rev-parse", "--abbrev-ref", "HEAD")).strip()
    trace.context.update(repository_root=root, commit=head, branch=ref)
    trace.report.update(commit=head, selected_ref="HEAD", branch=ref, repository_root=root)
    trace.record("git.snapshot", outcome="selected")
    trace.require(
        await asyncio.to_thread(Path(root).resolve) == workspace,
        "git.repository_root",
        "Validation workspace must be the repository root",
    )
    expected = run.get("branch") or config.git.branch
    trace.require(
        not expected or ref == expected,
        "git.branch",
        "Checked-out branch differs from the submitted integration branch",
    )
    # Read the frozen commit tree, not the index (ls-files also includes staged additions).
    trace.rule = "git.commit_tree"
    entries = await manager.git.run(workspace, "ls-tree", "-r", "-z", "--full-tree", head)
    blobs = {}
    for entry in entries.split("\0"):
        if entry:
            metadata, name = entry.split("\t", 1)
            mode, kind, oid = metadata.split()
            if kind == "blob" and mode in {"100644", "100755"}:
                blobs[name] = oid
    tracked = set(blobs)

    async def committed(target, rule):
        relative = target.relative_to(workspace).as_posix()
        trace.context.update(
            git_path=relative,
            resolved_path=str(target),
            blob_exists=relative in blobs,
            blob_oid=blobs.get(relative),
        )
        if relative in blobs:
            trace.rule = rule + ".blob_lookup"
            trace.context["blob_exists"] = None
            kind = (await manager.git.run(workspace, "cat-file", "-t", blobs[relative])).strip()
            trace.context["blob_exists"] = kind == "blob"
            trace.require(kind == "blob", trace.rule, "Expected committed Git blob")
        trace.record(rule, outcome="inspected")
        trace.require(
            target.is_file(), rule + ".file_exists", "Declared file is absent from workspace"
        )
        trace.require(
            relative in blobs,
            rule + ".blob_exists",
            "Declared file is not a regular Git blob in the selected commit",
        )
        trace.rule = rule + ".content_matches_commit"
        actual = (
            await manager.git.run(workspace, "hash-object", "--path", relative, "--", str(target))
        ).strip()
        trace.require(
            actual == blobs[relative],
            trace.rule,
            "Workspace file differs from the selected commit; commit changes and retry",
        )

    trace.rule = "plan.path"
    path = files.path("validation/plan.json")
    await committed(path, "plan.committed")
    trace.require(path.stat().st_size <= 65536, "plan.size", "Test plan exceeds size limit")
    try:
        plan = TestPlan.model_validate_json(path.read_text())
    except ValidationError:
        trace.reject("plan.schema", "Invalid shared test plan schema or requirement/check coverage")
    trace.require(
        plan.source_sha256 == run.get("requirements_sha256"),
        "plan.requirements_snapshot",
        "Test plan does not reference the current requirements snapshot",
    )
    source = files.path("validation/requirements.md")
    await committed(source, "requirements.committed")
    trace.require(
        source.stat().st_size <= 131072
        and hashlib.sha256(source.read_bytes()).hexdigest() == run.get("requirements_sha256"),
        "requirements.content",
        "Committed requirements must match the exact shared requirements snapshot",
    )
    trace.report.update(
        source_sha256=plan.source_sha256,
        plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        requirements=[r.model_dump() for r in plan.requirements],
    )
    results = trace.report["checks"]
    for check in plan.checks:
        trace.context = {
            "selected_ref": "HEAD",
            "commit": head,
            "branch": ref,
            "repository_root": root,
            "check": check.id,
            "directory": check.directory,
            "script": check.script,
            "resolved_path": None,
            "blob_exists": None,
        }
        trace.rule = "check.directory"
        directory = files.path(check.directory)
        trace.require(directory.is_dir(), trace.rule, "Validation directory does not exist")
        relative = directory.relative_to(workspace).as_posix()
        prefix = "" if relative == "." else relative + "/"
        if check.kind == "pytest":
            trace.require(
                any(
                    name.startswith(prefix)
                    and Path(name).name.startswith("test")
                    and name.endswith(".py")
                    for name in tracked
                ),
                "pytest.committed_tests",
                "Pytest validation requires committed test files",
            )
            command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
        elif check.kind == "godot":
            declared = check.script if check.script is not None else "tests/test_states.gd"
            script = declared.removeprefix("res://")
            trace.context["script"] = declared
            trace.rule = "godot.script_path"
            trace.require(
                bool(script) and ":" not in script and "\\" not in script,
                trace.rule,
                "Use a project-relative path or res:// path",
            )
            # Both supported spellings resolve relative to the declared Godot project directory.
            project_files = ApprovedFiles(directory)
            target = project_files.path(script)
            trace.context["resolved_path"] = str(target)
            await committed(target, "godot.script")
            trace.require(
                target.suffix == ".gd",
                "godot.script_extension",
                "Godot test script must have the .gd extension",
            )
            trace.require(
                target.name.startswith("test"),
                "godot.script_name",
                "Godot test script filename must start with 'test' (file is committed)",
            )
            script = target.relative_to(directory).as_posix()
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
            await committed(package, "npm.package")
            command = ["npm", "test"]
        trace.rule = "workspace.clean_before_tests"
        await manager.git.require_clean(workspace)
        trace.rule = "check.execution"
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
        output = tail.decode(errors="replace")
        godot_error = check.kind == "godot" and bool(
            re.search(r"(?m)^(?:SCRIPT ERROR:|ERROR:)", output)
        )
        passed = code == 0 and not godot_error
        diagnostics = test_diagnostic(check.kind, code, output)
        diagnostics["passed"] = passed
        if godot_error:
            diagnostics["causes"].append("Godot reported a script or runtime error")
        results.append(
            {
                "id": check.id,
                "kind": check.kind,
                "exit_code": code,
                "passed": passed,
                "output_sha256": digest.hexdigest(),
                "diagnostics": diagnostics,
            }
        )
        manager.emit(
            run,
            EventType.TESTING if passed else EventType.ERROR,
            f"Shared check {check.id}: {'PASS' if passed else 'FAIL'} (exit {code})",
        )
    trace.rule = "git.commit_unchanged"
    trace.require(
        (await manager.git.run(workspace, "rev-parse", "HEAD")).strip() == head,
        trace.rule,
        "Integration commit changed during validation; rerun tests",
    )
    trace.rule = "workspace.clean_after_tests"
    await manager.git.require_clean(workspace)
    trace.require(
        all(check["passed"] for check in results),
        "check.result",
        "Shared requirements tests failed; main was not changed",
    )
    trace.report["passed"] = True
    trace.record("validation.complete", outcome="passed")
    return trace.report

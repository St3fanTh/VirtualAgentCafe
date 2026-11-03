"""Execute a requirements-linked test plan in an unauthenticated filesystem sandbox."""

import asyncio
import hashlib
import importlib.metadata
import json
import os
import re
import shutil
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, model_validator

from ..adapters.diagnostics import godot_failure_category, test_diagnostic
from ..models import EventType
from .config import StrictModel
from .files import ApprovedFiles
from .sandbox import Sandbox


class Check(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    kind: Literal["pytest", "godot", "npm"]
    directory: str = Field(default=".", max_length=256)
    script: str | None = Field(default=None, max_length=256)
    targets: list[str] = Field(default_factory=list, max_length=50)
    python: Literal["runtime", "project-venv"] = "runtime"

    @model_validator(mode="after")
    def supported_scope(self):
        if self.kind == "godot" and not self.script:
            raise ValueError("Godot checks require an explicit script; no implicit tests are run")
        if self.script is not None and self.kind != "godot":
            raise ValueError("script is only supported for Godot; use targets for pytest")
        if self.python != "runtime" and self.kind != "pytest":
            raise ValueError("python selection is only supported for pytest")
        if self.targets and self.kind != "pytest":
            raise ValueError("targets are only supported for pytest")
        return self


class Requirement(StrictModel):
    id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=10, max_length=2000)
    checks: list[str] = Field(min_length=1, max_length=20)


class TestPlan(StrictModel):
    manual_acceptance: list[str] = Field(default_factory=list, max_length=30)
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

    def reject(self, rule, message, *, infrastructure=None):
        if infrastructure is None:
            infrastructure = (
                rule.startswith("git.")
                or rule.endswith(".blob_lookup")
                or rule == "pytest.interpreter"
            )
        category = "VALIDATION_INFRA_ERROR" if infrastructure else "VALIDATION_FAILED"
        self.report.update(passed=False, failed_rule=rule, state=category)
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
        trace.reject(
            trace.rule,
            str(error),
            infrastructure=trace.rule.startswith("git.")
            or trace.rule.endswith(".blob_lookup")
            or trace.rule == "pytest.interpreter",
        )
    except TimeoutError:
        trace.reject(trace.rule, "Validation timed out", infrastructure=True)
    except OSError:
        trace.reject(
            trace.rule, "Validation filesystem or executable access failed", infrastructure=True
        )
    except Exception as error:
        trace.record("controller.exception", exception_type=type(error).__name__)
        trace.reject(
            "controller.exception", "Controller validation failed unexpectedly", infrastructure=True
        )


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
    trace.require(
        not run.get("submitted_commit") or head == run["submitted_commit"],
        "git.submitted_commit",
        "Workspace HEAD differs from the submitted commit",
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
    except ValidationError as error:
        trace.report["schema_errors"] = error.errors(
            include_url=False, include_input=False, include_context=False
        )
        trace.reject("plan.schema", "Invalid shared test plan; inspect validation schema_errors")
    trace.require(
        plan.source_sha256 == run.get("requirements_sha256"),
        "plan.requirements_snapshot",
        "Test plan does not reference the current requirements snapshot",
    )
    source = files.path("validation/requirements.md")
    await committed(source, "requirements.committed")
    trace.require(
        source.stat().st_size <= 262144
        and hashlib.sha256(source.read_bytes()).hexdigest() == run.get("requirements_sha256"),
        "requirements.content",
        "Committed requirements must match the exact shared requirements snapshot",
    )
    trace.report.update(
        source_sha256=plan.source_sha256,
        plan_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        requirements=[r.model_dump() for r in plan.requirements],
        manual_acceptance=plan.manual_acceptance,
    )
    trace.rule = "environment.inspect"
    environment = await asyncio.to_thread(environment_identity)
    trace.report["environment"] = environment
    results = trace.report["checks"]
    pending_cache = []
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
            interpreter = runtime_python()
            if check.python == "project-venv":
                trace.rule = "pytest.interpreter"
                # Venv interpreters commonly symlink to the approved runtime.
                interpreter = str(ApprovedFiles(directory).path(".venv/bin") / "python")
                resolved = await asyncio.to_thread(Path(interpreter).resolve)
                trace.require(
                    any(
                        resolved.is_relative_to(root)
                        for root in (workspace, Path("/usr"), Path("/bin"), Path("/opt/venv"))
                    ),
                    trace.rule,
                    "Project interpreter resolves outside approved runtime mounts",
                )
                trace.require(
                    await asyncio.to_thread(Path(interpreter).is_file),
                    trace.rule,
                    "Project Python interpreter is missing",
                )
            command = [interpreter, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
            for target in check.targets:
                trace.rule = "pytest.target"
                target_path = ApprovedFiles(directory).path(target)
                trace.require(target_path.exists(), trace.rule, "Pytest target is absent")
                command.append("./" + target_path.relative_to(directory).as_posix())
        elif check.kind == "godot":
            declared = check.script
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
        # Tests must not read run-specific RPC/instruction artifacts or credentials.
        if (workspace / ".cafe").exists():
            offset = sandbox.index("--chdir")
            sandbox[offset:offset] = ["--tmpfs", str(workspace / ".cafe")]
        # Sandbox root remains the entire integration workspace; chdir is explicit.
        sandbox[sandbox.index("--chdir") + 1] = str(directory)
        context = {
            "commit": head,
            "repository_root": root,
            "cwd": str(directory),
            "command": command,
            "check": check.model_dump(),
            "environment_sha256": environment["sha256"],
            "network": False,
            "timeout_seconds": min(config.execution.timeout_seconds, 300),
        }
        # Ignored dependencies/build products can change outside Git. Fail closed:
        # do not reuse results when such inputs exist (except controller-only .cafe).
        ignored = await manager.git.run(
            workspace,
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "-z",
            "--",
            ".",
            ":(exclude).cafe",
        )
        cache_key = hashlib.sha256(
            json.dumps(
                ["validation-v3-xdg", context, trace.report["plan_sha256"], plan.source_sha256],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        cached = None
        if not ignored:
            try:
                cached = manager.store.get("validation_cache", cache_key)
            except KeyError:
                pass
        if cached:
            result = {**cached["result"], "cached": True}
        else:
            capture = await capture_check(sandbox, context["timeout_seconds"])
            output = capture["stdout"] + "\n" + capture["stderr"]
            code = capture["exit_code"]
            diagnostics = test_diagnostic(check.kind, code, output)
            godot_error = check.kind == "godot" and bool(
                re.search(r"(?m)^(?:SCRIPT ERROR:|ERROR:)", output)
            )
            passed = code == 0 and not godot_error and not capture["error"]
            diagnostics["passed"] = passed
            if capture["error"]:
                diagnostics.update(category="ENVIRONMENT_ERROR", causes=[capture["error"]])
            elif godot_error:
                if diagnostics["category"] != "ENVIRONMENT_ERROR":
                    diagnostics["category"] = godot_failure_category(output)
                diagnostics["causes"].append("Godot reported a script or runtime error")
            result = {
                "id": check.id,
                "kind": check.kind,
                "exit_code": code,
                "passed": passed,
                "output_sha256": hashlib.sha256(output.encode()).hexdigest(),
                "diagnostics": diagnostics,
                "context": context,
                "cached": False,
            }
            if passed and not ignored:
                pending_cache.append((cache_key, result, capture))
            # Raw output stays in a separate authenticated, private endpoint.
            manager.store.put(
                "validation_outputs", run["id"] + ":" + check.id, {**capture, "context": context}
            )
        if cached:
            manager.store.put(
                "validation_outputs",
                run["id"] + ":" + check.id,
                {**cached["capture"], "context": context, "cached": True},
            )
        results.append(result)
        passed, code = result["passed"], result["exit_code"]
        trace.save()
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
    if environment != await asyncio.to_thread(environment_identity):
        trace.reject(
            "environment.changed",
            "Runtime dependencies changed during validation",
            infrastructure=True,
        )
    for key, result, capture in pending_cache:
        manager.store.put("validation_cache", key, {"result": result, "capture": capture})
    if not all(check["passed"] for check in results):
        failures = [check for check in results if not check["passed"]]
        infrastructure = any(c["diagnostics"]["category"] != "TEST_FAILURE" for c in failures)
        detail = "; ".join(
            f"{c['id']}: {c['diagnostics']['category']} (exit {c['exit_code']})" for c in failures
        )
        trace.reject(
            "check.result", detail + "; main was not changed", infrastructure=infrastructure
        )
    trace.report.update(passed=True, state="VALIDATION_PASSED")
    trace.record("validation.complete", outcome="passed")
    return trace.report


def runtime_python():
    # Match Sandbox.command's fixed PATH, never a host-only controller virtualenv.
    for location in ("/opt/venv/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"):
        if Path(location).is_file():
            return location
    raise OSError("Approved Python runtime unavailable")


def environment_identity():
    """Conservative local runtime identity, including installed package file metadata."""
    packages = sorted(
        (d.metadata.get("Name", ""), d.version) for d in importlib.metadata.distributions()
    )
    files = []
    for directory in {Path(sys.prefix), Path("/opt/venv"), Path("/usr/local/lib/node_modules")}:
        if directory.exists() and directory != Path("/usr"):
            for path in sorted(directory.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    stat = path.stat()
                    files.append((str(path), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns))
    tools = {}
    for name in (runtime_python(), "godot", "node", "npm", "bwrap"):
        path = shutil.which(name, path="/opt/venv/bin:/usr/local/bin:/usr/bin:/bin")
        tools[name] = hashlib.sha256(Path(path).read_bytes()).hexdigest() if path else None
    for file in ("/etc/os-release", "/var/lib/dpkg/status"):
        if Path(file).is_file():
            tools[file] = hashlib.sha256(Path(file).read_bytes()).hexdigest()
    identity = {
        "python": runtime_python(),
        "version": sys.version,
        "packages": packages,
        "tools": tools,
        "platform": tuple(os.uname()),
    }
    digest = hashlib.sha256(json.dumps([identity, files], sort_keys=True).encode()).hexdigest()
    return {"runtime_python": runtime_python(), "controller_version": sys.version, "sha256": digest}


async def capture_check(command, seconds):
    """Drain both pipes, retain private output, and make bounds/timeouts explicit."""
    chunks = {"stdout": bytearray(), "stderr": bytearray()}
    result = {"exit_code": None, "error": None, "truncated": False}
    process = None

    async def read(stream, name):
        while data := await stream.read(65536):
            remaining = 1024 * 1024 - len(chunks[name])
            chunks[name].extend(data[:remaining])
            if len(data) > remaining:
                result["truncated"] = True
                raise ValueError("Validation output exceeds 1 MiB per stream; output truncated")

    readers = []
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        readers = [
            asyncio.create_task(read(process.stdout, "stdout")),
            asyncio.create_task(read(process.stderr, "stderr")),
        ]
        async with asyncio.timeout(seconds):
            await asyncio.gather(*readers)
            result["exit_code"] = await process.wait()
    except TimeoutError:
        result["error"] = "Validation timed out"
    except OSError:
        result["error"] = "Validation executable or sandbox could not be started"
    except ValueError as error:
        result["error"] = str(error)
    finally:
        if process:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()
            result["exit_code"] = process.returncode
        for reader in readers:
            if not reader.done():
                reader.cancel()
        await asyncio.gather(*readers, return_exceptions=True)
    return {**result, **{name: value.decode(errors="replace") for name, value in chunks.items()}}

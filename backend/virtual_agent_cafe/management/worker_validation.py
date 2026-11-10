"""Recheck observed socket-blocked Godot tests, never arbitrary shell commands."""

import asyncio
import hashlib
import json
import re
import shlex
from pathlib import Path

from ..adapters.base import RunResult
from ..adapters.codex import test_scope_id
from ..models import EventType
from . import validation
from .files import ApprovedFiles

RUNTIME_VARIABLES = {
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_RUNTIME_DIR",
    "XDG_STATE_HOME",
    "FONTCONFIG_FILE",
    "FONTCONFIG_PATH",
}


def tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def observed_check(evidence, workspace):
    """Accept a single explicit Godot test, optionally env/cd/a literal shell wrapper."""
    workspace = workspace.resolve()
    files = ApprovedFiles(workspace)

    def path(value, cwd):
        value = value.replace("${PWD}", str(cwd)).replace("$PWD", str(cwd))
        if any(c in value for c in ("$", "`", "\n", "\x00")):
            raise ValueError("Unsupported variable or command substitution in Godot invocation")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = cwd / candidate
        try:
            relative = candidate.relative_to(workspace)
        except ValueError:
            raise ValueError("Observed Godot path is outside the assigned workspace") from None
        return files.path(str(relative))

    cwd = path(evidence.get("reported_cwd") or str(workspace), workspace)
    command = evidence["command"]
    if len(command) > 65536:
        raise ValueError("Observed command exceeds limit")
    args = tokens(command)
    # Codex reports both /bin and /usr/bin shell wrappers. Unwrap only these
    # literal paths; the controller executes the validated Godot argv, never a shell.
    for _ in range(3):
        if (
            len(args) == 3
            and args[0] in {"bash", "sh", "/bin/bash", "/bin/sh", "/usr/bin/bash", "/usr/bin/sh"}
            and args[1]
            in {
                "-c",
                "-lc",
            }
        ):
            args = tokens(args[2])
        else:
            break
    if args[:1] == ["cd"]:
        if len(args) < 4 or args[2] != "&&":
            raise ValueError("Unsupported working-directory command")
        cwd = path(args[1], cwd)
        args = args[3:]
    if args[:1] == ["env"]:
        args = args[1:]
    environment = {}
    while args and "=" in args[0]:
        name, value = args.pop(0).split("=", 1)
        if name not in RUNTIME_VARIABLES or name in environment:
            label = name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}", name) else "<invalid name>"
            reason = "Repeated" if name in environment else "Unsupported"
            raise ValueError(f"{reason} test environment setting: {label}")
        environment[name] = value
    if not args or args.pop(0) not in {"godot", "/usr/local/bin/godot"}:
        raise ValueError("Only the approved Godot runtime can be rechecked")
    values = {}
    headless = False
    while args:
        flag = args.pop(0)
        if flag == "--headless" and not headless:
            headless = True
        elif flag in {"--path", "--script"} and args and flag not in values:
            values[flag] = args.pop(0)
        else:
            raise ValueError(
                "Unsupported Godot arguments; no shell, pipelines or wrappers replayed"
            )
    if not headless or "--script" not in values:
        raise ValueError("An explicit headless Godot test script is required")
    directory = path(values.get("--path", str(cwd)), cwd)
    script = values["--script"].removeprefix("res://")
    script_path = path(script, directory)
    try:
        script = script_path.relative_to(directory).as_posix()
    except ValueError:
        raise ValueError("Godot script must be inside its project directory") from None
    fields = {
        "kind": "godot",
        "directory": directory.relative_to(workspace).as_posix(),
        "script": script,
    }
    for name, field, default in (
        ("FONTCONFIG_FILE", "fontconfig_file", "/etc/fonts/fonts.conf"),
        ("FONTCONFIG_PATH", "fontconfig_path", "/etc/fonts"),
    ):
        if name in environment and environment[name] != default:
            fields[field] = path(environment[name], cwd).relative_to(workspace).as_posix()
    # XDG directories are deliberately replaced by private per-check runtime directories.
    identifier = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:20]
    return validation.Check(id="worker-" + identifier, **fields)


def candidates(result, evidence, workspace):
    if result.success or not result.implementation_complete:
        return None
    if len(result.test_runs) >= 100 or len(evidence["checks"]) >= 100:
        raise ValueError("Cannot recheck incomplete history at the evidence retention limit")
    active = [t for t in result.test_runs if not t.get("superseded")]
    failures = [t for t in active if not t.get("passed")]
    if not failures or any(
        not t.get("tool", "").startswith("Godot")
        or t.get("category") not in {"UNCLASSIFIED_ERROR", "ENVIRONMENT_ERROR"}
        for t in failures
    ):
        return None
    by_scope = {test_scope_id(e["command"], e.get("reported_cwd")): e for e in evidence["checks"]}
    for failure in failures:
        row = by_scope.get(failure.get("scope_sha256"))
        if not row:
            raise ValueError("Private command evidence is missing for a failed Godot test")
        output = row.get("aggregated_output", "")
        if "_sock == -1" not in output or "net_socket_unix.cpp" not in output:
            return None
    checks, scopes = {}, {}
    # Recheck all observed Godot scopes, including passing companions, at submitted HEAD.
    for item in active:
        if not item.get("tool", "").startswith("Godot"):
            continue
        scope = item.get("scope_sha256")
        if scope not in by_scope:
            raise ValueError("Private command evidence is incomplete")
        row = by_scope[scope]
        if Path(row["workspace"]).resolve() != workspace.resolve():
            raise ValueError("Observed test belongs to a different workspace")
        check = observed_check(row, workspace)
        checks[check.id] = check
        scopes[scope] = check.id
    return list(checks.values()), scopes


async def recover(manager, config, run, workspace, result):
    if result.success or not result.implementation_complete or not config.git.enabled:
        return result
    try:
        evidence = manager.store.get("runtime_test_outputs", run["id"])
    except KeyError:
        return result
    try:
        selected = candidates(result, evidence, workspace)
        if selected is None:
            return result
        checks, scopes = selected
        run["submitted_commit"] = (
            await manager.git.run(workspace, "rev-parse", "--verify", "HEAD^{commit}")
        ).strip()
        manager.emit(
            run, EventType.TESTING, "Controller: rechecking socket-blocked Godot tests offline"
        )
        async with asyncio.timeout(config.execution.timeout_seconds):
            report = await validation.validate(
                manager, config, run, workspace, observed_checks=checks
            )
    except (ValueError, TimeoutError) as error:
        detail = str(error) or "Controller Godot recheck timed out"
        run.setdefault("worker_validation", {}).update(passed=False, detail=detail[:512])
        manager.emit(
            run, EventType.ERROR, "Controller Godot recheck failed; inspect private report"
        )
        return RunResult(
            False,
            "Controller Godot recheck failed: " + detail[:200],
            result.test_runs,
            result.implementation_complete,
        )
    history = []
    for item in result.test_runs:
        updated = dict(item)
        if item.get("scope_sha256") in scopes:
            updated.update(
                superseded=True,
                resolved_by=scopes[item["scope_sha256"]],
                resolved_commit=report["commit"],
            )
        history.append(updated)
    history.extend(
        {
            **c["diagnostics"],
            "origin": "controller",
            "check_id": c["id"],
            "commit": report["commit"],
            "cached": c["cached"],
        }
        for c in report["checks"]
    )
    run["controller_recovered"] = True
    run["workflow"]["validation"] = "VALIDATION_PASSED"
    return RunResult(
        True, "Controller Godot recheck passed at submitted commit", tuple(history), True
    )

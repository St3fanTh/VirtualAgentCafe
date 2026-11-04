import asyncio
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
from pathlib import Path

from ..models import EventType
from .base import Emit, RunResult
from .diagnostics import godot_failure_category, godot_user_data_failure, test_diagnostic


def test_command_label(command: str, depth: int = 0) -> str | None:
    if depth > 3 or len(command) > 65536:
        return None
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    groups: list[list[str]] = [[]]
    for token in tokens:
        if token and all(char in ";&|" for char in token):
            groups.append([])
        else:
            groups[-1].append(token)
    for words in groups:
        while words and ("=" in words[0] or words[0] == "env"):
            words = words[1:]
        if not words:
            continue
        executable = Path(words[0]).name
        if executable in {"bash", "sh", "zsh"}:
            for index, word in enumerate(words[1:], 1):
                if word.startswith("-") and "c" in word and index + 1 < len(words):
                    nested = test_command_label(words[index + 1], depth + 1)
                    if nested:
                        return nested
            continue
        if executable in {"pytest", "py.test"}:
            return "pytest"
        if executable.startswith("python") and words[1:3] in [["-m", "pytest"], ["-m", "unittest"]]:
            return "python -m " + words[2]
        if executable in {"npm", "pnpm", "yarn", "cargo", "go"}:
            if words[1:2] == ["test"] or words[1:3] == ["run", "test"]:
                return executable + " test"
        if executable == "check.sh" and "scripts/" in words[0]:
            return "project checks"
        if executable in {"godot", "godot4"} and "--headless" in words[1:]:
            return "Godot headless tests"
        if executable == "uv" and words[1:2] == ["run"]:
            nested = test_command_label(shlex.join(words[2:]), depth + 1)
            if nested:
                return nested
    return None


def is_test_command(command: str, depth: int = 0) -> bool:
    return bool(test_command_label(command, depth))


def test_scope_tokens(command: str, depth: int = 0):
    """Normalize presentation flags, but retain cwd, interpreter, selectors and config."""
    if depth > 3:
        return command
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return command
    groups = [[]]
    for token in tokens:
        if token and all(char in ";&|" for char in token):
            groups.extend([[token], []])
        else:
            groups[-1].append(token)
    for group in groups:
        index = 0
        while index < len(group) and ("=" in group[index] or group[index] == "env"):
            index += 1
        if index == len(group):
            continue
        executable = Path(group[index]).name
        if executable in {"godot", "godot4"} and "--headless" in group[index + 1 :]:
            # Runtime-directory/font repairs do not change which Godot suite runs.
            # This identifies observed reruns only, never controller cache entries.
            # Keep other environment values, executable, script, cwd and flags intact.
            setup_variables = {
                "XDG_DATA_HOME",
                "XDG_CONFIG_HOME",
                "XDG_CACHE_HOME",
                "XDG_RUNTIME_DIR",
                "FONTCONFIG_FILE",
                "FONTCONFIG_PATH",
            }
            prefix = [
                word
                for word in group[:index]
                if word != "env" and word.split("=", 1)[0] not in setup_variables
            ]
            group[:] = prefix + group[index:]
            index = len(prefix)
        if executable in {"bash", "sh", "zsh"}:
            for offset in range(index + 1, len(group) - 1):
                if group[offset].startswith("-") and "c" in group[offset]:
                    group[offset + 1] = test_scope_tokens(group[offset + 1], depth + 1)
                    break
        elif executable in {"pytest", "py.test"} or (
            executable.startswith("python") and group[index + 1 : index + 3] == ["-m", "pytest"]
        ):
            group[index + 1 :] = [
                value
                for value in group[index + 1 :]
                if value not in {"--quiet", "--verbose", "--no-header", "--no-summary"}
                and not re.fullmatch(r"-(?:q+|v+)", value)
            ]
    return groups


def test_scope_id(command: str, cwd) -> str:
    scope = json.dumps([test_scope_tokens(command), cwd])
    return hashlib.sha256(scope.encode()).hexdigest()


MAX_LINE = 1024 * 1024


class CodexObserver:
    """Map evidence to public activity; raw commands, text and reasoning stay private."""

    def __init__(self, emit: Emit):
        self.emit = emit
        self.turn_complete = False
        self.fatal = False
        self.test_runs: list[dict] = []
        self.failed_diagnostics: dict[str, str] = {}
        self.failed_tests = False
        self.failed_frameworks: set[str] = set()
        self.failed_patch = False
        self.command_warnings = 0
        self.sandbox_failed = False

    def consume(self, data: dict) -> None:
        kind = data.get("type")
        item = data.get("item", {})
        if not isinstance(item, dict):
            raise ValueError("Invalid Codex item")
        item_type = item.get("type")
        if kind == "turn.started":
            self.turn_complete = False
            self.emit(EventType.THINKING, "Codex model turn active")
        elif kind == "turn.completed":
            self.turn_complete = True
        elif kind in {"turn.failed", "error"}:
            self.fatal = True
            self.emit(EventType.ERROR, "Codex reported a runtime error")
        elif kind in {"item.started", "item.completed", "item.updated"}:
            if item_type == "file_change" and kind in {"item.started", "item.completed"}:
                if item.get("status") == "failed":
                    self.failed_patch = True
                    self.emit(EventType.ERROR, "Codex file edit failed")
                else:
                    self.failed_patch = False
                    changes = item.get("changes", [])
                    count = len(changes) if isinstance(changes, list) else 0
                    detail = f"Editing files · {count} changes" if count else "Editing files"
                    self.emit(EventType.CODING, detail)
            elif item_type == "command_execution":
                test_label = test_command_label(str(item.get("command", "")))
                output = str(item.get("aggregated_output", ""))
                if not test_label and godot_user_data_failure(output):
                    # Wrapper scripts can hide the executable; this specific engine
                    # diagnostic still proves a blocked runtime, not a harmless helper.
                    test_label = "Godot runtime"
                testing = bool(test_label)
                if kind == "item.started":
                    self.emit(
                        EventType.TESTING if testing else EventType.WAITING,
                        f"CLI: {test_label} · RUNNING" if testing else "CLI: running shell command",
                    )
                elif kind == "item.completed":
                    godot_error = bool(
                        test_label
                        and test_label.startswith("Godot")
                        and re.search(
                            r"(?m)^(?:SCRIPT ERROR:|ERROR:)", str(item.get("aggregated_output", ""))
                        )
                    )
                    failed = (
                        item.get("exit_code") != 0 or item.get("status") == "failed" or godot_error
                    )
                    if failed:
                        self.command_warnings += 1
                    if testing:
                        diagnostic = test_diagnostic(
                            test_label,
                            item.get("exit_code"),
                            str(item.get("aggregated_output", "")),
                        )
                        diagnostic["passed"] = not failed
                        diagnostic["origin"] = "worker_command"
                        diagnostic["command_id"] = item.get("id")
                        if godot_error:
                            if diagnostic["category"] != "ENVIRONMENT_ERROR":
                                diagnostic["category"] = godot_failure_category(output)
                            diagnostic["causes"].append("Godot reported a script or runtime error")
                        self.test_runs.append(diagnostic)
                        self.test_runs = self.test_runs[-100:]
                        # A passing subset must not clear a failure in a different cwd/suite.
                        framework = test_scope_id(str(item.get("command", "")), item.get("cwd"))
                        diagnostic["scope_sha256"] = framework
                        for prior in self.test_runs[:-1]:
                            if prior.get("scope_sha256") == framework:
                                prior["superseded"] = True
                        if failed:
                            self.failed_frameworks.add(framework)
                            cause = "; ".join(diagnostic["causes"]) or "Test command failed"
                            self.failed_diagnostics[framework] = (
                                f"{test_label} (exit {diagnostic['exit_code']}): {cause}"
                            )
                        else:
                            self.failed_frameworks.discard(framework)
                            self.failed_diagnostics.pop(framework, None)
                        self.failed_tests = bool(self.failed_frameworks)
                    # Known environment failure must never become a success animation.
                    output = str(item.get("aggregated_output", ""))
                    if "No permissions to create a new namespace" in output or (
                        failed and "bwrap:" in output
                    ):
                        self.fatal = True
                        self.sandbox_failed = True
                        self.emit(EventType.ERROR, "Codex sandbox unavailable: namespace denied")
                    elif failed:
                        label = test_label or "shell command"
                        self.emit(
                            EventType.ERROR,
                            (
                                f"CLI: {label} · FAIL (exit {item.get('exit_code')})"
                                + (" · " + "; ".join(diagnostic["causes"]) if testing else "")
                            )[:256],
                        )
                    elif testing:
                        self.emit(EventType.TESTING, f"CLI: {test_label} · PASS (exit 0)")
                    else:
                        self.emit(EventType.THINKING, "CLI command finished · model turn active")
            elif item_type in {"agent_message", "collab_tool_call"}:
                if kind == "item.completed":
                    self.emit(EventType.MESSAGE, "Codex sent a response (content kept private)")
            elif item_type == "error":
                self.fatal = True
                self.emit(EventType.ERROR, "Codex tool reported an error")
            # Reasoning items are intentionally ignored.

    @property
    def successful(self) -> bool:
        return self.turn_complete and not (self.fatal or self.failed_tests or self.failed_patch)


class CodexAdapter:
    def __init__(
        self,
        executable: str | None = None,
        timeout: float = 300,
        *,
        model: str | None = None,
        evidence_sink=None,
    ):
        self.executable = executable or shutil.which("codex") or "codex"
        self.timeout = timeout
        self.model = model
        self.evidence_sink = evidence_sink

    def arguments(self, workspace: Path) -> list[str]:
        return [
            self.executable,
            "exec",
            *(["--model", self.model] if self.model else []),
            "--json",
            "--ephemeral",
            "--ignore-user-config",
            "--sandbox",
            "workspace-write",
            "-C",
            str(workspace),
            "--output-last-message",
            str(workspace / ".cafe" / "last-response.md"),
            "-",
        ]

    @staticmethod
    def prepare_response_file(workspace: Path) -> None:
        response_file = workspace / ".cafe" / "last-response.md"
        if not response_file.resolve().is_relative_to(workspace.resolve()):
            raise ValueError("Invalid response path")
        response_file.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def code_snapshot(workspace: Path) -> dict:
        excluded = {
            ".git",
            ".cafe",
            ".venv",
            "node_modules",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            ".godot",
        }
        extensions = {
            ".py",
            ".gd",
            ".gdshader",
            ".tscn",
            ".godot",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".html",
            ".css",
            ".scss",
            ".json",
            ".toml",
            ".yaml",
            ".yml",
            ".sql",
            ".rs",
            ".go",
            ".c",
            ".cpp",
            ".h",
            ".java",
            ".cs",
            ".md",
        }
        snapshot = {}
        for visited, (directory, folders, files) in enumerate(os.walk(workspace)):
            if visited >= 512 or len(snapshot) >= 512:
                break
            folders[:] = [
                name
                for name in folders
                if name not in excluded and not (Path(directory) / name).is_symlink()
            ]
            for name in files:
                path = Path(directory) / name
                if path.suffix not in extensions or path.is_symlink():
                    continue
                try:
                    stat = path.stat()
                except OSError:
                    continue
                snapshot[str(path.relative_to(workspace))] = (stat.st_mtime_ns, stat.st_size)
                if len(snapshot) >= 512:
                    break
        return snapshot

    async def run(self, prompt: str, workspace: Path, emit: Emit) -> RunResult:
        observer = CodexObserver(emit)
        process = None
        try:
            await asyncio.to_thread(self.prepare_response_file, workspace)
            previous_files = await asyncio.to_thread(self.code_snapshot, workspace)
            async with asyncio.timeout(self.timeout):
                process = await asyncio.create_subprocess_exec(
                    *self.arguments(workspace),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                    limit=MAX_LINE,
                )
                process.stdin.write(prompt.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()
                total = 0
                while line := await process.stdout.readline():
                    total += len(line)
                    if total > 64 * MAX_LINE:
                        raise ValueError("Codex stream exceeds limit")
                    data = json.loads(line)
                    if not isinstance(data, dict):
                        raise ValueError("Invalid Codex event")
                    previous_test = observer.test_runs[-1] if observer.test_runs else None
                    observer.consume(data)
                    item = data.get("item", {})
                    if (
                        self.evidence_sink
                        and data.get("type") == "item.completed"
                        and item.get("type") == "command_execution"
                        and observer.test_runs
                        and observer.test_runs[-1] is not previous_test
                    ):
                        await self.evidence_sink(item, workspace)
                    if data.get("type") == "item.completed" and item.get("type") in {
                        "command_execution",
                        "file_change",
                    }:
                        current_files = await asyncio.to_thread(self.code_snapshot, workspace)
                        changed = sum(
                            previous_files.get(path) != current_files.get(path)
                            for path in previous_files.keys() | current_files.keys()
                        )
                        if changed and item.get("type") == "command_execution":
                            emit(EventType.CODING, f"CLI wrote code files · {changed} changes")
                        previous_files = current_files
                code = await process.wait()
                if code == 0 and observer.successful:
                    detail = "Codex turn completed; see workspace and .cafe/last-response.md"
                    if observer.command_warnings:
                        detail = (
                            "Codex turn completed with command warnings; see .cafe/last-response.md"
                        )
                    return RunResult(True, detail, tuple(observer.test_runs))
                if observer.sandbox_failed:
                    return RunResult(
                        False,
                        "Codex sandbox unavailable; check container namespaces",
                        tuple(observer.test_runs),
                    )
                if observer.failed_tests:
                    return RunResult(
                        False,
                        "Unresolved tests: " + "; ".join(observer.failed_diagnostics.values()),
                        tuple(observer.test_runs),
                        implementation_complete=code == 0
                        and observer.turn_complete
                        and not observer.fatal
                        and not observer.failed_patch,
                    )
                if observer.failed_patch:
                    return RunResult(
                        False, "Codex task ended with a failed file edit", tuple(observer.test_runs)
                    )
                return RunResult(
                    False,
                    "Codex runtime failed or turn did not complete",
                    tuple(observer.test_runs),
                )
        except TimeoutError:
            return RunResult(False, "Codex task timed out", tuple(observer.test_runs))
        except (OSError, ValueError, json.JSONDecodeError):
            return RunResult(
                False,
                "Codex unavailable or invalid runtime event stream",
                tuple(observer.test_runs),
            )
        finally:
            if process:
                # Also reap children if the leader exited; no background tools survive a task.
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                if process.returncode is None:
                    try:
                        async with asyncio.timeout(2):
                            await process.wait()
                    except TimeoutError:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        await process.wait()
                # The leader may have exited while an ignoring child still holds pipes.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

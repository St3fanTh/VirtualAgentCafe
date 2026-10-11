import asyncio
import json
import os
import shlex
import shutil
import signal
from pathlib import Path

from ..models import EventType
from .base import Emit, RunResult


def is_test_command(command: str, depth: int = 0) -> bool:
    if depth > 3 or len(command) > 65536:
        return False
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return False
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
                    if is_test_command(words[index + 1], depth + 1):
                        return True
            continue
        if executable in {"pytest", "py.test"}:
            return True
        if executable.startswith("python") and words[1:3] in [["-m", "pytest"], ["-m", "unittest"]]:
            return True
        if executable in {"npm", "pnpm", "yarn", "cargo", "go"}:
            if words[1:2] == ["test"] or words[1:3] == ["run", "test"]:
                return True
        if executable == "check.sh" and "scripts/" in words[0]:
            return True
        if executable == "godot" and "--headless" in words[1:]:
            return True
        if executable == "uv" and words[1:2] == ["run"]:
            if is_test_command(shlex.join(words[2:]), depth + 1):
                return True
    return False


MAX_LINE = 1024 * 1024


class CodexObserver:
    """Map evidence to public activity; raw commands, text and reasoning stay private."""

    def __init__(self, emit: Emit):
        self.emit = emit
        self.turn_complete = False
        self.fatal = False
        self.failed_tests = False
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
                    self.emit(EventType.CODING, "Codex editing files")
            elif item_type == "command_execution":
                testing = is_test_command(str(item.get("command", "")))
                if kind == "item.started":
                    self.emit(
                        EventType.TESTING if testing else EventType.WAITING,
                        "Codex running tests" if testing else "Codex executing a command",
                    )
                elif kind == "item.completed":
                    failed = item.get("exit_code") not in (None, 0)
                    if failed:
                        self.command_warnings += 1
                    if testing:
                        self.failed_tests = failed
                    # Known environment failure must never become a success animation.
                    output = str(item.get("aggregated_output", ""))
                    if "No permissions to create a new namespace" in output or (
                        failed and "bwrap:" in output
                    ):
                        self.fatal = True
                        self.sandbox_failed = True
                        self.emit(EventType.ERROR, "Codex sandbox unavailable: namespace denied")
                    elif failed:
                        self.emit(EventType.ERROR, "Codex command failed")
                    else:
                        self.emit(EventType.WAITING, "Codex command completed")
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
    def __init__(self, executable: str | None = None, timeout: float = 300):
        self.executable = executable or shutil.which("codex") or "codex"
        self.timeout = timeout

    def arguments(self, workspace: Path) -> list[str]:
        return [
            self.executable,
            "exec",
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

    async def run(self, prompt: str, workspace: Path, emit: Emit) -> RunResult:
        observer = CodexObserver(emit)
        process = None
        try:
            await asyncio.to_thread(self.prepare_response_file, workspace)
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
                    observer.consume(data)
                code = await process.wait()
                if code == 0 and observer.successful:
                    detail = "Codex turn completed; see workspace and .cafe/last-response.md"
                    if observer.command_warnings:
                        detail = (
                            "Codex turn completed with command warnings; see .cafe/last-response.md"
                        )
                    return RunResult(True, detail)
                if observer.sandbox_failed:
                    return RunResult(False, "Codex sandbox unavailable; check container namespaces")
                if observer.failed_tests:
                    return RunResult(False, "Codex task ended with failing tests")
                if observer.failed_patch:
                    return RunResult(False, "Codex task ended with a failed file edit")
                return RunResult(False, "Codex runtime failed or turn did not complete")
        except TimeoutError:
            return RunResult(False, "Codex task timed out")
        except (OSError, ValueError, json.JSONDecodeError):
            return RunResult(False, "Codex unavailable or invalid runtime event stream")
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

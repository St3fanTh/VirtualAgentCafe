"""Linux mount/PID namespaces: expose runtime libraries and one approved work tree."""

import asyncio
import os
import shutil
import signal
from pathlib import Path

from ..adapters.codex import CodexAdapter


def bubblewrap() -> str:
    installed = shutil.which("bwrap")
    if installed:
        return installed
    vendor = Path("/usr/local/lib/node_modules/@openai/codex/node_modules")
    found = sorted(vendor.glob("@openai/codex-linux-*/vendor/*/codex-resources/bwrap"))
    if found:
        return str(found[0])
    raise ValueError("Install bubblewrap; managed agents require filesystem isolation")


class Sandbox:
    def __init__(self, auth_home: Path | None = None):
        self.auth_home = auth_home

    def command(
        self,
        workspace: Path,
        command: list[str],
        *,
        metadata: list[Path] = (),
        authenticated: bool = False,
        network: bool = True,
        ssh: bool = False,
        writable_git: bool = True,
        instructions: Path | None = None,
    ) -> list[str]:
        args = [
            bubblewrap(),
            "--unshare-user",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
            "--cap-drop",
            "ALL",
            "--clearenv",
            "--setenv",
            "PATH",
            "/opt/venv/bin:/usr/local/bin:/usr/bin:/bin",
            "--setenv",
            "HOME",
            "/home/agent",
            "--setenv",
            "CODEX_HOME",
            "/home/agent/.codex",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--setenv",
            "TMPDIR",
            "/tmp",
        ]
        if not network:
            args += ["--unshare-net"]
        # No /workspace, /home/node, /run, host /tmp, SSH socket or controller environment.
        for location in ["/usr", "/bin", "/lib", "/lib64", "/opt/venv"]:
            if Path(location).exists():
                args += ["--ro-bind", location, location]
        for location in ["/etc/ssl", "/etc/resolv.conf", "/etc/hosts", "/etc/nsswitch.conf"]:
            if Path(location).exists():
                args += ["--ro-bind", location, location]
        args += [
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/home/agent",
            "--dir",
            "/home/agent/.codex",
        ]
        if authenticated:
            home = self.auth_home or Path(os.getenv("CODEX_HOME", Path.home() / ".codex"))
            auth = home / "auth.json"
            if auth.is_symlink():
                raise ValueError("Authentication file must not be a symlink")
            if auth.exists():
                # Runtime requires auth, but controller configuration/history are not exposed.
                args += ["--ro-bind", str(auth), "/home/agent/.codex/auth.json"]
        if ssh:
            # OpenSSH resolves the caller UID before contacting the remote. Expose
            # only public account metadata, never shadow files or home directories.
            for location in ["/etc/passwd", "/etc/group"]:
                if Path(location).is_file():
                    args += ["--ro-bind", location, location]
            sock = os.getenv("SSH_AUTH_SOCK")
            known = Path.home() / ".ssh" / "known_hosts"
            if sock and known.is_file():
                args += [
                    "--bind",
                    sock,
                    "/run/ssh-agent",
                    "--setenv",
                    "SSH_AUTH_SOCK",
                    "/run/ssh-agent",
                    "--dir",
                    "/home/agent/.ssh",
                    "--ro-bind",
                    str(known),
                    "/home/agent/.ssh/known_hosts",
                ]
        args += [
            "--setenv",
            "GIT_CONFIG_GLOBAL",
            "/dev/null",
            "--setenv",
            "GIT_CONFIG_NOSYSTEM",
            "1",
            "--setenv",
            "GIT_TERMINAL_PROMPT",
            "0",
        ]
        args += ["--bind", str(workspace), str(workspace)]
        if not writable_git and (workspace / ".git").exists():
            args += ["--ro-bind", str(workspace / ".git"), str(workspace / ".git")]
        for path in metadata:
            args += ["--bind" if writable_git else "--ro-bind", str(path), str(path)]
        if instructions is not None:
            args += ["--ro-bind", str(instructions), str(workspace / ".cafe/instructions")]
        args += ["--chdir", str(workspace), "--", *command]
        return args

    @staticmethod
    def failure(stderr: str, code: int | None) -> dict:
        # Classify only the trusted, unauthenticated /usr/bin/true self-test.
        # Raw stderr can contain private workspace paths and never enters the API.
        text = stderr.lower()
        reason = "sandbox_failed"
        detail = "Sandbox self-test failed. Run scripts/sandbox-diagnostics.py in the backend."
        if "no space left on device" in text:
            reason = "namespace_limit"
            detail = (
                "Sandbox resource limit reached. Check host namespace limits and available space."
            )
        elif any(
            term in text
            for term in ("operation not permitted", "permission denied", "no permissions")
        ):
            reason = "namespace_denied"
            detail = (
                "Namespace creation or mounts denied by the kernel/container. "
                "Start the local starter with --privileged; if already enabled, "
                "check the Docker/WSL host namespace policy."
            )
        elif any(
            term in text
            for term in (
                "ro-bind",
                "bind mount",
                "read-only file system",
                "can't mkdir",
                "can't chdir",
            )
        ):
            reason = "mount_failed"
            detail = (
                "Sandbox mount setup failed. "
                "Check the selected workspace mount and directory permissions."
            )
        elif "execvp" in text or "no such file or directory" in text:
            reason = "runtime_missing"
            detail = (
                "Sandbox runtime or mount target is missing. "
                "Rebuild the backend and check the project mount."
            )
        return {"ok": False, "code": reason, "exit_code": code, "detail": detail}

    async def probe(self, workspace: Path) -> dict:
        try:
            command = self.command(workspace, ["/usr/bin/true"], network=False)
        except ValueError:
            return {
                "ok": False,
                "code": "runtime_missing",
                "exit_code": None,
                "detail": "Bubblewrap is missing. "
                "Rebuild the backend image or install bubblewrap locally.",
            }
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except OSError:
            return {
                "ok": False,
                "code": "launch_failed",
                "exit_code": None,
                "detail": "Sandbox executable could not be started. "
                "Check installation and executable permissions.",
            }
        try:
            async with asyncio.timeout(5):
                output = bytearray()
                while chunk := await process.stderr.read(1024):
                    output.extend(chunk)
                    if len(output) > 4096:
                        return self.failure("", None)
                code = await process.wait()
            if code:
                return self.failure(output.decode("utf-8", errors="replace"), code)
            return {
                "ok": True,
                "code": "ready",
                "exit_code": 0,
                "detail": "Workspace namespace isolation ready",
            }
        except TimeoutError:
            return {
                "ok": False,
                "code": "timeout",
                "exit_code": None,
                "detail": "Sandbox self-test timed out. Check container and host namespace setup.",
            }
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.communicate()

    async def validate(self, workspace: Path):
        result = await self.probe(workspace)
        if not result["ok"]:
            raise ValueError(result["detail"])


class IsolatedCodexAdapter(CodexAdapter):
    def __init__(
        self,
        sandbox: Sandbox,
        *,
        metadata: list[Path] = (),
        timeout: float = 300,
        instructions: Path | None = None,
        model: str | None = None,
    ):
        super().__init__(timeout=timeout, model=model)
        self.sandbox = sandbox
        self.metadata = metadata
        self.instructions = instructions

    def arguments(self, workspace: Path) -> list[str]:
        arguments = super().arguments(workspace)
        arguments.insert(-1, "--skip-git-repo-check")
        return self.sandbox.command(
            workspace,
            arguments,
            metadata=self.metadata,
            authenticated=True,
            writable_git=False,
            instructions=self.instructions,
        )

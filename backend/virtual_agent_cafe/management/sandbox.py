"""Linux mount/PID namespaces: expose runtime libraries and one approved work tree."""

import asyncio
import os
import shutil
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

    async def validate(self, workspace: Path):
        process = await asyncio.create_subprocess_exec(
            *self.command(workspace, ["/usr/bin/true"], network=False),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(5):
                code = await process.wait()
            if code:
                raise ValueError("Filesystem isolation unavailable; check user/mount namespaces")
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()


class IsolatedCodexAdapter(CodexAdapter):
    def __init__(
        self,
        sandbox: Sandbox,
        *,
        metadata: list[Path] = (),
        timeout: float = 300,
        instructions: Path | None = None,
    ):
        super().__init__(timeout=timeout)
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

import asyncio
import os
import re
from pathlib import Path

from .files import WorkspaceManager
from .sandbox import Sandbox


class GitService:
    """Typed operations only. No shell, aliases, hooks, forced updates or automatic merge."""

    def __init__(self, workspaces: WorkspaceManager):
        self.workspaces = workspaces
        self.locks: dict[str, asyncio.Lock] = {}

    def metadata(self, path: Path) -> list[Path]:
        git = path / ".git"
        if git.is_symlink():
            raise ValueError("Git metadata symlinks are not approved")
        if git.is_file():
            if git.stat().st_size > 4096:
                raise ValueError("Invalid worktree metadata")
            value = git.read_text().strip()
            if not value.startswith("gitdir: "):
                raise ValueError("Invalid worktree metadata")
            directory = (path / value[8:]).resolve()
            if not directory.is_relative_to(self.workspaces.files.root):
                raise ValueError("Worktree metadata outside approved roots")
            common_file = directory / "commondir"
            common = (directory / common_file.read_text().strip()).resolve()
            if not common.is_relative_to(self.workspaces.files.root):
                raise ValueError("Common metadata outside approved roots")
            return [common]
        return []

    async def run(self, path: Path, *arguments: str, extra_mounts: tuple[Path, ...] = ()) -> str:
        path = await asyncio.to_thread(path.resolve)
        if not path.is_relative_to(self.workspaces.files.root):
            raise ValueError("Git path is outside approved workspaces")
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": str(Path.home()),
            "LANG": "C.UTF-8",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_SSH_COMMAND": "ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "
            "-o UserKnownHostsFile=/home/agent/.ssh/known_hosts",
        }
        if os.getenv("SSH_AUTH_SOCK"):
            env["SSH_AUTH_SOCK"] = os.environ["SSH_AUTH_SOCK"]
        command = [
            "git",
            "-c",
            f"safe.directory={path}",
            "-c",
            "core.sshCommand=ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "
            "-o UserKnownHostsFile=/home/agent/.ssh/known_hosts",
            "-c",
            "credential.helper=",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "protocol.file.allow=never",
            "-c",
            "protocol.ext.allow=never",
            "-c",
            "user.name=VirtualAgentCafe",
            "-c",
            "user.email=agent@localhost",
            "-C",
            str(path),
            *arguments,
        ]
        sandbox = Sandbox()
        isolated = sandbox.command(
            path,
            command,
            metadata=[*self.metadata(path), *extra_mounts],
            ssh=arguments[:1] in [("clone",), ("fetch",), ("pull",), ("push",), ("ls-remote",)],
        )
        process = await asyncio.create_subprocess_exec(
            *isolated,
            env=env,
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            async with asyncio.timeout(30):
                output = bytearray()
                while chunk := await process.stdout.read(65536):
                    output.extend(chunk)
                    if len(output) > 1024 * 1024:
                        raise ValueError("Git output exceeds 1 MiB; narrow the requested diff")
                if await process.wait():
                    raise ValueError(
                        "Git operation failed; check repository, branch and permissions"
                    )
                return output.decode("utf-8", errors="replace")
        finally:
            import signal

            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    @staticmethod
    def branch_name(name: str) -> str:
        if (
            not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9/_-]{0,159}", name)
            or "//" in name
            or name.endswith("/")
        ):
            raise ValueError("Invalid branch name")
        return name

    async def repository(self, identifier: str) -> Path:
        path = self.workspaces.get(identifier)
        # A connected repository must have its metadata under approved workspace roots.
        metadata = Path((await self.run(path, "rev-parse", "--absolute-git-dir")).strip())
        if not (await asyncio.to_thread(metadata.resolve)).is_relative_to(
            self.workspaces.files.root
        ):
            raise ValueError("Repository metadata is outside approved workspaces")
        if await asyncio.to_thread(metadata.is_symlink):
            raise ValueError("Repository metadata symlinks are not approved")
        return path

    async def init(self, identifier: str) -> dict:
        path = self.workspaces.get(identifier)
        await self.run(path, "init", "-q", "--initial-branch=main")
        return await self.info(identifier)

    async def clone(self, identifier: str, remote: str) -> dict:
        # SSH/SCP and HTTPS only. Reject credential URLs, options and local host paths.
        if not (
            re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+", remote)
            or re.fullmatch(r"https://[A-Za-z0-9.-]+/[A-Za-z0-9_./-]+", remote)
        ):
            raise ValueError("Use an SSH or credential-free HTTPS repository URL")
        path = self.workspaces.get(identifier)
        if any(path.iterdir()):
            raise ValueError("Clone destination must be empty")
        await self.run(path, "clone", "--", remote, ".")
        return await self.info(identifier)

    async def set_remote(self, identifier: str, name: str, url: str) -> dict:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", name):
            raise ValueError("Invalid remote name")
        if not (
            re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+", url)
            or re.fullmatch(r"https://[A-Za-z0-9.-]+/[A-Za-z0-9_./-]+", url)
        ):
            raise ValueError("Use an SSH or credential-free HTTPS repository URL")
        path = await self.repository(identifier)
        names = (await self.run(path, "remote")).splitlines()
        await self.run(path, "remote", "set-url" if name in names else "add", name, url)
        return await self.info(identifier)

    async def info(self, identifier: str) -> dict:
        path = await self.repository(identifier)
        branch = (await self.run(path, "symbolic-ref", "--short", "HEAD")).strip()
        status = await self.run(path, "status", "--porcelain=v1", "--untracked-files=normal")
        try:
            history = await self.run(path, "log", "-20", "--format=%h %s")
        except ValueError:
            history = ""
        remotes = await self.run(path, "remote")
        return {
            "remotes": remotes.splitlines(),
            "workspace": identifier,
            "repository": str(path),
            "branch": branch,
            "modified_files": status.splitlines(),
            "history": history.splitlines(),
        }

    async def diff(self, identifier: str) -> str:
        path = await self.repository(identifier)
        return await self.run(path, "diff", "--no-ext-diff", "--no-textconv", "HEAD")

    async def branch(self, identifier: str, branch: str, create: bool = True):
        path = await self.repository(identifier)
        name = self.branch_name(branch)
        await self.run(path, "switch", *(["-c"] if create else []), name)
        return await self.info(identifier)

    def validate_files(self, path: Path, files: list[str]):
        for filename in files:
            if not filename or filename.startswith(":") or len(filename) > 512:
                raise ValueError("Invalid file path")
            if (
                any(part in {".git", ".cafe", ".ssh", ".codex"} for part in Path(filename).parts)
                or Path(filename).name.startswith(".env")
                or Path(filename).suffix.lower() in {".pem", ".key"}
                or Path(filename).name.startswith("id_ed25519")
                or Path(filename).name.startswith("id_rsa")
            ):
                raise ValueError("Credential and runtime files cannot be staged")
            target = self.workspaces.files.path(
                str(path.relative_to(self.workspaces.files.root) / filename)
            )
            if target.is_dir():
                raise ValueError("Stage individual files, not directories")
            if not target.resolve().is_relative_to(path) or ".git" in Path(filename).parts:
                raise ValueError("Invalid file path")

    async def stage(self, identifier: str, files: list[str]):
        path = await self.repository(identifier)
        if not files or len(files) > 100:
            raise ValueError("Choose 1–100 files")
        self.validate_files(path, files)
        await self.run(path, "--literal-pathspecs", "add", "--", *files)
        return await self.info(identifier)

    async def commit(self, identifier: str, message: str):
        if not message.strip() or len(message) > 256:
            raise ValueError("Commit message must be 1–256 characters")
        path = await self.repository(identifier)
        staged = await self.run(path, "diff", "--cached", "--name-only", "-z")
        self.validate_files(path, [name for name in staged.split("\0") if name])
        await self.run(path, "commit", "-m", message)
        return await self.info(identifier)

    async def worktree(self, repository: str, destination: str, branch: str) -> Path:
        path = await self.repository(repository)
        target = self.workspaces.get(destination)
        name = self.branch_name(branch)
        async with self.locks.setdefault(repository, asyncio.Lock()):
            if (target / ".git").exists():
                actual = await self.repository(destination)
                common = (await self.run(actual, "rev-parse", "--git-common-dir")).strip()
                if (actual / common).resolve() != (path / ".git").resolve():
                    raise ValueError("Workspace is connected to a different repository")
                if (await self.info(destination))["branch"] != name:
                    raise ValueError("Existing workspace has a different branch")
                return target
            if any(target.iterdir()):
                raise ValueError("Worktree destination must be empty")
            # Require one reviewed initial commit; never manufacture a commit on main.
            await self.run(path, "rev-parse", "--verify", "HEAD")
            references = await self.run(path, "for-each-ref", "--format=%(refname)", "refs/heads/")
            flags = [] if f"refs/heads/{name}" in references.splitlines() else ["-b", name]
            await self.run(
                path,
                "worktree",
                "add",
                *flags,
                str(target),
                *([name] if not flags else []),
                extra_mounts=(target,),
            )
            return target

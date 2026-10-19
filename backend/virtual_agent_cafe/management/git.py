import asyncio
import os
import re
import shutil
from pathlib import Path

from .files import WorkspaceManager
from .sandbox import Sandbox


class GitOperationError(ValueError):
    """A sanitized failure of an approved Git subprocess."""


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
        operation = self.operation(arguments)
        sandbox = Sandbox()
        isolated = sandbox.command(
            path,
            command,
            metadata=[*self.metadata(path), *extra_mounts],
            ssh=operation in {"clone", "fetch", "pull", "push", "ls-remote"},
        )
        process = await asyncio.create_subprocess_exec(
            *isolated,
            env=env,
            start_new_session=True,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            async with asyncio.timeout(30):

                async def bounded_read(stream, limit):
                    output = bytearray()
                    while chunk := await stream.read(65536):
                        output.extend(chunk)
                        if len(output) > limit:
                            raise ValueError("Git output exceeds limit; narrow the requested diff")
                    return bytes(output)

                output, errors = await asyncio.gather(
                    bounded_read(process.stdout, 1024 * 1024),
                    bounded_read(process.stderr, 65536),
                )
                if await process.wait():
                    raise GitOperationError(
                        self.failure(operation, errors.decode("utf-8", errors="replace"))
                    )
                return output.decode("utf-8", errors="replace")
        except TimeoutError:
            raise GitOperationError(
                "Git command timed out. Check repository and remote access."
            ) from None
        finally:
            import signal

            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            await process.wait()

    @staticmethod
    def operation(arguments: tuple[str, ...]) -> str:
        index = 0
        while index < len(arguments):
            if arguments[index] == "-c":
                index += 2
            elif arguments[index] == "--literal-pathspecs":
                index += 1
            else:
                return arguments[index]
        return "command"

    @staticmethod
    def failure(operation: str, stderr: str) -> str:
        # Classify stderr; never expose Git output containing remote URLs or credentials.
        text = stderr.lower()
        if "publickey" in text or "authentication failed" in text:
            return f"Git {operation} failed. Remote authentication failed. " + (
                "Check SSH-agent forwarding and repository access."
            )
        if "no user exists for uid" in text:
            return (
                f"Git {operation} failed. SSH cannot resolve the sandbox user. "
                "Update and restart the backend to mount read-only account metadata."
            )
        reason = "Check repository metadata, branch and filesystem permissions."
        for fragments, advice in (
            (
                ("protected branch", "gh006", "gh013", "repository rule"),
                "Remote branch protection rejected the update. Main remains unchanged; "
                "use an allowed pull-request workflow or repository permission policy.",
            ),
            (
                (
                    "conflict (",
                    "automatic merge failed",
                    "unmerged files",
                    "refusing to merge unrelated histories",
                ),
                "Integration has merge conflicts or unrelated history. "
                "Existing worktrees are preserved; main was not changed.",
            ),
            (
                ("non-fast-forward", "fetch first", "[rejected]"),
                "Remote branch has other changes or rejected the update. "
                "Review and integrate changes explicitly; force-push is disabled.",
            ),
            (
                ("already checked out", "already used by worktree"),
                "Branch is already assigned to another worktree. Select a different "
                "branch; existing files are preserved.",
            ),
            (
                (
                    "could not create leading directories",
                    "permission denied",
                    "read-only file system",
                ),
                "Workspace or Git metadata is not writable. Check the mounted folder's "
                "user permissions.",
            ),
            (
                ("index.lock", "cannot lock ref", "unable to create", "already exists"),
                "Git lock or destination conflict. Check other Git processes and "
                "existing branches/worktrees; no files were removed.",
            ),
            (
                ("dubious ownership",),
                "Git rejected repository ownership. Check the approved workspace mount.",
            ),
            (
                ("not a git repository", "invalid gitfile"),
                "Repository/worktree metadata is missing or refers to an unavailable "
                "path. Check the project mount.",
            ),
            (
                ("bad object", "invalid reference", "ambiguous argument"),
                "Requested commit or branch is unavailable. Check the initial commit and "
                "selected branch.",
            ),
            (
                ("host key verification failed",),
                "SSH host verification failed. Configure trusted known_hosts in the backend.",
            ),
        ):
            if any(fragment in text for fragment in fragments):
                reason = advice
                break
        return f"Git {operation} failed. {reason}"

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
        if not (path / ".git").exists():
            raise ValueError(
                "Selected workspace has no Git repository. Select the current agent worktree "
                "in Workspaces; an old project mount may no longer be connected."
            )
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

    async def push_target(self, config) -> tuple[Path, str]:
        if (
            not config.git.enabled
            or not config.git.allow_push
            or os.getenv("VAC_ALLOW_REMOTE_GIT") != "1"
        ):
            raise ValueError(
                "Publishing requires controller remote Git opt-in and agent push permission"
            )
        path = await self.repository(config.workspace)
        branch = (await self.info(config.workspace))["branch"]
        if not branch.startswith(f"agent/{config.id}/"):
            raise ValueError("Publishing is restricted to this agent's own branch namespace")
        self.branch_name(branch)
        urls = (
            await self.run(path, "remote", "get-url", "--push", "--all", config.git.remote_name)
        ).splitlines()
        if len(urls) != 1 or not (
            re.fullmatch(r"git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+", urls[0])
            or re.fullmatch(r"https://[A-Za-z0-9.-]+/[A-Za-z0-9_./-]+", urls[0])
        ):
            raise ValueError("Publishing requires one SSH or credential-free HTTPS push URL")
        return path, branch

    async def push(self, config) -> dict:
        path, branch = await self.push_target(config)
        # Runtime helper/instruction files are not project results. Everything else
        # must have been deliberately committed by the worker before publication.
        dirty = await self.run(
            path, "status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude).cafe"
        )
        if dirty.strip():
            raise ValueError(
                "Results are not fully committed. Review and commit project files before publishing"
            )
        commit = (await self.run(path, "rev-parse", "HEAD")).strip()
        await self.run(
            path,
            "-c",
            f"remote.{config.git.remote_name}.mirror=false",
            "-c",
            "push.followTags=false",
            "push",
            "--porcelain",
            "--no-follow-tags",
            "--recurse-submodules=no",
            "--set-upstream",
            "--",
            config.git.remote_name,
            f"HEAD:refs/heads/{branch}",
        )
        return {"branch": branch, "commit": commit, "remote": config.git.remote_name}

    async def require_clean(self, path: Path):
        dirty = await self.run(
            path, "status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude).cafe"
        )
        if dirty.strip():
            raise ValueError("Commit or resolve integration changes before continuing")

    async def fetch_main(self, config) -> str:
        path, _branch = await self.push_target(config)
        await self.run(
            path,
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            "--",
            config.git.remote_name,
            "refs/heads/main",
        )
        return (await self.run(path, "rev-parse", "FETCH_HEAD")).strip()

    async def merge_commit(self, workspace: str, commit: str):
        if not re.fullmatch(r"[a-f0-9]{40,64}", commit):
            raise ValueError("Integration requires an exact published commit")
        path = await self.repository(workspace)
        try:
            await self.run(path, "merge-base", "--is-ancestor", commit, "HEAD")
            return
        except GitOperationError:
            pass
        await self.require_clean(path)
        await self.run(path, "merge", "--no-ff", "--no-edit", "--no-verify", commit)

    async def promote(self, config, commit: str, base: str) -> dict:
        path, branch = await self.push_target(config)
        if not config.execution.integration_validation or not re.fullmatch(
            r"[a-f0-9]{40,64}", commit
        ):
            raise ValueError("Main promotion requires a tested integration commit")
        await self.require_clean(path)
        if (await self.run(path, "rev-parse", "HEAD")).strip() != commit:
            raise ValueError("Integration commit changed after tests")
        remote = await self.run(path, "ls-remote", "--", config.git.remote_name, "refs/heads/main")
        if not remote.split() or remote.split()[0] != base:
            raise ValueError("Remote main changed; merge its latest commit and rerun shared tests")
        await self.run(path, "merge-base", "--is-ancestor", base, commit)
        await self.run(
            path,
            "-c",
            f"remote.{config.git.remote_name}.mirror=false",
            "-c",
            "push.followTags=false",
            "push",
            "--porcelain",
            "--no-follow-tags",
            "--recurse-submodules=no",
            "--",
            config.git.remote_name,
            f"{commit}:refs/heads/main",
        )
        return {
            "branch": "main",
            "commit": commit,
            "remote": config.git.remote_name,
            "feature_branch": branch,
        }

    async def remove_worktree(self, repository: str, destination: str) -> None:
        source = await self.repository(repository)
        target = self.workspaces.get(destination)
        if not (target / ".git").exists():
            if target.is_dir() and not any(target.iterdir()):
                await asyncio.to_thread(target.rmdir)
                return
            raise ValueError("Managed workspace is not a removable Git worktree")
        actual = await self.repository(destination)
        common = Path(
            (
                await self.run(actual, "rev-parse", "--path-format=absolute", "--git-common-dir")
            ).strip()
        )
        if not (await asyncio.to_thread((actual / common).resolve)).is_relative_to(
            self.workspaces.files.root
        ):
            raise ValueError("Worktree metadata is outside approved workspace roots")
        common = (actual / common).resolve()
        source_common = Path(
            (
                await self.run(source, "rev-parse", "--path-format=absolute", "--git-common-dir")
            ).strip()
        )
        if (source / source_common).resolve() != common:
            raise ValueError("Workspace belongs to a different Git repository")
        await self.require_clean(actual)
        # Git cannot unlink a worktree that bubblewrap mounted as its own mount point.
        # After clean-state and same-repository checks, remove this approved tree and
        # prune its now-stale administrative entry. Branch references remain intact.
        if target.resolve() != target or not target.resolve().is_relative_to(
            self.workspaces.files.root
        ):
            raise ValueError("Worktree path is outside approved workspace roots")
        await asyncio.to_thread(shutil.rmtree, target)

    async def prune_worktrees(self, repository: str) -> None:
        """Prune stale metadata once after a group of managed worktrees is removed."""
        source = await self.repository(repository)
        await self.run(source, "worktree", "prune", "--expire", "now")

    async def worktree(self, repository: str, destination: str, branch: str) -> Path:
        path = await self.repository(repository)
        target = self.workspaces.get(destination)
        name = self.branch_name(branch)
        async with self.locks.setdefault(repository, asyncio.Lock()):
            if (target / ".git").exists():
                actual = await self.repository(destination)
                common = (
                    await self.run(
                        actual, "rev-parse", "--path-format=absolute", "--git-common-dir"
                    )
                ).strip()
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

"""Answer questions in a disposable runtime with a read-only project mount."""

from pathlib import Path

from ..adapters.codex import CodexAdapter
from .sandbox import Sandbox


def question_command(
    sandbox: Sandbox, scratch: Path, project: Path, command: list[str], *, authenticated=False
):
    args = sandbox.command(scratch, command, authenticated=authenticated, writable_git=False)
    mounts = ["--ro-bind", str(project), "/project"]
    # Never expose the work execution's Git RPC socket/token or writable Git metadata.
    for name in (".cafe", ".git"):
        path = project / name
        if path.exists() or path.is_symlink():
            mounts += (
                ["--tmpfs", f"/project/{name}"]
                if path.is_dir()
                else ["--ro-bind", "/dev/null", f"/project/{name}"]
            )
    offset = args.index("--chdir")
    return [*args[:offset], *mounts, *args[offset:]]


class QuestionAdapter(CodexAdapter):
    def __init__(
        self, sandbox: Sandbox, project: Path, *, model=None, timeout=300, executable=None
    ):
        super().__init__(executable=executable, model=model, timeout=timeout)
        self.sandbox, self.project = sandbox, project

    def arguments(self, workspace: Path) -> list[str]:
        command = super().arguments(workspace)
        command.insert(-1, "--skip-git-repo-check")
        return question_command(self.sandbox, workspace, self.project, command, authenticated=True)

"""Private, execution-scoped file RPC; no controller token or remote credentials."""

import asyncio
import json
from pathlib import Path
from uuid import UUID

from .files import ApprovedFiles

HELPER = """#!/usr/bin/env python3
import argparse, json, time
from pathlib import Path
from uuid import uuid4
parser = argparse.ArgumentParser(description="Git operations in this assigned workspace")
parser.add_argument("operation",
    choices=["status", "history", "diff", "stage", "commit", "branch", "switch"])
parser.add_argument("arguments", nargs="*")
args = parser.parse_args()
root = Path(__file__).resolve().parent
identifier = str(uuid4())
request = root / "git-requests" / RUN_ID / (identifier + ".json")
response = root / "git-responses" / RUN_ID / (identifier + ".json")
for path in (request, response):
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        parser.error("Invalid helper path")
request.write_text(json.dumps(
    {"run": RUN_ID, "operation": args.operation, "arguments": args.arguments}))
for attempt in range(600):
    if response.is_file():
        result = json.loads(response.read_text())
        print(result.get("result", result.get("error", "Git failed")))
        raise SystemExit(0 if result.get("ok") else 1)
    time.sleep(0.1)
parser.error("Git controller timed out")
"""


def prepare(workspace: Path, run_id: str):
    files = ApprovedFiles(workspace)
    for name in [f".cafe/git-requests/{run_id}", f".cafe/git-responses/{run_id}"]:
        files.path(name).mkdir(parents=True, exist_ok=True)
    files.path(".cafe/git.py").write_text(f"RUN_ID = {run_id!r}\n" + HELPER)


async def watch(manager, config, run: dict, workspace: Path):
    files = ApprovedFiles(workspace)
    seen = set()
    request_dir = f".cafe/git-requests/{run['id']}"
    response_dir = f".cafe/git-responses/{run['id']}"
    while True:
        for path in sorted(files.path(request_dir).glob("*.json"))[:100]:
            if path.name in seen:
                continue
            seen.add(path.name)
            try:
                UUID(path.stem)
                path = files.path(request_dir + "/" + path.name)
                if path.stat().st_size > 8192 or len(seen) > 100:
                    raise ValueError("Git request limit exceeded")
                data = json.loads(path.read_text())
                if data.get("run") != run["id"] or not config.git.enabled:
                    raise ValueError("Git request is not authorized")
                operation, arguments = data.get("operation"), data.get("arguments")
                if not isinstance(arguments, list) or any(
                    not isinstance(v, str) for v in arguments
                ):
                    raise ValueError("Invalid arguments")
                git = manager.git
                if operation in {"status", "history"} and not arguments:
                    result = await git.info(config.workspace)
                elif operation == "diff" and not arguments:
                    result = await git.diff(config.workspace)
                elif operation == "stage":
                    result = await git.stage(config.workspace, arguments)
                elif operation == "commit" and len(arguments) == 1:
                    result = await git.commit(config.workspace, arguments[0])
                elif operation in {"branch", "switch"} and len(arguments) == 1:
                    if not arguments[0].startswith(f"agent/{config.id}/"):
                        raise ValueError("Choose this agent's own branch namespace")
                    result = await git.branch(config.workspace, arguments[0], operation == "branch")
                else:
                    raise ValueError("Operation is not authorized")
                response = {"ok": True, "result": result}
                from ..models import EventType

                manager.emit(
                    run,
                    EventType.CODING if operation in {"stage", "commit"} else EventType.WAITING,
                    f"Git: {operation} completed",
                )
            except (ValueError, OSError, KeyError):
                response = {"ok": False, "error": "Git request rejected or failed"}
            try:
                files.path(response_dir + "/" + path.name).write_text(json.dumps(response))
            except (ValueError, OSError):
                pass
        await asyncio.sleep(0.1)

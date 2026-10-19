#!/usr/bin/env python3
"""Run the exact managed-agent namespace self-test, without model calls or credentials."""

import argparse
import asyncio
import json
import os
import tempfile
from pathlib import Path

from virtual_agent_cafe.management.sandbox import Sandbox


def namespace_settings():
    result = {}
    for name in (
        "kernel/unprivileged_userns_clone",
        "user/max_user_namespaces",
        "kernel/apparmor_restrict_unprivileged_userns",
    ):
        path = Path("/proc/sys") / name
        try:
            value = path.read_text().strip()
            if value.isdecimal():
                result[name] = int(value)
        except OSError:
            pass
    return result


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", help="Existing project directory inside the backend")
    args = parser.parse_args()
    try:
        if args.workspace:
            workspace = await asyncio.to_thread(Path(args.workspace).resolve, strict=True)
            if not workspace.is_dir():
                raise ValueError("Workspace is not a directory")
            report = await Sandbox().probe(workspace)
        else:
            with tempfile.TemporaryDirectory(dir=os.getenv("VAC_WORKSPACE_ROOT")) as directory:
                report = await Sandbox().probe(Path(directory))
    except (OSError, ValueError):
        report = {
            "ok": False,
            "code": "workspace_unavailable",
            "detail": "Diagnostic workspace unavailable. Check workspace mount and permissions.",
        }
    report["namespace_settings"] = namespace_settings()
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""Namespace-confined CLI fixture; no external model calls."""

import asyncio
import os
from pathlib import Path

from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.sandbox import IsolatedCodexAdapter, Sandbox

PROGRAM = """
import json, sys, time
from pathlib import Path
prompt = sys.stdin.read()
workspace = Path(sys.argv[1])
def send(data):
    print(json.dumps(data), flush=True)
send({'type': 'turn.started'})
if 'fixture: wait' in prompt:
    time.sleep(60)
assert 'ROLE backend.md' in prompt
assert 'TASK task.md' in prompt
(workspace / 'managed-result.txt').write_text('roles and Markdown task received')
send({'type': 'item.completed', 'item': {'type': 'file_change', 'status': 'completed'}})
send({'type': 'item.started', 'item': {'type': 'command_execution', 'command': 'pytest -q'}})
send({'type': 'item.completed', 'item': {'type': 'command_execution',
      'command': 'pytest -q', 'exit_code': 0}})
send({'type': 'turn.completed'})
"""


class FixtureRuntime(IsolatedCodexAdapter):
    def arguments(self, workspace):
        return self.sandbox.command(
            workspace, ["/usr/bin/python3", "-c", PROGRAM, str(workspace)], writable_git=False
        )


app = create_app(
    "codex",
    workspace_root=Path(os.environ["VAC_FIXTURE_ROOT"]) / "legacy",
    management_root=Path(os.environ["VAC_FIXTURE_ROOT"]) / "management",
    managed_adapter=FixtureRuntime(Sandbox(), timeout=10),
)


@app.middleware("http")
async def delay_overview_for_gui_race(request, call_next):
    if request.url.path == "/management" or request.method in {"POST", "PUT"}:
        await asyncio.sleep(float(os.getenv("VAC_GUI_DELAY", "0")))
    return await call_next(request)

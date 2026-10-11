"""Only used by integration tests; never selected by the production server."""

import os
from pathlib import Path

from virtual_agent_cafe.adapters.codex import CodexAdapter
from virtual_agent_cafe.main import create_app

app = create_app(
    mode="codex",
    adapter=CodexAdapter(os.environ["VAC_FIXTURE_CLI"], timeout=10),
    workspace_root=Path(os.environ["VAC_FIXTURE_ROOT"]),
)

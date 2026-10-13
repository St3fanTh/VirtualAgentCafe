import json

import pytest
from pydantic import ValidationError

from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.files import ApprovedFiles, MarkdownManager, WorkspaceManager
from virtual_agent_cafe.management.registry import AgentRegistry
from virtual_agent_cafe.management.storage import Store


def managers(root):
    store = Store(root)
    tasks = MarkdownManager(root / "tasks", "tasks", store)
    roles = MarkdownManager(root / "roles", "roles", store)
    workspaces = WorkspaceManager(root / "workspaces", store)
    registry = AgentRegistry(store, ApprovedFiles(root / "agents"), tasks, roles, workspaces)
    return store, tasks, roles, workspaces, registry


def test_markdown_is_source_of_truth_and_config_survives_restart(tmp_path):
    store, tasks, roles, workspaces, registry = managers(tmp_path)
    tasks.save("login.md", "# Login\nImplement login.")
    roles.save("backend.md", "# Backend\nWrite tests.")
    workspaces.create("project")
    config = AgentConfig(
        id="backend-agent",
        name="Backend",
        workspace="project",
        task="login.md",
        roles=["backend.md"],
    )
    registry.save(config)
    tasks.files.path("login.md").write_text("# Login\nUpdated requirements.")
    assert tasks.load("login.md")["content"].endswith("Updated requirements.")
    restarted = managers(tmp_path)
    assert restarted[4].get(config.id)["config"] == config.model_dump(mode="json")
    assert json.loads((tmp_path / "agents/backend-agent.json").read_text())["task"] == "login.md"
    registry.update(config.id, state="RUNNING")
    with pytest.raises(ValueError, match="Stop"):
        registry.save(config)
    store.log("run1", {"detail": "Testing"})
    assert restarted[0].logs("run1")[0]["detail"] == "Testing"


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "../escape"},
        {"id": "ada"},
        {"workspace": "/etc"},
        {"task": "../secrets.md"},
        {"roles": ["backend.md", "backend.md"]},
        {"execution": {"timeout_seconds": 0}},
        {"provider": "shell"},
        {"git": {"enabled": True}},
        {"git": {"auto_commit": True}},
    ],
)
def test_invalid_configuration(changes):
    with pytest.raises(ValidationError):
        AgentConfig.model_validate(
            {"id": "agent", "name": "Agent", "workspace": "project", **changes}
        )


def test_workspace_and_markdown_escape_rejected(tmp_path):
    _, tasks, _, workspaces, registry = managers(tmp_path / "approved")
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspaces.files.root / "escape").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        workspaces.create("escape")
    tasks.files.path("escape.md").symlink_to(outside / "secret.md")
    with pytest.raises(ValueError):
        tasks.save("escape.md", "# Instructions")
    with pytest.raises(KeyError):
        registry.save(AgentConfig(id="agent", name="Agent", workspace="unknown"))
    with pytest.raises(ValueError):
        tasks.save("empty.md", "not markdown instructions")

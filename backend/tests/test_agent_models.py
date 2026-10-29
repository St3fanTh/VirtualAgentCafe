import asyncio

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_management_execution import ControlledRuntime, completed, configured

from virtual_agent_cafe.adapters.codex import CodexAdapter
from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.execution import ExecutionManager
from virtual_agent_cafe.management.model_catalog import ModelCatalog
from virtual_agent_cafe.management.sandbox import IsolatedCodexAdapter, Sandbox


@pytest.mark.parametrize("model", ["--help", "x y", "x\ny", "$(id)", "", "x" * 129])
def test_model_config_rejects_invalid_identifiers(model):
    with pytest.raises(ValidationError):
        AgentConfig(id="agent", name="Agent", workspace="project", model=model)


def test_model_override_reaches_both_cli_and_confined_command(tmp_path):
    default = CodexAdapter().arguments(tmp_path)
    assert "--model" not in default
    for adapter in (
        CodexAdapter(model="example-model"),
        IsolatedCodexAdapter(Sandbox(), model="example-model"),
    ):
        arguments = adapter.arguments(tmp_path)
        assert arguments[arguments.index("--model") + 1] == "example-model"
        assert "--ignore-user-config" in arguments


async def test_saved_model_passed_to_runtime_and_snapshotted_per_execution(tmp_path, monkeypatch):
    seen = []

    class Runtime(ControlledRuntime):
        def __init__(self, *args, model=None, **kwargs):
            super().__init__()
            seen.append(model)
            self.release.set()

    monkeypatch.setattr("virtual_agent_cafe.management.execution.IsolatedCodexAdapter", Runtime)
    manager = configured(tmp_path, None)
    config = AgentConfig.model_validate(manager.registry.get("backend-agent")["config"])
    assert config.model is None
    config.model = "example-model"
    manager.configure(config)
    restored = ExecutionManager(tmp_path, EventBus())
    assert restored.registry.get("backend-agent")["config"]["model"] == "example-model"
    run = await restored.start("backend-agent")
    await completed(restored)
    assert seen == ["example-model"]
    assert restored.store.get("executions", run["id"])["model"] == "example-model"
    config.model = "different-model"
    restored.configure(config)
    assert restored.store.get("executions", run["id"])["model"] == "example-model"


async def test_catalog_filters_private_fields_and_caches_concurrent_requests(monkeypatch):
    calls = []

    async def query(bundled=False):
        calls.append(bundled)
        await asyncio.sleep(0)
        return {
            "models": [
                {"slug": "example-model", "visibility": "list", "instructions": "PRIVATE"},
                {"slug": "hidden-model", "visibility": "hide"},
                {"slug": "--invalid", "visibility": "list"},
                {"slug": "example-model", "visibility": "list"},
            ]
        }

    monkeypatch.setattr(ModelCatalog, "query", staticmethod(query))
    catalog = ModelCatalog()
    first, second = await asyncio.gather(catalog.get(), catalog.get())
    assert first == second
    assert first["models"] == ["example-model"]
    assert "PRIVATE" not in str(first)
    assert calls == [False]
    await catalog.get(refresh=True)
    assert calls == [False, False]


async def test_catalog_falls_back_then_explains_unavailable(monkeypatch):
    async def query(bundled=False):
        if not bundled:
            raise TimeoutError()
        return {"models": [{"slug": "example-model", "visibility": "list"}]}

    monkeypatch.setattr(ModelCatalog, "query", staticmethod(query))
    assert (await ModelCatalog().get())["source"] == "bundled"

    async def broken(bundled=False):
        raise ValueError("PRIVATE ERROR OUTPUT")

    monkeypatch.setattr(ModelCatalog, "query", staticmethod(broken))
    result = await ModelCatalog().get()
    assert result["source"] == "unavailable" and result["models"] == []
    assert "PRIVATE" not in str(result)


def test_model_catalog_endpoint_requires_auth(tmp_path, monkeypatch):
    async def query(bundled=False):
        return {"models": [{"slug": "example-model", "visibility": "list"}]}

    monkeypatch.setattr(ModelCatalog, "query", staticmethod(query))
    app = create_app("codex", management_root=tmp_path)
    with TestClient(app) as client:
        assert client.get("/management/models").status_code == 401
        client.headers["Authorization"] = "Bearer " + app.state.management.access.token
        assert client.get("/management/models").json()["models"] == ["example-model"]


async def test_model_query_parses_cli_output_without_exposing_stderr(tmp_path, monkeypatch):
    cli = tmp_path / "codex"
    cli.write_text("#!/bin/sh\necho private-diagnostic >&2\necho '{\"models\": []}'\n")
    cli.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert await ModelCatalog.query(True) == {"models": []}


async def test_model_query_rejects_excessive_output(tmp_path, monkeypatch):
    cli = tmp_path / "codex"
    cli.write_text("#!/usr/bin/python3\nimport sys\nsys.stdout.write('x' * (3 * 1024 * 1024))\n")
    cli.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(ValueError, match="exceeds limit"):
        await ModelCatalog.query(True)

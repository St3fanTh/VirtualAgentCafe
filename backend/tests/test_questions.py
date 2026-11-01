import asyncio

import pytest
from fastapi.testclient import TestClient
from test_management_execution import ControlledRuntime, completed, configured
from test_team_integration import settle, start_workers, team

from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.questions import QuestionAdapter


class IsolatedFixtureQuestion(QuestionAdapter):
    async def run(self, prompt, workspace, emit):
        script = workspace / "fake-codex"
        script.write_text("""#!/usr/bin/python3
import json, sys
from pathlib import Path
prompt = sys.stdin.read()
assert "Answer the user's question only" in prompt
project = Path('/project')
assert (project / 'question-evidence.txt').read_text() == 'existing source'
assert not (project / '.cafe/secret-token').exists()
assert not (project / '.git/config').exists()
try:
    (project / 'question-evidence.txt').write_text('changed')
except OSError:
    pass
else:
    raise AssertionError('project must be read-only')
output = Path(sys.argv[sys.argv.index('--output-last-message') + 1])
output.write_text('The script is question-evidence.txt. No project files changed.')
print(json.dumps({'type': 'turn.started'}))
print(json.dumps({'type': 'turn.completed'}))
""")
        script.chmod(0o755)
        self.executable = str(script)
        if self.model:
            assert self.model in self.arguments(workspace)
        return await super().run(prompt, workspace, emit)


def prepare_question(manager, identifier):
    path = manager.workspaces.get(manager.registry.get(identifier)["config"]["workspace"])
    (path / "question-evidence.txt").write_text("existing source")
    (path / ".cafe").mkdir(exist_ok=True)
    (path / ".cafe/secret-token").write_text("must not be exposed")
    return path


async def wait_for_answer(manager):
    await asyncio.gather(*list(manager.conversations.running.values()))
    await asyncio.sleep(0)


async def test_question_reads_project_without_new_execution_or_instruction_leak(
    tmp_path, monkeypatch
):
    manager = configured(tmp_path, ControlledRuntime())
    monkeypatch.setattr(
        "virtual_agent_cafe.management.conversations.QuestionAdapter", IsolatedFixtureQuestion
    )
    try:
        config = AgentConfig.model_validate(manager.registry.get("backend-agent")["config"])
        config.model = "fixture-question-model"
        manager.configure(config)
        path = prepare_question(manager, "backend-agent")
        before = manager.registry.get("backend-agent")
        events = manager.bus.sequence
        result = await manager.conversations.ask("backend-agent", "Where is the script? PRIVATE")
        assert result["delivery"] == "ANSWERING"
        with pytest.raises(ValueError, match="current answer"):
            await manager.conversations.ask("backend-agent", "Duplicate question")
        await wait_for_answer(manager)
        history = manager.conversations.read("backend-agent")
        assert history["question"]["status"] == "COMPLETED", history
        assert "question-evidence.txt" in history["messages"][-1]["content"]
        assert manager.registry.get("backend-agent") == before
        assert manager.bus.sequence == events
        assert not manager.store.list("executions")
        assert manager.conversations.context("backend-agent") == ""
        assert (path / "question-evidence.txt").read_text() == "existing source"
        assert not list(manager.contexts.root.parent.glob("question-*"))
        manager.adapter.release.set()
        await manager.conversations.send("backend-agent", "Implement this requirement", True)
        await completed(manager)
        assert "Implement this requirement" in manager.adapter.contexts[-1]
        assert "Where is the script" not in manager.adapter.contexts[-1]
    finally:
        await manager.close()


async def test_worker_and_integrator_questions_do_not_trigger_team_or_publication(
    tmp_path, monkeypatch
):
    manager, _, _, pushed = await team(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "virtual_agent_cafe.management.conversations.QuestionAdapter", IsolatedFixtureQuestion
    )
    try:
        await start_workers(manager)
        before = manager.store.get("projects", "project")
        executions = manager.store.list("executions")
        publications = list(pushed)
        for identifier in ("project-backend", "project-integration"):
            prepare_question(manager, identifier)
            await manager.conversations.ask(identifier, "Where is the script?")
            await wait_for_answer(manager)
            assert manager.conversations.read(identifier)["question"]["status"] == "COMPLETED"
        await settle(manager)
        assert manager.store.get("projects", "project") == before
        assert manager.store.list("executions") == executions
        assert pushed == publications
    finally:
        await manager.close()


def test_question_is_safe_api_default_and_explicit_instruction_still_resumes(tmp_path, monkeypatch):
    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    manager.workspaces.create("project")
    manager.configure(AgentConfig(id="agent", name="Agent", workspace="project"))
    prepare_question(manager, "agent")
    monkeypatch.setattr(
        "virtual_agent_cafe.management.conversations.QuestionAdapter", IsolatedFixtureQuestion
    )
    with TestClient(app) as client:
        url = "/management/agents/agent/chat"
        assert client.post(url, json={"content": "Where?"}).status_code == 401
        client.headers["Authorization"] = "Bearer " + manager.access.token
        response = client.post(url, json={"content": "Where is the script?"})
        assert response.status_code == 200
        assert response.json()["delivery"] == "ANSWERING"
        assert not manager.store.list("executions")
        assert client.post(url, json={"content": "x", "mode": "invalid"}).status_code == 422


async def test_failed_and_cancelled_answers_preserve_work_state(tmp_path, monkeypatch):
    from virtual_agent_cafe.adapters.base import RunResult

    manager = configured(tmp_path, ControlledRuntime())
    before = manager.registry.get("backend-agent")

    class FailedQuestion:
        def __init__(self, *args, **kwargs):
            pass

        async def run(self, *args):
            return RunResult(False, "Question runtime unavailable")

    monkeypatch.setattr(
        "virtual_agent_cafe.management.conversations.QuestionAdapter", FailedQuestion
    )
    try:
        await manager.conversations.ask("backend-agent", "Where is the script?")
        await wait_for_answer(manager)
        question = manager.conversations.read("backend-agent")["question"]
        assert question["status"] == "FAILED"
        assert question["detail"] == "Question runtime unavailable"
        assert manager.registry.get("backend-agent") == before
        assert not manager.store.list("executions")
        await manager.conversations.ask("backend-agent", "Try answering again")
        await manager.close()
        assert manager.conversations.read("backend-agent")["question"]["status"] == "CANCELLED"
        assert manager.registry.get("backend-agent") == before
    finally:
        await manager.close()

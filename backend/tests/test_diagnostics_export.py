import json

from fastapi.testclient import TestClient
from test_codex import fake_cli

from virtual_agent_cafe.adapters.codex import CodexAdapter
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.diagnostics import export
from virtual_agent_cafe.management.storage import Store


def test_export_complete_history_auth_redaction_and_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("VAC_MANAGEMENT_TOKEN", "private-management-token")
    app = create_app("codex", management_root=tmp_path)
    with TestClient(app) as client:
        store = app.state.management.store
        store.put(
            "executions", "run", {"id": "run", "status": "FAILED", "branch": "agent/frontend"}
        )
        for i in range(251):
            store.log("run", {"detail": f"line {i}"})
        store.runtime_event(
            "run",
            {
                "type": "item.completed",
                "command": "env TOKEN=secret-value godot --headless",
                "output": "Bearer private-management-token",
            },
        )
        store.put(
            "runtime_test_outputs",
            "run",
            {"checks": [{"command": "godot --script test.gd", "exit_code": 0}]},
        )
        store.put("validation_outputs", "run:states", {"stderr": "ERROR: socket", "exit_code": 0})
        store.put("validation_outputs", "other:states", {"stderr": "unrelated"})
        url = "/management/executions/run/diagnostics"
        assert client.get(url).status_code == 401
        client.headers["Authorization"] = "Bearer private-management-token"
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert len(data["activity"]) == 251
        assert data["activity"][-1]["detail"] == "line 250"
        assert "run:states" in data["validation_outputs"]
        assert "other:states" not in data["validation_outputs"]
        assert "secret-value" not in response.text
        assert "private-management-token" not in response.text
        assert "godot --script test.gd" in response.text
        assert client.get("/management/executions/missing/diagnostics").status_code == 404
    reopened = Store(tmp_path)
    assert len(export(reopened, "run")["runtime_events"]) == 1
    reopened.db.close()


async def test_runtime_capture_includes_non_tests_and_stderr_excludes_reasoning(tmp_path):
    body = """
print(json.dumps({"type":"item.completed", "item":{"type":"reasoning", "text":"private thought"}}))
print(json.dumps({"type":"item.completed", "item":{"type":"command_execution",
    "command":"git status",
    "aggregated_output":"clean", "exit_code":0}}))
print(json.dumps({"type":"item.completed", "item":{"type":"agent_message", "text":"Done"}}))
print(json.dumps({"type":"turn.completed"}))
print("runtime warning", file=sys.stderr)
"""
    events = []

    async def sink(event):
        events.append(event)

    adapter = CodexAdapter(fake_cli(tmp_path, body), event_sink=sink)
    result = await adapter.run("task", tmp_path, lambda *_: None)
    assert result.success
    encoded = json.dumps(events)
    assert "git status" in encoded and "runtime warning" in encoded and "Done" in encoded
    assert "private thought" not in encoded


def test_export_redacts_legacy_private_keys_and_credentials(tmp_path):
    store = Store(tmp_path)
    store.put("executions", "old", {"id": "old"})
    store.put(
        "runtime_test_outputs",
        "old",
        {
            "checks": [
                {
                    "aggregated_output": (
                        "-----BEGIN OPENSSH PRIVATE KEY-----\nprivate-material\n"
                        "-----END OPENSSH PRIVATE KEY-----\n"
                        "https://user:credential@example.com/repo\n"
                        'API_KEY="hidden-value"\nPASS'
                    )
                }
            ]
        },
    )
    report = json.dumps(export(store, "old"))
    assert "private-material" not in report
    assert "credential@" not in report
    assert "hidden-value" not in report
    assert "PASS" in report
    store.db.close()

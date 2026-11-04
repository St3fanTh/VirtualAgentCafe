from fastapi.testclient import TestClient

from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.changelog import overview, sections
from virtual_agent_cafe.management.storage import Store


def test_requirement_sections_keep_partial_work_and_legacy_notes():
    result = sections(
        "# Recap\nSummary.\n## Requirement 1.1 — Login\nImplemented endpoint.\n"
        "## Requirement 1.2 — UI\nBlocked: API contract missing."
    )
    assert [row["requirement"] for row in result] == ["", "1.1", "1.2"]
    assert result[1]["title"] == "Login"
    assert result[2]["description"].startswith("Blocked:")
    assert sections("Legacy recap")[0]["description"] == "Legacy recap"
    assert sections("## 1.1 API\nChanged routes.")[0]["requirement"] == "1.1"
    assert sections("## Requirement REQ-42 — API\nChanged routes.")[0]["requirement"] == "REQ-42"


def test_private_changelog_preserves_history_without_claiming_publication(tmp_path, monkeypatch):
    monkeypatch.setenv("VAC_MANAGEMENT_TOKEN", "changelog-fixture-private-token")
    app = create_app("codex", management_root=tmp_path)
    with TestClient(app) as client:
        store = app.state.management.store
        for identifier, agent, date, recap in [
            ("older", "backend", "2026-11-01", "Legacy recap"),
            ("newer", "backend", "2026-11-02", "## Requirement 1.1 — API\nImplemented endpoint."),
            ("frontend-run", "frontend", "2026-11-03", "## Requirement 1.2 — UI\nBlocked."),
        ]:
            store.put(
                "executions",
                identifier,
                {
                    "id": identifier,
                    "agent_id": agent,
                    "agent_name": agent.title(),
                    "started_at": date,
                    "status": "COMPLETED",
                    "changelog": recap,
                    "agent_commit": "abc123",
                    "publication": "FAILED",
                    "workflow": {"integration": "INTEGRATION_PENDING"},
                    "private_prompt": "DO_NOT_EXPOSE",
                    "test_runs": [{"output": "DO_NOT_EXPOSE"}],
                },
            )
        assert client.get("/management/changelog").status_code == 401
        client.headers["Authorization"] = "Bearer changelog-fixture-private-token"
        response = client.get("/management/changelog")
        assert response.status_code == 200
        assert "DO_NOT_EXPOSE" not in response.text
        groups = response.json()["agents"]
        assert len(groups) == 2
        assert [e["execution"] for e in groups[0]["entries"]] == ["newer", "older"]
        first = groups[0]["entries"][0]
        assert first["publication"] == "FAILED"
        assert first["workflow"]["integration"] == "INTEGRATION_PENDING"
        assert first["sections"][0]["requirement"] == "1.1"
        assert overview(Store(tmp_path)) == response.json()

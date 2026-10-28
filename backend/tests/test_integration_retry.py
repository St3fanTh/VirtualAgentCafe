from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.config import AgentConfig


@pytest.mark.parametrize(
    "condition", ["no_run", "unpublished", "task_changed", "ready", "promoted"]
)
def test_retry_reports_blockers_and_distinguishes_queue_from_completion(
    tmp_path, monkeypatch, condition
):
    app = create_app("codex", management_root=tmp_path)
    manager = app.state.management
    manager.workspaces.create("project")
    task = manager.tasks.save("task.md", "# Task\nBuild the service")
    manager.configure(AgentConfig(id="worker", name="Worker", workspace="project", task="task.md"))
    record = {
        "id": "project",
        "agents": ["worker"],
        "auto_integrate": True,
        "integrator": "integrator",
    }
    schedule = Mock()
    monkeypatch.setattr(manager.integrations, "schedule", schedule)
    with TestClient(app) as client:
        manager.store.put("projects", "project", record)
        if condition != "no_run":
            manager.registry.update("worker", last_execution="run")
            manager.store.put(
                "executions",
                "run",
                {
                    "id": "run",
                    "status": "COMPLETED",
                    "publication": "PUSHED",
                    "task_sha256": task["sha256"],
                    "project_sha256": {},
                    "role_sha256": {},
                    "published": {"commit": "a" * 40},
                },
            )
        if condition == "unpublished":
            run = manager.store.get("executions", "run")
            run["publication"] = "FAILED"
            manager.store.put("executions", "run", run)
        if condition == "task_changed":
            manager.tasks.save("task.md", "# Changed\nNew requirements")
        if condition == "promoted":
            record["integration"] = {
                "status": "PROMOTED",
                "signature": manager.integrations.sources(record)["signature"],
            }
            manager.store.put("projects", "project", record)
        response = client.post(
            "/management/projects/project/integrate",
            json={},
            headers={"Authorization": "Bearer " + manager.access.token},
        )
        if condition in {"ready", "promoted"}:
            assert response.status_code == 202
            assert response.json()["status"] == ("QUEUED" if condition == "ready" else "PROMOTED")
            assert schedule.call_count == (1 if condition == "ready" else 0)
        else:
            assert response.status_code == 409
            detail = response.json()["detail"]
            assert "worker" in detail
            expected = {
                "no_run": "no execution",
                "unpublished": "not published",
                "task_changed": "task changed",
            }
            assert expected[condition] in detail
            assert (
                manager.store.get("projects", "project")["integration"]["status"]
                == "WAITING_FOR_WORKERS"
            )
            schedule.assert_not_called()

import asyncio

import pytest
from test_team_integration import settle, team

from virtual_agent_cafe.management.project_documents import load_documents


async def test_reviewed_round_syncs_main_runs_both_workers_and_promotes_again(
    tmp_path, monkeypatch
):
    manager, remote, _, _ = await team(tmp_path, monkeypatch)
    try:
        await settle(manager)
        source = manager.workspaces.get("project")
        # Existing valid Markdown may start with a paragraph or list, not a heading.
        (source / "PLANNING.md").write_text(
            "Implement the shared API.\n- Preserve existing features"
        )
        initial_plan = load_documents(source)["PLANNING.md"]
        initial_round = await manager.integrations.next_iteration(
            "project", "Implement the initial shared API contract", initial_plan["sha256"]
        )
        await settle(manager)
        assert manager.store.get("iterations", initial_round["id"])["status"] == "PROMOTED"
        first = manager.store.get("projects", "project")
        assert first["integration"]["status"] == "PROMOTED"
        base = (await manager.git.run(remote, "rev-parse", "refs/heads/main")).strip()
        source = manager.workspaces.get("project")
        # Updating planning invalidates the latest team input status, but does not
        # erase the fact that main exists or authorize accepting old failed runs.
        with (source / "PLANNING.md").open("a") as plan:
            plan.write("\n## Next requirements\nAdd regression coverage.\n")
        await manager.integrations.advance("project")
        assert (
            manager.store.get("projects", "project")["integration"]["status"]
            == "WAITING_FOR_WORKERS"
        )
        old_plan = load_documents(source)["PLANNING.md"]
        with pytest.raises(ValueError, match="Planning changed"):
            await manager.integrations.next_iteration("project", "Add regression coverage", "")
        dirty = manager.workspaces.get("project-backend") / "preserve.txt"
        dirty.write_text("Uncommitted user work")
        with pytest.raises(ValueError):
            await manager.integrations.next_iteration(
                "project", "Add regression coverage", old_plan["sha256"]
            )
        assert dirty.read_text() == "Uncommitted user work"
        assert load_documents(source)["PLANNING.md"] == old_plan
        dirty.unlink()
        # Suspend workers so start orchestration and duplicate protection can be observed.
        original = manager.adapter.run
        release = asyncio.Event()
        prompts = []

        async def hold(context, workspace, emit):
            prompts.append(context)
            await release.wait()
            return await original(context, workspace, emit)

        monkeypatch.setattr(manager.adapter, "run", hold)
        result = await manager.integrations.next_iteration(
            "project", "Add regression coverage for the shared API", old_plan["sha256"]
        )
        assert result["status"] == "RUNNING" and len(result["runs"]) == 2
        assert result["base"] == base
        record = manager.store.get("projects", "project")
        assert manager.integrations.sources(record) is None
        with pytest.raises(ValueError, match="current team"):
            await manager.integrations.next_iteration(
                "project", "Duplicate round", load_documents(source)["PLANNING.md"]["sha256"]
            )
        for run_id in result["runs"]:
            run = manager.store.get("executions", run_id)
            assert run["iteration_id"] == result["id"]
            path = manager.workspaces.get(run["workspace"])
            await manager.git.run(path, "merge-base", "--is-ancestor", base, "HEAD")
            assert (path / "backend.py").exists() and (path / "frontend.py").exists()
        release.set()
        await settle(manager)
        assert all("Add regression coverage for the shared API" in prompt for prompt in prompts)
        final = manager.store.get("projects", "project")
        assert final["integration"]["status"] == "PROMOTED", final["integration"]
        assert manager.store.get("iterations", result["id"])["base"] == base
        assert manager.store.get("iterations", result["id"])["status"] == "PROMOTED"
        head = (await manager.git.run(remote, "rev-parse", "refs/heads/main")).strip()
        assert head != base
        requirements = await manager.git.run(remote, "show", f"{head}:validation/requirements.md")
        assert "Add regression coverage for the shared API" in requirements
        # Old published runs cannot satisfy a new iteration even with unchanged tasks.
        final["iteration"]["id"] = "future-round"
        with pytest.raises(ValueError, match="iteration"):
            manager.integrations.sources(final, explain=True)
    finally:
        await manager.close()


@pytest.mark.parametrize("status", ["READY", "WAITING_FOR_WORKERS", "FAILED", "NEEDS_INPUT"])
async def test_previous_team_status_does_not_replace_current_input_validation(tmp_path, status):
    """Preflight should validate the new request, not demand a transient success label."""
    from types import SimpleNamespace

    from virtual_agent_cafe.management.integration import Integrations
    from virtual_agent_cafe.management.storage import Store

    store = Store(tmp_path / "controller")
    source = tmp_path / "source"
    source.mkdir()
    (source / "PLANNING.md").write_text("# Updated planning\nNew requirements")
    store.put(
        "projects",
        "project",
        {
            "id": "project",
            "agents": ["backend", "frontend"],
            "integrator": "integration",
            "auto_integrate": True,
            "integration": {"status": status},
        },
    )
    manager = SimpleNamespace(
        store=store,
        control=asyncio.Lock(),
        running={},
        workspaces=SimpleNamespace(get=lambda _: source),
    )
    integrations = Integrations(manager)
    try:
        with pytest.raises(ValueError, match="Planning changed"):
            await integrations.next_iteration("project", "Implement new requirements", "")
        assert store.get("projects", "project")["integration"]["status"] == status
        assert not integrations.preparing
    finally:
        store.db.close()

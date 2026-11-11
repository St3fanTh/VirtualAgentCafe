"""Management HTTP -> deterministic workers -> real Git/pytest -> product verification."""

import asyncio
import subprocess
import sys

import httpx
import pytest
from fixtures.pipeline_runtime import OBJECTIVE, prepare

from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.diagnostics import export
from virtual_agent_cafe.management.storage import Store


async def settle(manager):
    async with asyncio.timeout(90):
        while manager.running or manager.integrations.running:
            await asyncio.gather(
                *list(manager.running.values()), *list(manager.integrations.running.values())
            )


@pytest.mark.parametrize("fail_first", [False, True], ids=["success", "failure-retry"])
async def test_management_pipeline_verifies_product_before_publishing(
    tmp_path, monkeypatch, fail_first
):
    app = create_app("codex", management_root=tmp_path / "controller")
    state = await prepare(app, tmp_path, monkeypatch, fail_product=fail_first)
    manager = state["manager"]
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            assert (await client.post("/management/setup/team", json={})).status_code == 401
            client.headers["Authorization"] = "Bearer " + manager.access.token
            response = await client.post(
                "/management/setup/team",
                json={
                    "project": "counter",
                    "objective": OBJECTIVE,
                    "auto_integrate": True,
                },
            )
            assert response.status_code == 201, response.text
            for role in ("backend", "frontend"):
                response = await client.post(f"/management/agents/counter-{role}/start", json={})
                assert response.status_code == 202, response.text
            await settle(manager)
            project = manager.store.get("projects", "counter")
            if fail_first:
                assert project["integration"]["status"] == "NEEDS_INPUT", project
                failed_id = project["integration"]["execution"]
                failed = (
                    await client.get(f"/management/executions/{failed_id}/diagnostics")
                ).json()
                assert failed["execution"]["validation"]["passed"] is False
                assert "AssertionError" in str(failed["validation_outputs"])
                assert (
                    await manager.git.run(state["remote"], "rev-parse", "main")
                ).strip() == state["initial"]
                assert not any(ref.endswith(":refs/heads/main") for ref in state["pushed"])
                state["runtime"].fail_product = False
                response = await client.post("/management/projects/counter/integrate", json={})
                assert response.status_code == 202, response.text
                await settle(manager)
                project = manager.store.get("projects", "counter")
                # Failed evidence is retained, not rewritten into a pass by recovery.
                assert (await client.get(f"/management/executions/{failed_id}")).json()[
                    "validation"
                ]["passed"] is False
            assert project["integration"]["status"] == "PROMOTED", manager.store.list("executions")
            run_id = project["integration"]["execution"]
            response = await client.get(f"/management/executions/{run_id}/diagnostics")
            assert response.status_code == 200
            evidence = response.json()
            run = evidence["execution"]
            head = (await manager.git.run(state["remote"], "rev-parse", "main")).strip()
            assert (
                head
                == run["validation"]["commit"]
                == run["published"]["commit"]
                == run["promoted"]["commit"]
            )
            assert run["workflow"]["integration"] == "INTEGRATED"
            assert run["validation"]["checks"][0]["cached"] is False
            assert evidence["validation_outputs"][run_id + ":counter-behavior"]["exit_code"] == 0
            activity = "\n".join(item.get("detail", "") for item in evidence["activity"])
            assert "Shared check counter-behavior: PASS" in activity
            assert "tested integration promoted to main" in activity
            assert "counter-backend" in state["runtime"].calls
            assert "counter-frontend" in state["runtime"].calls
            # Independent oracle: retrieve exactly the published product, outside worker tests.
            product = tmp_path / "independent-product"
            product.mkdir()
            for name in ("counter.py", "controls.py"):
                (product / name).write_text(
                    await manager.git.run(state["remote"], "show", f"{head}:{name}")
                )
            result = await asyncio.to_thread(
                subprocess.run,
                [
                    sys.executable,
                    "-c",
                    "from controls import CounterControls; "
                    "c=CounterControls(); "
                    "assert [c.click(x) for x in ['minus','minus','plus','reset','plus']] "
                    "== ['-1','-2','-1','0','1']",
                ],
                cwd=product,
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, result.stderr
            assert manager.access.token not in response.text
            restored = Store(tmp_path / "controller")
            try:
                persisted = export(restored, run_id)
                assert persisted["execution"]["promoted"]["commit"] == head
                assert persisted["validation_outputs"] == evidence["validation_outputs"]
            finally:
                restored.db.close()
    finally:
        await manager.close()


@pytest.fixture
def smoke_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "scripts/management_smoke.py"
    spec = importlib.util.spec_from_file_location("management_smoke_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_smoke_requires_success_before_independent_acceptance(smoke_module):
    smoke_module.verify_runtime(
        {"status": "COMPLETED", "runtime_success": True, "acceptance": "UNVERIFIED"}
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "FAILED"},
        {"runtime_success": False},
        {"acceptance": "ACCEPTED"},
        {"acceptance": "REVIEW_REQUIRED"},
    ],
)
def test_smoke_rejects_failure_or_premature_acceptance(smoke_module, changes):
    result = {"status": "COMPLETED", "runtime_success": True, "acceptance": "UNVERIFIED"}
    with pytest.raises(RuntimeError):
        smoke_module.verify_runtime(result | changes)


def test_smoke_failure_detail_redacts_credentials(smoke_module, monkeypatch):
    monkeypatch.setenv("EXAMPLE_API_KEY", "private-fixture-credential")
    with pytest.raises(RuntimeError) as error:
        smoke_module.verify_runtime(
            {"status": "FAILED", "detail": "Provider rejected private-fixture-credential"}
        )
    assert "Provider rejected" in str(error.value)
    assert "private-fixture-credential" not in str(error.value)

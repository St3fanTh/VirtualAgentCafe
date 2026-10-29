import asyncio
import subprocess

import pytest
from fastapi.testclient import TestClient
from test_project_setup import project

from virtual_agent_cafe.adapters.base import RunResult
from virtual_agent_cafe.main import create_app
from virtual_agent_cafe.management.project_documents import (
    ProjectDocumentInput,
    load_documents,
    save_document,
)
from virtual_agent_cafe.management.setup import SetupInput


@pytest.mark.parametrize("filename", ["AGENTS.md", "agents.md", "PLANNING.md", "planning.md"])
def test_document_aliases_preserved_and_conflicts_rejected(tmp_path, filename):
    (tmp_path / filename).write_text("\ufeff# Existing instructions\nKeep me.")
    canonical = filename.upper().replace(".MD", ".md")
    loaded = load_documents(tmp_path)[canonical]
    save_document(
        tmp_path,
        ProjectDocumentInput(
            project="sample",
            name=canonical,
            content=loaded["content"],
            expected_sha256=loaded["sha256"],
        ),
    )
    assert loaded["file"] == filename
    update = ProjectDocumentInput(
        project="sample",
        name=canonical,
        content="# Updated instructions",
        expected_sha256=loaded["sha256"],
    )
    saved = save_document(tmp_path, update)
    assert saved[canonical]["file"] == filename
    assert (tmp_path / filename).read_text() == "# Updated instructions"
    with pytest.raises(ValueError, match="changed on disk"):
        save_document(tmp_path, update)


def test_missing_document_symlink_and_size_validation(tmp_path):
    assert not load_documents(tmp_path)["PLANNING.md"]["exists"]
    data = ProjectDocumentInput(
        project="sample", name="PLANNING.md", content="# Plan\nImplement tests", expected_sha256=""
    )
    save_document(tmp_path, data)
    with pytest.raises(ValueError, match="changed on disk"):
        save_document(tmp_path, data)
    (tmp_path / "agents.md").symlink_to(tmp_path / "PLANNING.md")
    with pytest.raises(ValueError, match="Symlinks"):
        load_documents(tmp_path)
    (tmp_path / "agents.md").unlink()
    (tmp_path / "AGENTS.md").write_text("x" * 65537)
    with pytest.raises(ValueError, match="64 KiB"):
        load_documents(tmp_path)


async def test_each_agent_receives_latest_source_documents_in_readonly_snapshots(
    tmp_path, monkeypatch
):
    manager, setup, source = await project(tmp_path, monkeypatch)
    await setup.create(SetupInput(project="sample", objective="Implement backend and frontend."))
    # These files were never committed and do not exist in either worktree.
    (source / "AGENTS.md").write_text("# Shared agents\nAlways test the API contract.")
    (source / "planning.md").write_text("# Shared plan\nFrontend depends on the API contract.")
    prompts = []

    class CaptureRuntime:
        async def run(self, prompt, workspace, emit):
            prompts.append(prompt)
            return RunResult(True, "Fixture complete")

    manager.adapter = CaptureRuntime()
    runs = []
    for agent in ["sample-backend", "sample-frontend"]:
        runs.append(await manager.start(agent))
    await asyncio.gather(*manager.running.values())
    assert len(prompts) == 2
    for run in runs:
        record = manager.store.get("executions", run["id"])
        snapshot = manager.contexts.path(run["id"])
        assert record["project_sha256"] == {
            n: d["sha256"] for n, d in load_documents(source).items()
        }
        assert "Always test the API contract" in (snapshot / "project/AGENTS.md").read_text()
        workspace = manager.workspaces.get(run["workspace"])
        assert not (workspace / "planning.md").exists()
        command = manager.sandbox.command(
            workspace,
            [
                "/usr/bin/python3",
                "-c",
                """
from pathlib import Path
path = Path('.cafe/instructions/project/AGENTS.md')
assert 'Always test the API contract' in path.read_text()
try:
    path.write_text('override security')
except OSError:
    pass
else:
    raise AssertionError('project instructions must be read-only')
""",
            ],
            instructions=snapshot,
        )
        result = await asyncio.to_thread(
            subprocess.run, command, capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, result.stderr
    assert all("Frontend depends on the API contract" in p for p in prompts)
    # A subsequent run sees edits; previous execution snapshots remain unchanged.
    (source / "planning.md").write_text("# Revised plan\nAdd authentication tests.")
    new_run = await manager.start("sample-backend")
    await asyncio.gather(*manager.running.values())
    assert "Add authentication tests" in prompts[-1]
    assert (
        "Frontend depends"
        in (manager.contexts.path(runs[0]["id"]) / "project/PLANNING.md").read_text()
    )
    assert new_run["project_sha256"] != runs[0]["project_sha256"]


def test_document_api_authorization_conflicts_and_fixed_paths(tmp_path):
    app = create_app("demo", management_root=tmp_path)
    manager = app.state.management
    path = manager.workspaces.files.root / "project"
    (path / ".git").mkdir(parents=True)
    headers = {"Authorization": "Bearer " + manager.access.token}
    with TestClient(app) as client:
        assert (
            client.post("/management/setup/documents/load", json={"project": "project"}).status_code
            == 401
        )
        loaded = client.post(
            "/management/setup/documents/load", headers=headers, json={"project": "project"}
        ).json()
        assert not loaded["documents"]["AGENTS.md"]["exists"]
        body = {
            "project": "project",
            "name": "AGENTS.md",
            "content": "# Project instructions\n" + "äöü\n" * 6000,
            "expected_sha256": "",
        }
        assert (
            client.put("/management/setup/documents", headers=headers, json=body).status_code == 200
        )
        assert (
            client.put("/management/setup/documents", headers=headers, json=body).status_code == 409
        )
        body["name"] = "../outside.md"
        assert (
            client.put("/management/setup/documents", headers=headers, json=body).status_code == 422
        )
        manager.store.put(
            "agents",
            "running-agent",
            {"config": {"workspace": "project", "git": {"repository": "project"}}},
        )
        manager.running["running-agent"] = None
        body.update(name="PLANNING.md", content="# Plan")
        assert (
            client.put("/management/setup/documents", headers=headers, json=body).status_code == 409
        )
        manager.running.clear()


def test_large_planning_utf8_roundtrip_and_byte_limit(tmp_path):
    content = "# Planning\n" + "Anforderung äöü\n" * 2500
    data = ProjectDocumentInput(
        project="sample", name="PLANNING.md", content=content, expected_sha256=""
    )
    assert len(content.encode()) > 12000
    assert save_document(tmp_path, data)["PLANNING.md"]["content"] == content
    data.content = "# Plan\n" + "ä" * 33000
    data.expected_sha256 = load_documents(tmp_path)["PLANNING.md"]["sha256"]
    with pytest.raises(ValueError, match="64 KiB"):
        save_document(tmp_path, data)
    assert load_documents(tmp_path)["PLANNING.md"]["content"] == content


@pytest.mark.parametrize(
    "content",
    [
        "Implement the shared API.",
        "- Add login\n- Test authentication",
        "<!-- Project notes -->\n# Planning",
        "\ufeffPlanning\n========\nRequirements",
    ],
)
def test_project_markdown_without_leading_hash_is_preserved(tmp_path, content):
    for name in ("AGENTS.md", "PLANNING.md"):
        saved = save_document(
            tmp_path,
            ProjectDocumentInput(
                project="sample",
                name=name,
                content=content,
                expected_sha256="",
            ),
        )
        assert saved[name]["content"] == content
        assert (tmp_path / name).read_text() == content


def test_project_document_errors_distinguish_empty_size_and_file_type(tmp_path):
    data = ProjectDocumentInput(
        project="sample", name="PLANNING.md", content=" \n\ufeff", expected_sha256=""
    )
    with pytest.raises(ValueError, match="PLANNING.md is empty"):
        save_document(tmp_path, data)
    assert not (tmp_path / "PLANNING.md").exists()
    data.content = "ä" * 32768
    saved = save_document(tmp_path, data)
    data.expected_sha256 = saved["PLANNING.md"]["sha256"]
    data.content += "ä"
    with pytest.raises(ValueError, match="PLANNING.md is too large: 65538 UTF-8 bytes"):
        save_document(tmp_path, data)
    assert (tmp_path / "PLANNING.md").read_text() == "ä" * 32768
    (tmp_path / "AGENTS.md").mkdir()
    with pytest.raises(ValueError, match="regular Markdown file, not a directory"):
        load_documents(tmp_path)


def test_oversized_ascii_api_reports_exact_size_without_overwriting(tmp_path):
    app = create_app("demo", management_root=tmp_path)
    manager = app.state.management
    path = manager.workspaces.files.root / "project"
    (path / ".git").mkdir(parents=True)
    (path / "PLANNING.md").write_text("Keep these requirements.")
    headers = {"Authorization": "Bearer " + manager.access.token}
    with TestClient(app) as client:
        result = client.put(
            "/management/setup/documents",
            headers=headers,
            json={
                "project": "project",
                "name": "PLANNING.md",
                "content": "a" * 65537,
                "expected_sha256": load_documents(path)["PLANNING.md"]["sha256"],
            },
        )
        assert result.status_code == 409
        assert "PLANNING.md is too large: 65537 UTF-8 bytes" in result.json()["detail"]
        assert (path / "PLANNING.md").read_text() == "Keep these requirements."

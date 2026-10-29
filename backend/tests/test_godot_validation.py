import hashlib
import json

import pytest

from virtual_agent_cafe.bus import EventBus
from virtual_agent_cafe.management.config import AgentConfig
from virtual_agent_cafe.management.execution import ExecutionManager
from virtual_agent_cafe.management.validation import validate


async def fixture(tmp_path, *, resource_uri=False):
    manager = ExecutionManager(tmp_path, EventBus())
    manager.workspaces.create("source")
    source = manager.workspaces.get("source")
    await manager.git.init("source")
    (source / "README.md").write_text("# Main has no Godot scripts\n")
    await manager.git.stage("source", ["README.md"])
    await manager.git.commit("source", "feat: initial")
    main = (await manager.git.run(source, "rev-parse", "HEAD")).strip()
    branch = "agent/integration/validation"
    manager.workspaces.create("integration")
    await manager.git.worktree("source", "integration", branch)
    workspace = manager.workspaces.get("integration")
    (workspace / "frontend/tests").mkdir(parents=True)
    (workspace / "frontend/project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Validation fixture"\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
    )
    (workspace / ".gitignore").write_text(".godot/\n*.gd.uid\n")
    checks = []
    for name in ("test_backend", "test_frontend", "test_contract"):
        (workspace / f"frontend/tests/{name}.gd").write_text(
            'extends SceneTree\nfunc _initialize():\n\tprint("PASS")\n\tquit(0)\n'
        )
        checks.append(
            {
                "id": name,
                "kind": "godot",
                "directory": "frontend",
                "script": ("res://" if resource_uri else "") + f"tests/{name}.gd",
            }
        )
    requirements = "# Requirements\nAll three Godot checks must pass.\n"
    digest = hashlib.sha256(requirements.encode()).hexdigest()
    (workspace / "validation").mkdir()
    (workspace / "validation/requirements.md").write_text(requirements)
    plan = {
        "source_sha256": digest,
        "requirements": [
            {
                "id": "REQ-1",
                "description": "All Godot contracts are tested",
                "checks": [c["id"] for c in checks],
            }
        ],
        "checks": checks,
    }
    (workspace / "validation/plan.json").write_text(json.dumps(plan))
    await manager.git.stage(
        "integration",
        [
            ".gitignore",
            "frontend/project.godot",
            "validation/plan.json",
            "validation/requirements.md",
            *[
                f"frontend/tests/{name}.gd"
                for name in ("test_backend", "test_frontend", "test_contract")
            ],
        ],
    )
    await manager.git.commit("integration", "test: add integration-only Godot scripts")
    commit = (await manager.git.run(workspace, "rev-parse", "HEAD")).strip()
    config = AgentConfig(
        id="integrator",
        name="Integrator",
        workspace="integration",
        git={"enabled": True, "repository": "source", "branch": branch},
        execution={"integration_validation": True},
    )
    run = {
        "id": "validation-run",
        "agent_id": "integrator",
        "branch": branch,
        "requirements_sha256": digest,
    }
    manager.emit = lambda *args: None
    return manager, config, run, workspace, main, commit


@pytest.mark.parametrize("resource_uri", [False, True])
async def test_committed_scripts_only_on_integration_branch(tmp_path, resource_uri):
    manager, config, run, workspace, main, commit = await fixture(
        tmp_path, resource_uri=resource_uri
    )
    assert "frontend/tests/" not in await manager.git.run(
        workspace, "ls-tree", "-r", "--name-only", main
    )
    assert len((await manager.git.run(workspace, "ls-files", "frontend/tests/")).splitlines()) == 3
    report = await validate(manager, config, run, workspace)
    assert report["commit"] == commit != main
    assert report["passed"] and len(report["checks"]) == 3
    inspected = [e for e in report["diagnostics"] if e["rule"] == "godot.script"]
    assert len(inspected) == 3
    for entry in inspected:
        assert entry["selected_ref"] == "HEAD" and entry["commit"] == commit
        assert entry["branch"] == run["branch"]
        assert entry["directory"] == "frontend"
        assert entry["resolved_path"] == str(workspace / entry["git_path"])
        assert entry["blob_exists"] is True and entry["blob_oid"]
    assert (await manager.git.run(workspace, "rev-parse", "main")).strip() == main


async def save_plan(manager, workspace, mutate):
    path = workspace / "validation/plan.json"
    plan = json.loads(path.read_text())
    mutate(plan)
    path.write_text(json.dumps(plan))
    await manager.git.stage("integration", ["validation/plan.json"])
    if (await manager.git.run(workspace, "diff", "--cached", "--name-only")).strip():
        await manager.git.commit("integration", "test: change validation declaration")


@pytest.mark.parametrize(
    "case, rule",
    [
        ("duplicate-directory", "godot.script.file_exists"),
        ("traversal", "godot.script_path"),
        ("absolute", "godot.script_path"),
        ("name", "godot.script_name"),
        ("extension", "godot.script_extension"),
        ("symlink", "godot.script_path"),
        ("staged", "godot.script.blob_exists"),
        ("modified", "godot.script.content_matches_commit"),
        ("snapshot", "plan.requirements_snapshot"),
    ],
)
async def test_exact_failure_rule_and_no_stale_success(tmp_path, case, rule):
    manager, config, run, workspace, _, _ = await fixture(tmp_path)
    original = workspace / "frontend/tests/test_backend.gd"
    script = "tests/test_backend.gd"
    if case == "duplicate-directory":
        script = "frontend/" + script
    elif case == "traversal":
        script = "../frontend/" + script
    elif case == "absolute":
        script = str(original)
    elif case in {"name", "extension", "staged", "symlink"}:
        filename = {
            "name": "smoke.gd",
            "extension": "test_backend.txt",
            "staged": "test_staged.gd",
            "symlink": "test_link.gd",
        }[case]
        script = "tests/" + filename
        target = workspace / "frontend" / script
        if case == "symlink":
            target.symlink_to(original.name)
        elif case != "staged":
            target.write_bytes(original.read_bytes())
            await manager.git.stage("integration", ["frontend/" + script])
            await manager.git.commit("integration", "test: add alternate test entry")
    await save_plan(manager, workspace, lambda p: p["checks"][0].update(script=script))
    if case == "staged":
        (workspace / "frontend" / script).write_bytes(original.read_bytes())
        await manager.git.stage("integration", ["frontend/" + script])
    elif case == "modified":
        original.write_text(original.read_text() + "# uncommitted\n")
    elif case == "snapshot":
        run["requirements_sha256"] = "0" * 64
    run["validation"] = {"passed": True, "commit": "old-success"}
    with pytest.raises(ValueError, match=rule):
        await validate(manager, config, run, workspace)
    report = manager.store.get("executions", run["id"])["validation"]
    assert not report["passed"] and report["failed_rule"] == rule
    assert report["commit"] != "old-success"
    entry = report["diagnostics"][-1]
    assert entry["rule"] == rule and entry["outcome"] == "failed"
    assert entry["repository_root"] == str(workspace)
    if case in {"name", "extension"}:
        assert entry["blob_exists"] is True
    if case == "staged":
        assert entry["blob_exists"] is False
    assert any(rule in log["detail"] for log in manager.store.logs(run["id"]))


async def test_wrong_workspace_branch_is_not_misclassified_as_missing_script(tmp_path):
    manager, config, run, _, main, _ = await fixture(tmp_path)
    with pytest.raises(ValueError, match="git.branch"):
        await validate(manager, config, run, manager.workspaces.get("source"))
    assert run["validation"]["commit"] == main
    assert run["validation"]["failed_rule"] == "git.branch"


async def test_head_change_during_validation_never_leaves_passed_report(tmp_path, monkeypatch):
    manager, config, run, workspace, _, commit = await fixture(tmp_path)
    original = manager.git.run

    async def move_head(path, *args, **kwargs):
        if args == ("rev-parse", "HEAD"):
            await original(path, "commit", "--allow-empty", "-m", "test: concurrent change")
        return await original(path, *args, **kwargs)

    monkeypatch.setattr(manager.git, "run", move_head)
    with pytest.raises(ValueError, match="git.commit_unchanged"):
        await validate(manager, config, run, workspace)
    assert not run["validation"]["passed"]
    assert run["validation"]["commit"] == commit


async def test_dirty_test_output_does_not_validate_a_different_worktree(tmp_path):
    manager, config, run, workspace, _, _ = await fixture(tmp_path)
    path = workspace / "frontend/tests/test_contract.gd"
    path.write_text(
        "extends SceneTree\nfunc _initialize():\n"
        '\tFileAccess.open("res://generated.txt", FileAccess.WRITE).store_string("changed")\n'
        "\tquit(0)\n"
    )
    await manager.git.stage("integration", ["frontend/tests/test_contract.gd"])
    await manager.git.commit("integration", "test: generate uncommitted output")
    with pytest.raises(ValueError, match="workspace.clean_after_tests"):
        await validate(manager, config, run, workspace)
    assert not run["validation"]["passed"]


async def test_push_rejects_commit_changed_since_validation(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    manager, config, run, workspace, main, _ = await fixture(tmp_path)
    monkeypatch.setattr(
        manager.git, "push_target", AsyncMock(return_value=(workspace, run["branch"]))
    )
    with pytest.raises(ValueError, match="changed after validation"):
        await manager.git.push(config, expected_commit=main)


@pytest.mark.parametrize("exit_code", [0, 1])
async def test_godot_execution_errors_are_not_missing_scripts(tmp_path, exit_code):
    manager, config, run, workspace, _, _ = await fixture(tmp_path)
    path = workspace / "frontend/tests/test_contract.gd"
    path.write_text(
        "extends SceneTree\nfunc _initialize():\n"
        f'\tpush_error("fixture execution failure")\n\tquit({exit_code})\n'
    )
    await manager.git.stage("integration", ["frontend/tests/test_contract.gd"])
    await manager.git.commit("integration", "test: report runtime error")
    with pytest.raises(ValueError, match="check.result"):
        await validate(manager, config, run, workspace)
    assert run["validation"]["checks"][-1]["passed"] is False
    assert run["validation"]["checks"][-1]["exit_code"] == exit_code


async def test_committed_scripts_with_git_crlf_checkout_rules(tmp_path):
    manager, config, run, workspace, _, _ = await fixture(tmp_path)
    (workspace / ".gitattributes").write_text("frontend/tests/*.gd text eol=crlf\n")
    await manager.git.stage("integration", [".gitattributes"])
    await manager.git.commit("integration", "test: configure Windows checkout line endings")
    for path in (workspace / "frontend/tests").glob("*.gd"):
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    # Refresh index stat data after introducing checkout attributes; blobs remain unchanged.
    await manager.git.stage(
        "integration",
        [
            f"frontend/tests/{name}.gd"
            for name in ("test_backend", "test_frontend", "test_contract")
        ],
    )
    assert not (await manager.git.run(workspace, "diff", "--cached", "--name-only")).strip()
    await manager.git.require_clean(workspace)
    report = await validate(manager, config, run, workspace)
    assert report["passed"]


async def test_git_blob_lookup_failure_is_not_a_missing_script(tmp_path, monkeypatch):
    from virtual_agent_cafe.management.git import GitOperationError

    manager, config, run, workspace, _, commit = await fixture(tmp_path)
    oid = (
        await manager.git.run(workspace, "rev-parse", f"{commit}:frontend/tests/test_backend.gd")
    ).strip()
    original = manager.git.run

    async def unavailable(path, *args, **kwargs):
        if args == ("cat-file", "-t", oid):
            raise GitOperationError("Git cat-file failed: repository object unavailable")
        return await original(path, *args, **kwargs)

    monkeypatch.setattr(manager.git, "run", unavailable)
    with pytest.raises(ValueError, match="godot.script.blob_lookup"):
        await validate(manager, config, run, workspace)
    report = run["validation"]
    assert report["failed_rule"] == "godot.script.blob_lookup"
    assert report["diagnostics"][-1]["blob_exists"] is None
    assert not report["passed"]

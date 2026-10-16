extends SceneTree

func _initialize() -> void:
	call_deferred("render")

func render() -> void:
	root.gui_embed_subwindows = true
	var cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	await create_timer(0.3).timeout
	var ui = cafe.management
	ui.poll.stop()
	ui.token.text = ""
	ui.cache = {
		"agents": [{"config": {"id": "backend-agent", "name": "Backend Engineer", "workspace": "api",
		"task": "implement-api.md", "roles": ["backend.md"], "git": {"enabled": true, "repository": "project", "branch": "agent/backend/api", "remote_name": "origin"},
		"execution": {"timeout_seconds": 900, "max_retries": 0}}, "state": "READY", "task_state": "ASSIGNED"},
		{"config": {"id": "frontend-agent", "name": "Frontend Engineer", "workspace": "frontend", "task": "login-screen.md", "roles": ["frontend.md"], "git": {"enabled": false}, "execution": {"timeout_seconds": 300, "max_retries": 0}}, "state": "CONFIGURED", "task_state": "ASSIGNED"}],
		"workspaces": [{"id": "api", "path": "/workspaces/api"}, {"id": "frontend", "path": "/workspaces/frontend"}, {"id": "project", "path": "/workspaces/project"}],
		"roles": [{"file": "backend.md", "content": "# Backend Developer\n\nBuild clear APIs and test important behavior."}, {"file": "frontend.md", "content": "# Frontend Developer"}],
		"tasks": [{"file": "implement-api.md", "content": "# Implement the project API\n\n## Objective\nExtend the existing service.\n\n## Acceptance Criteria\n- API tests pass\n- Changes stay on the agent branch\n- Reviewer accepts the task"}],
		"executions": []}
	ui.setup_project.add_item("my-project")
	ui.setup_objective.text = "Build a task tracker. Backend: task API. Frontend: task list and creation form. Shared contract: GET /api/tasks and POST /api/tasks."
	ui.setup_result.text = "DESIGN PREVIEW · example data\n\n1. Choose the project folder using the local starter.\n\n2. Run Check project to verify Codex login, namespace sandbox and Git.\n\n3. Create your team. Each agent gets editable Markdown roles/tasks and its own worktree and branch.\n\n4. Review the tasks and start each agent from Agents.\n\nNo automatic model task, push or merge."
	ui.populate()
	ui.load_agent(0)
	ui.show_management()
	ui.notice.text = "DESIGN PREVIEW · example data · no live task running"
	var directory := OS.get_environment("VAC_PREVIEW_DIR")
	if directory.is_empty():
		directory = "/tmp/vac-ui-previews"
	DirAccess.make_dir_recursive_absolute(directory)
	for index in 5:
		ui.tabs.current_tab = index
		if index == 1:
			ui.load_definition()
		await create_timer(0.15).timeout
		await RenderingServer.frame_post_draw
		var image := root.get_texture().get_image()
		image.save_png(directory + "/management-" + str(index) + ".png")
	ui.tabs.current_tab = 0
	ui.task_file.show_popup()
	await create_timer(0.15).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(directory + "/management-popup.png")
	ui.task_file.get_popup().hide()
	ui.hide()
	cafe.select_agent("ada")
	cafe.task_info.text = "DESIGN PREVIEW · Task for Ada / Backend"
	cafe.task_input.text = "Implement the project endpoint using the existing architecture.\n\nAdd relevant tests and document the result."
	await create_timer(0.15).timeout
	await RenderingServer.frame_post_draw
	root.get_texture().get_image().save_png(directory + "/task-dialog.png")
	print("Godot management design previews: PASS")
	quit()

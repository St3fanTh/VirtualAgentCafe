extends "res://tests/test_gui_input.gd"

func run() -> void:
	root.gui_embed_subwindows = true
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	if OS.get_environment("VAC_GUI_RENDERED") == "1":
		cafe.world.hide()
	await frames(12)
	var ui = cafe.management
	ui.poll.stop()
	await settled(ui)
	check(ui.visible and ui.tabs.current_tab == 4, "Starter opens wizard automatically")
	check(ui.chosen(ui.setup_project) == "wizard-project", "Starter preselects mounted project")
	await click(ui.buttons["Close"])
	var entry: Button
	for node in cafe.find_children("*", "Button", true, false):
		if node.text == "Manage agents":
			entry = node
	await click(entry)
	await settled(ui)
	await click(ui.buttons["Setup project"])
	await settled(ui)
	check(ui.tabs.current_tab == 4, "Project setup opens through pointer")
	check(ui.setup_project.item_count == 1, "Approved source repositories listed")
	check(ui.buttons["Create backend + frontend team"].disabled, "Cannot create before checks")
	await type_text(ui.setup_objective, "Build an API and matching frontend. Share the task contract.")
	await click(ui.buttons["Check project"])
	await settled(ui)
	check(ui.setup_ready, "Real namespace and repository checks pass with fixture login")
	check(ui.setup_result.text.contains("PASS"), "Readiness report visible")
	check(not ui.buttons["Create backend + frontend team"].disabled, "Ready team can be created")
	await click(ui.buttons["Create backend + frontend team"])
	await settled(ui)
	check(ui.setup_result.text.contains("TEAM READY"), "Creation result is shown")
	check(ui.cache.agents.size() == 2, "Both agents persist via API")
	for agent in ui.cache.agents:
		check(agent.state == "CONFIGURED", "Setup never starts model tasks")
		check(not agent.config.git.allow_push, "Push disabled by default")
		check(agent.config.git.worktree, "Separate worktree for each agent")
	await tab(ui, 0)
	check(ui.agents.item_count == 2, "Team appears in original agent management")
	await click(ui.agents, Vector2(35, 20))
	await frames()
	check(not ui.active_agent.is_empty(), "Generated agent can be selected for review")
	await click(ui.buttons["Close"])
	check(not ui.visible, "Wizard can be closed")
	cafe.queue_free()
	await frames()
	print("Godot project setup input tests: PASS (", checks, " checks)")
	quit(0)

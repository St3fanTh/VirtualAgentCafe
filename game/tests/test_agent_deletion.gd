extends "res://tests/test_gui_input.gd"

func wait_for(predicate: Callable, message: String) -> void:
	var deadline := Time.get_ticks_msec() + 10000
	while not predicate.call():
		check(Time.get_ticks_msec() < deadline, message)
		await process_frame
	await frames()

func run() -> void:
	root.gui_embed_subwindows = true
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	if OS.get_environment("VAC_GUI_RENDERED") == "1":
		cafe.world.hide()
	await frames(12)
	var ui = cafe.management
	ui.poll.stop()
	ui.show_management()
	await settled(ui)
	ui.call_api("mutation", "/workspaces", HTTPClient.METHOD_POST, {"id": "project"})
	await settled(ui)
	ui.call_api("mutation", "/definitions/tasks/task.md", HTTPClient.METHOD_PUT, {"content": "# Task\nPreserve all project work."})
	await settled(ui)
	ui.call_api("mutation", "/agents", HTTPClient.METHOD_POST, {"id": "delete-me", "name": "Delete me", "workspace": "project", "task": "task.md"})
	await settled(ui)
	await wait_for(func(): return cafe.characters.has("delete-me"), "Configured agent appears in cafe")
	check(ui.active_agent == "delete-me", "Created agent selected")
	check(not ui.buttons["Delete agent"].disabled, "Stopped agent can be deleted")
	await click(ui.buttons["Delete agent"])
	check(ui.delete_dialog.visible, "Pointer opens confirmation")
	check(ui.delete_dialog.dialog_text.contains("Workspace, Git branches"), "Confirmation explains preserved work")
	await key(KEY_ESCAPE)
	check(not ui.delete_dialog.visible, "Escape cancels deletion")
	check(ui.cache.agents.size() == 1 and cafe.characters.has("delete-me"), "Cancel preserves registry and character")
	await click(ui.buttons["Delete agent"])
	check(ui.delete_dialog.visible, "Confirmation reopens")
	await key(KEY_ENTER)
	await settled(ui)
	await wait_for(func(): return ui.cache.agents.is_empty() and not cafe.characters.has("delete-me"), "Confirmed deletion removes list entry and live character")
	check(ui.active_agent.is_empty() and not ui.editing, "Deleted agent form clears")
	check(ui.buttons["Delete agent"].disabled, "No selected agent cannot be deleted")
	check(ui.cache.workspaces.size() == 1 and ui.cache.tasks.size() == 1, "Workspace and task kept")
	check(cafe.characters.has("ada") and cafe.characters.has("turing"), "Built-in cafe characters stay")
	ui.refresh()
	await settled(ui)
	check(ui.cache.agents.is_empty(), "Refresh does not resurrect deleted agent")
	print("Godot agent delete/cancel/confirmation/live snapshot tests: PASS (", checks, " checks)")
	cafe.queue_free()
	await frames()
	quit(0)

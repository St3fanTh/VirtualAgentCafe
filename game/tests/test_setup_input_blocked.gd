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
	check(ui.visible and ui.tabs.current_tab == 4, "Wizard auto-opened")
	await type_text(ui.setup_objective, "Implement backend and frontend.")
	await click(ui.buttons["Check project"])
	await settled(ui)
	check(not ui.setup_ready, "Blocked namespace cannot start workers")
	check(ui.setup_result.text.contains("FIX · Namespace"), "Sandbox failure shown")
	check(ui.setup_result.text.contains("--privileged"), "Actionable container hint shown")
	check(ui.setup_result.text.contains("SKIP · Codex login not checked"), "Unverified login shown as skipped")
	check(not ui.setup_result.text.contains("FIX · Run docker compose"), "No false authentication failure")
	check(ui.setup_result.text.contains("SKIP · Git not checked"), "Dependent Git check skipped")
	check(ui.buttons["Create backend + frontend team"].disabled, "Unsafe team start remains disabled")
	cafe.queue_free()
	await frames()
	print("Godot blocked sandbox input tests: PASS (", checks, " checks)")
	quit(0)

extends "res://tests/test_gui_input.gd"

# Uses normal viewport mouse/keyboard dispatch against the real HTTP API.
# The backend substitutes only the worker model with a deterministic fixture.
var artifacts := OS.get_environment("VAC_PIPELINE_ARTIFACTS")

func _initialize() -> void:
	create_timer(180).timeout.connect(func():
		push_error("Rendered pipeline exceeded deadline")
		quit(1))
	call_deferred("run")

func screenshot(label: String) -> void:
	await RenderingServer.frame_post_draw
	check(root.get_texture().get_image().save_png(artifacts.path_join(label + ".png")) == OK, "Screenshot saved: " + label)

# FileDialog is an embedded Window with its own viewport coordinates.
# Send ordinary input events to that viewport, never emit control signals.
var input_viewport: Viewport

func click(control: Control, point := Vector2(-1, -1)) -> void:
	var ancestor := control.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			ancestor.ensure_control_visible(control)
		ancestor = ancestor.get_parent()
	await frames()
	input_viewport = control.get_viewport()
	var local_point: Vector2 = control.size / 2 if point.x < 0 else point
	var position := control.get_global_transform_with_canvas() * local_point
	check(input_viewport.get_visible_rect().has_point(position), "Control hit point fits its viewport: " + str(control.name))
	var motion := InputEventMouseMotion.new()
	motion.position = position
	input_viewport.push_input(motion, true)
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = position
		event.global_position = position
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		input_viewport.push_input(event, true)
		await process_frame
	await frames()

func key(code: int, unicode := 0, control := false, shift := false) -> void:
	for pressed in [true, false]:
		var event := InputEventKey.new()
		event.keycode = code
		event.unicode = unicode
		event.ctrl_pressed = control
		event.shift_pressed = shift
		event.pressed = pressed
		input_viewport.push_input(event, true)
	await process_frame

func run() -> void:
	check(DisplayServer.get_name() != "headless", "Requires actual rendered display")
	root.gui_embed_subwindows = true
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	await frames(12)
	var ui = cafe.management
	ui.poll.stop()
	var open_button: Button
	for node in cafe.find_children("*", "Button", true, false):
		if node.text == "Manage agents":
			open_button = node
	check(open_button != null, "Management button exists")
	await screenshot("01-cafe")
	await click(open_button)
	await settled(ui)
	await click(ui.buttons["Setup project"])
	await settled(ui)
	check(ui.chosen(ui.setup_project) == "counter", "Temporary test project discovered")
	await type_text(ui.setup_objective, "Build a counter with increment, decrement and reset; verify all operations with tests.")
	await click(ui.buttons["Check project"])
	await settled(ui)
	check(ui.setup_ready, "Readiness checks passed: " + ui.setup_result.text)
	await screenshot("02-project-ready")
	await click(ui.buttons["Create backend + frontend team"])
	await settled(ui)
	check(ui.cache.agents.size() == 3, "Two workers plus integration configured through UI")
	await tab(ui, 0)
	for identifier in ["counter-backend", "counter-frontend"]:
		var found := false
		for index in ui.agents.item_count:
			if str(ui.agents.get_item_metadata(index)) == identifier:
				await click(ui.agents, ui.agents.get_item_rect(index).get_center())
				found = true
				break
		check(found and ui.active_agent == identifier, "Pointer selected " + identifier)
		await click(ui.buttons["Start agent"])
		await settled(ui)
	await tab(ui, 3)
	await screenshot("03-running")
	var deadline := Time.get_ticks_msec() + 100000
	var integration: Dictionary = {}
	while integration.is_empty() or integration.get("ended_at") == null:
		check(Time.get_ticks_msec() < deadline, "Integration completes before deadline")
		await create_timer(0.2).timeout
		await click(ui.buttons["Connect / Refresh"])
		await settled(ui)
		for execution in ui.cache.get("executions", []):
			if execution.get("agent_id") == "counter-integration":
				integration = execution
	check(integration.get("status") == "COMPLETED", "Integration succeeded: " + str(integration.get("detail")))
	check(integration.get("promotion") == "PROMOTED", "Controller promoted tested product")
	var selected := false
	for index in ui.executions.item_count:
		if str(ui.executions.get_item_metadata(index)) == integration.id:
			await click(ui.executions, ui.executions.get_item_rect(index).get_center())
			selected = true
			break
	await settled(ui)
	check(selected and "promoted to main" in ui.logs.text, "Live logs expose actual promotion")
	await screenshot("04-integration-complete")
	await click(ui.buttons["Download logs"])
	await settled(ui)
	check(ui.diagnostics_dialog.visible, "Download opens save dialog")
	var directory_input: LineEdit
	for edit in ui.diagnostics_dialog.find_children("*", "LineEdit", true, false):
		if edit.text == ui.diagnostics_dialog.current_dir:
			directory_input = edit
	check(directory_input != null, "Save dialog exposes directory navigation")
	await type_text(directory_input, artifacts)
	await key(KEY_ENTER)
	await frames(4)
	check(ui.diagnostics_dialog.current_dir == artifacts, "Directory navigation reaches artifacts folder")
	await type_text(ui.diagnostics_dialog.get_line_edit(), "downloaded-logs.json")
	await screenshot("05-download-dialog")
	check(ui.diagnostics_dialog.get_line_edit().text == "downloaded-logs.json", "Keyboard entered export filename")
	# FileDialog accepts the focused filename with Enter, as a user would.
	await key(KEY_ENTER)
	await frames(4)
	check(FileAccess.file_exists(artifacts.path_join("downloaded-logs.json")), "Save dialog writes downloaded evidence")
	if not FileAccess.file_exists(artifacts.path_join("downloaded-logs.json")):
		return
	var exported = JSON.parse_string(FileAccess.get_file_as_string(artifacts.path_join("downloaded-logs.json")))
	check(exported is Dictionary and exported.execution.id == integration.id, "Downloaded log belongs to selected execution")
	check(not exported.validation_outputs.is_empty(), "Downloaded logs contain shared validation output")
	await click(ui.buttons["Close"])
	await click(cafe.find_child("ChangelogButton", true, false))
	await settled(ui)
	var selected_changelog := false
	for index in ui.changelog_agents.item_count:
		if str(ui.changelog_data[index].id) == "counter-integration":
			await click(ui.changelog_agents, ui.changelog_agents.get_item_rect(index).get_center())
			selected_changelog = true
	check(selected_changelog and not ui.changelog_report.text.is_empty(), "Published integration recap visible")
	await screenshot("06-changelog")
	var result := FileAccess.open(artifacts.path_join("gui-result.json"), FileAccess.WRITE)
	result.store_string(JSON.stringify({"passed": true, "assertions": checks, "execution": integration.id, "commit": integration.promoted.commit, "display": DisplayServer.get_name(), "worker": "deterministic fixture; no live LLM"}, "  "))
	print("Rendered Cafe pipeline GUI: PASS (", checks, " assertions)")
	quit(0)

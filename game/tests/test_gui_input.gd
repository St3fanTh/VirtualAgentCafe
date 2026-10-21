extends SceneTree

# Controls are exercised through the viewport's mouse/keyboard dispatch, never
# by emitting pressed/item_selected or invoking management action handlers.
var cafe: Node
var checks := 0

func _initialize() -> void:
	create_timer(240 if OS.get_environment("VAC_GUI_RENDERED") == "1" else 50).timeout.connect(func():
		push_error("GUI input test exceeded deadline")
		quit(1))
	call_deferred("run")

func check(value: bool, message: String) -> void:
	checks += 1
	if not value:
		push_error("GUI input: " + message)
		quit(1)
		assert(value, message)

func contains(items: Array, key: String, value: String) -> bool:
	for item in items:
		if str(item.get(key, "")) == value:
			return true
	return false

func frames(count := 2) -> void:
	for _index in count:
		await process_frame

func settled(ui: Node) -> void:
	var deadline := Time.get_ticks_msec() + 10000
	while not ui.active_request.is_empty() or not ui.request_queue.is_empty() or ui.pending_refresh:
		check(Time.get_ticks_msec() < deadline, "HTTP action queue timed out: " + ui.notice.text)
		await process_frame
	await frames()

func screen_rect(control: Control) -> Rect2:
	var transform := control.get_global_transform_with_canvas()
	return Rect2(transform * Vector2.ZERO, control.size * transform.get_scale())

func click(control: Control, point := Vector2(-1, -1)) -> void:
	var ancestor := control.get_parent()
	while ancestor != null:
		if ancestor is ScrollContainer:
			ancestor.ensure_control_visible(control)
		ancestor = ancestor.get_parent()
	await frames()
	var local_point: Vector2 = control.size / 2 if point.x < 0 else point
	var position := control.get_global_transform_with_canvas() * local_point
	check(root.get_visible_rect().has_point(position), "Clickable control lies outside viewport: " + str(control.name))
	var motion := InputEventMouseMotion.new()
	motion.position = position
	root.push_input(motion, true)
	for pressed in [true, false]:
		var event := InputEventMouseButton.new()
		event.position = position
		event.global_position = position
		event.button_index = MOUSE_BUTTON_LEFT
		event.pressed = pressed
		root.push_input(event, true)
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
		Input.parse_input_event(event)
		Input.flush_buffered_events()
	await process_frame

func type_text(control: Control, value: String) -> void:
	await click(control)
	await key(KEY_A, 0, true)
	await key(KEY_BACKSPACE)
	for character in value:
		if character == "\n":
			await key(KEY_ENTER, 10)
		else:
			await key(0, character.unicode_at(0))
	await frames()

func select_option(control: OptionButton, index: int) -> void:
	await click(control)
	check(control.get_popup().visible, "Pointer opens dropdown")
	var required_height: float = cafe.management.theme.default_font.get_height(20) * control.item_count + 16
	check(control.get_popup().get_visible_rect().size.y >= required_height, "Dropdown items fit without 4K clipping")
	for _step in control.item_count + 1:
		if control.get_popup().get_focused_item() == index:
			break
		await key(KEY_DOWN)
	await key(KEY_ENTER)
	await frames()
	check(control.selected == index, "Keyboard activates dropdown choice")

func tab(ui: Node, index: int) -> void:
	var bar: TabBar = ui.tabs.get_tab_bar()
	await click(bar, bar.get_tab_rect(index).get_center())
	check(ui.tabs.current_tab == index, "Tab mouse hit test opens page " + str(index))

func run() -> void:
	root.gui_embed_subwindows = true
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	if OS.get_environment("VAC_GUI_RENDERED") == "1":
		cafe.world.hide() # GUI render test isolates the management surface from scene shader load.
	await frames(12)
	var ui = cafe.management
	ui.poll.stop() # Polls are explicitly triggered in the race regression below.
	var open_button: Button
	for node in cafe.find_children("*", "Button", true, false):
		if node is Button and node.text == "Manage agents":
			open_button = node
	check(open_button != null, "Management entry point exists")
	await click(open_button)
	check(ui.visible, "Real pointer opens management panel")
	await settled(ui)
	check(ui.cache.has("agents"), "Authorized connection succeeds")
	for node in cafe.find_children("*", "Button", true, false):
		if node.text == "Atmosphere":
			var before: bool = node.button_pressed
			await click(node)
			check(node.button_pressed == before and ui.visible, "Modal prevents clicks reaching café controls behind it")
	check(root.get_visible_rect().encloses(screen_rect(ui)), "Management modal fits viewport")

	await tab(ui, 2)
	await click(ui.buttons["Create workspace"])
	check(ui.notice_is_error and ui.cache.workspaces.is_empty(), "Invalid form shows feedback and sends no mutation")
	ui.poll.wait_time = 0.02
	ui.poll.start()
	await create_timer(0.2).timeout
	ui.poll.stop()
	await settled(ui)
	check(ui.notice_is_error, "Background refresh does not erase a validation error")
	await type_text(ui.workspace_id, "project")
	# Delayed overview is in flight when the create button receives a pointer click.
	await click(ui.buttons["Connect / Refresh"])
	check(not ui.active_request.is_empty(), "Background request really in flight")
	await click(ui.buttons["Create workspace"])
	await settled(ui)
	check(ui.cache.workspaces.size() == 1, "A click during refresh is executed exactly once")
	check(ui.cache.workspaces[0].id == "project", "Keyboard input reaches workspace field")

	await tab(ui, 1)
	await type_text(ui.definition_file, "task.md")
	await type_text(ui.markdown, "# Task\nCreate a result.")
	await click(ui.buttons["Save Markdown"])
	await settled(ui)
	check(ui.cache.tasks.size() == 1, "Mouse button saves Markdown")
	await select_option(ui.definition_kind, 1)
	await type_text(ui.definition_file, "backend.md")
	await type_text(ui.markdown, "# Backend\nFollow the architecture.")
	await click(ui.buttons["Save Markdown"])
	await settled(ui)
	check(ui.cache.roles.size() == 1, "Role editor saves to the selected definition type")
	await tab(ui, 0)
	await click(ui.buttons["New agent"])
	await type_text(ui.agent_id, "gui-agent")
	await type_text(ui.agent_name, "GUI Engineer")
	# Popup is driven by pointer, keyboard and Enter, not OptionButton.select().
	await select_option(ui.task_file, 1)
	await click(ui.roles, ui.roles.get_item_rect(0).get_center())
	check(ui.chosen(ui.task_file) == "task.md", "Task dropdown keyboard selection works")
	await click(ui.buttons["Save configuration"])
	check(ui.buttons["Save configuration"].disabled, "Pending save disables repeated submit")
	await click(ui.buttons["Save configuration"])
	await settled(ui)
	check(not ui.notice_is_error, "Repeated click does not submit a duplicate agent")
	check(ui.cache.agents.size() == 1, "Mouse button creates one agent")
	check(ui.active_agent == "gui-agent", "Newly saved agent becomes selected automatically")
	check(not ui.buttons["Start agent"].disabled, "Start becomes actionable after saving")
	# Preserve selection and edits across asynchronous polling.
	await type_text(ui.agent_name, "Unsaved name")
	await click(ui.buttons["Connect / Refresh"])
	await settled(ui)
	check(ui.agent_name.text == "Unsaved name" and ui.dirty, "Refresh preserves unsaved fields")
	check(ui.agents.get_selected_items().size() == 1, "Refresh preserves selected agent")
	await click(ui.buttons["Save configuration"])
	await settled(ui)
	check(ui.cache.agents[0].config.name == "Unsaved name", "Saved edit reaches backend")
	await click(ui.buttons["Start agent"])
	await settled(ui)
	var deadline := Time.get_ticks_msec() + 10000
	while ui.cache.agents[0].state != "COMPLETED":
		check(Time.get_ticks_msec() < deadline, "Pointer-started runtime finishes")
		await click(ui.buttons["Connect / Refresh"])
		await settled(ui)
	check(ui.cache.executions[0].runtime_success, "Start button really executes isolated CLI")
	await tab(ui, 3)
	await click(ui.executions, ui.executions.get_item_rect(0).get_center())
	await settled(ui)
	check("CODING" in ui.logs.text and "TESTING" in ui.logs.text, "Execution row click loads actual runtime evidence")
	check(not ui.buttons.has("Accept task") and not ui.buttons.has("Reject task"), "No manual acceptance gate")
	await tab(ui, 1)
	await select_option(ui.definition_kind, 0)
	await type_text(ui.definition_file, "task.md")
	await type_text(ui.markdown, "# Task\nfixture: wait")
	await click(ui.buttons["Save Markdown"])
	await settled(ui)
	await tab(ui, 0)
	await click(ui.buttons["Start agent"])
	await settled(ui)
	check(not ui.buttons["Stop agent"].disabled, "Stop becomes enabled for a running task")
	check(ui.buttons["Delete agent"].disabled, "Running agent cannot be deleted")
	await click(ui.buttons["Stop agent"])
	await settled(ui)
	check(ui.cache.agents[0].state == "CANCELLED", "Stop button cancels the real process")
	await type_text(ui.agent_name, "Saved version")
	await click(ui.buttons["Save configuration"])
	check(not ui.active_request.is_empty(), "Save response deliberately delayed")
	await type_text(ui.agent_name, "Next edit")
	await settled(ui)
	check(ui.cache.agents[0].config.name == "Saved version", "Save sends captured form values")
	check(ui.agent_name.text == "Next edit" and ui.dirty, "Typing during save is preserved for the next save")

	await tab(ui, 2)
	await click(ui.buttons["Initialize Git"])
	await settled(ui)
	check("BRANCH" in ui.git_result.text, "Initialize button creates a local repository")
	await type_text(ui.git_branch, "agent/gui/ui-test")
	await click(ui.buttons["Create branch"])
	await settled(ui)
	check("agent/gui/ui-test" in ui.git_result.text, "Branch button uses the typed branch")
	await type_text(ui.stage_files, "managed-result.txt")
	await click(ui.buttons["Stage selected files"])
	await settled(ui)
	await type_text(ui.commit_message, "feat: record GUI test result")
	await click(ui.buttons["Commit staged changes"])
	await settled(ui)
	check("feat: record GUI test result" in ui.git_result.text, "Commit button commits staged file")
	await click(ui.buttons["View diff"])
	await settled(ui)
	check("no tracked file changes" in ui.git_result.text, "Diff button handles a clean working tree")
	ui.call_api("mutation", "/workspaces", HTTPClient.METHOD_POST, {"id": "old-project"})
	await settled(ui)
	await tab(ui, 0)
	await select_option(ui.task_file, 0)
	await click(ui.buttons["Save configuration"])
	await settled(ui)
	check(ui.chosen(ui.task_file).is_empty(), "Task can be unassigned before deletion")
	await select_option(ui.task_file, 1)
	check(not ui.buttons["Delete selected task"].disabled, "Unassigned task can be deleted")
	await click(ui.buttons["Delete selected task"])
	check(ui.task_delete_dialog.visible, "Task deletion requires confirmation")
	ui.task_delete_dialog.get_ok_button().grab_focus()
	await key(KEY_ENTER)
	check(not ui.task_delete_dialog.visible, "Task confirmation accepts Enter")
	await settled(ui)
	check(ui.cache.tasks.is_empty(), "Confirmed task deletion refreshes the Markdown list: " + ui.notice.text + " · " + str(ui.cache.tasks))
	await tab(ui, 2)
	ui.choose(ui.git_workspace, "old-project")
	await click(ui.buttons["View diff"])
	await settled(ui)
	check("Selected workspace has no Git repository" in ui.git_result.text, "Missing repository error appears in Git panel")
	check(not "no tracked file changes" in ui.git_result.text, "Failed diff clears previous successful result")
	await tab(ui, 0)
	await select_option(ui.workspace, 1)
	check(not ui.buttons["Remove selected workspace"].disabled, "Unused workspace can be removed")
	await click(ui.buttons["Remove selected workspace"])
	check(ui.workspace_delete_dialog.visible, "Workspace removal requires confirmation")
	ui.workspace_delete_dialog.get_ok_button().grab_focus()
	await key(KEY_ENTER)
	await settled(ui)
	check(not contains(ui.cache.workspaces, "id", "old-project"), "Confirmed workspace removal updates the list")
	ui.load_agent(0)
	check(ui.chosen(ui.git_workspace) == "project", "Agent selection chooses its own Git workspace")
	await tab(ui, 2)
	await click(ui.buttons["Inspect repository"])
	await settled(ui)
	check("BRANCH" in ui.git_result.text, "Repository inspection recovers after choosing current workspace")
	for operation in ["fetch", "pull", "push"]:
		check(ui.buttons["Confirm " + operation].disabled, "Unauthorized " + operation + " visibly disabled")
	await click(ui.buttons["Close"])
	check(not ui.visible, "Close works while panel is topmost")
	await click(open_button)
	await settled(ui)
	await key(KEY_ESCAPE)
	check(not ui.visible, "Escape dismisses modal without affecting scene")
	print("Godot pointer/keyboard GUI tests: PASS (", checks, " assertions)")
	quit(0)

extends PanelContainer

var backend_url := "http://127.0.0.1:8000"
var request := HTTPRequest.new()
var token: LineEdit
var notice: Label
var cache: Dictionary = {}
var agents: ItemList
var agent_id: LineEdit
var agent_name: LineEdit
var workspace: OptionButton
var workspace_info: Label
var task_file: OptionButton
var roles: ItemList
var git_enabled: CheckBox
var git_worktree: CheckBox
var repository: OptionButton
var branch: LineEdit
var agent_remote_name: LineEdit
var timeout: SpinBox
var retries: SpinBox
var remote_flags: Dictionary = {}
var definition_kind: OptionButton
var definition_file: LineEdit
var definition_select: OptionButton
var markdown: TextEdit
var git_workspace: OptionButton
var remote: LineEdit
var git_branch: LineEdit
var stage_files: LineEdit
var commit_message: LineEdit
var git_result: TextEdit
var executions: ItemList
var logs: TextEdit
var execution_status: Label
var selected_execution := ""
var log_sequence := 0
var action := ""
var editing := false
var active_agent := ""
var delete_dialog := ConfirmationDialog.new()
var delete_candidate := ""
var project_delete_dialog := ConfirmationDialog.new()
var project_delete_ids: Array[String] = []
var delete_all_projects_pending := false
var pending_agent := ""
var poll := Timer.new()
var tabs: TabContainer
var buttons: Dictionary = {}
var mutation_buttons: Array[Button] = []
var request_queue: Array[Dictionary] = []
var active_request: Dictionary = {}
var dirty := false
var form_revision := 0
var loading_form := false
var pending_refresh := false
var notice_is_error := false
var form_status: Label
var agent_summary: Label
var workspace_id: LineEdit
var remote_name: LineEdit
var tab_keys := ["Agents", "Markdown", "Workspaces", "Executions", "Setup"]
var setup_project: OptionButton
var setup_objective: TextEdit
var setup_result: TextEdit
var setup_status: Label
var setup_remote: CheckBox
var setup_publish: CheckBox
var setup_integrate: CheckBox
var publish_on_success: CheckBox
var setup_ready := false
var setup_checked_project := ""
var setup_documents: Dictionary = {}
var setup_document_project := ""
var setup_document: OptionButton
var setup_document_editor: TextEdit
var setup_file_dialog: FileDialog

const INK := Color("e4ece6")
const MUTED := Color("92a9aa")
const MINT := Color("75d9bb")

func panel_style(fill: Color, border: Color, padding := 18) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(1)
	style.set_corner_radius_all(12)
	for side in ["left", "right", "top", "bottom"]:
		style.set("content_margin_" + side, padding)
	return style

func caption(value: String) -> Label:
	var result := Label.new()
	result.text = value
	result.add_theme_font_size_override("font_size", 18)
	result.add_theme_color_override("font_color", MUTED)
	result.mouse_filter = Control.MOUSE_FILTER_IGNORE
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return result

func line(parent: Node, placeholder: String) -> LineEdit:
	parent.add_child(caption(placeholder))
	var edit := LineEdit.new()
	edit.placeholder_text = placeholder
	edit.custom_minimum_size = Vector2(260, 44)
	edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(edit)
	return edit

func button(parent: Node, text: String, callback: Callable) -> Button:
	var result := Button.new()
	result.text = text
	result.custom_minimum_size.y = 46
	result.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	result.pressed.connect(callback)
	parent.add_child(result)
	if text in ["Save configuration", "Save Markdown", "Create backend + frontend team"]:
		result.add_theme_stylebox_override("normal", panel_style(MINT, MINT, 12))
		result.add_theme_stylebox_override("hover", panel_style(Color("a0ead3"), MINT, 12))
		result.add_theme_color_override("font_color", Color("10292c"))
		result.add_theme_color_override("font_hover_color", Color("10292c"))
	buttons[text] = result
	if text not in ["Close", "Connect / Refresh", "New agent", "New definition", "Load selected", "Refresh execution history", "Setup project", "Find projects"]:
		mutation_buttons.append(result)
	return result

func option(parent: Node, title: String) -> OptionButton:
	parent.add_child(caption(title))
	var result := OptionButton.new()
	var menu := result.get_popup()
	menu.content_scale_factor = 2.0
	menu.about_to_popup.connect(func():
		var row_height := theme.default_font.get_height(theme.default_font_size) + 8
		var height := mini(950, ceili((row_height * menu.item_count + 16) * 2.0))
		menu.min_size = Vector2i(ceili(result.size.x * 2), height)
		menu.max_size = Vector2i(0, height))
	result.custom_minimum_size = Vector2(260, 44)
	result.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(result)
	return result

func column(parent: Node) -> VBoxContainer:
	var result := VBoxContainer.new()
	result.add_theme_constant_override("separation", 10)
	result.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	parent.add_child(result)
	return result

func card(parent: Node, title: String, width := 420) -> VBoxContainer:
	var surface := PanelContainer.new()
	surface.custom_minimum_size.x = width
	surface.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	surface.size_flags_vertical = Control.SIZE_EXPAND_FILL
	surface.add_theme_stylebox_override("panel", panel_style(Color("192b32"), Color("30474e")))
	parent.add_child(surface)
	var shell := column(surface)
	var heading := caption(title)
	heading.add_theme_color_override("font_color", INK)
	heading.add_theme_font_size_override("font_size", 23)
	shell.add_child(heading)
	shell.add_child(HSeparator.new())
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.follow_focus = true
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.custom_minimum_size.y = 250
	shell.add_child(scroll)
	return column(scroll)

func apply_theme() -> void:
	theme = get_parent().theme.duplicate()
	theme.default_font_size = 20
	theme.set_stylebox("panel", "PanelContainer", panel_style(Color("10212a"), Color("57756c"), 22))
	for kind in ["LineEdit", "TextEdit", "ItemList"]:
		theme.set_stylebox("normal" if kind != "ItemList" else "panel", kind, panel_style(Color("0c1922"), Color("304953"), 12))
		theme.set_stylebox("focus", kind, panel_style(Color(0, 0, 0, 0), MINT, 12))
		theme.set_color("font_color", kind, INK)
		theme.set_color("font_placeholder_color", kind, MUTED)
	theme.set_stylebox("panel", "PopupMenu", panel_style(Color("142b33"), Color("547970"), 8))
	theme.set_stylebox("hover", "PopupMenu", panel_style(Color("315851"), MINT, 8))
	theme.set_color("font_color", "PopupMenu", INK)
	theme.set_color("font_hover_color", "PopupMenu", INK)
	theme.set_font("font", "PopupMenu", theme.default_font)
	theme.set_stylebox("selected", "ItemList", panel_style(Color("264e50"), MINT, 10))
	theme.set_stylebox("selected_focus", "ItemList", panel_style(Color("264e50"), MINT, 10))
	for kind in ["Button", "OptionButton"]:
		theme.set_stylebox("normal", kind, panel_style(Color("233c45"), Color("3d5960"), 12))
		theme.set_stylebox("hover", kind, panel_style(Color("31555b"), MINT, 12))
		theme.set_stylebox("pressed", kind, panel_style(Color("3b726b"), MINT, 12))
		theme.set_stylebox("disabled", kind, panel_style(Color("192830"), Color("253a44"), 12))
		theme.set_stylebox("focus", kind, panel_style(Color(0, 0, 0, 0), Color("dbbe87"), 12))
		theme.set_color("font_disabled_color", kind, Color("657b85"))
	theme.set_stylebox("panel", "TabContainer", panel_style(Color("10212a"), Color("10212a"), 8))
	theme.set_stylebox("tab_selected", "TabBar", panel_style(Color("264a4b"), MINT, 14))
	theme.set_stylebox("tab_unselected", "TabBar", panel_style(Color("172e37"), Color("304953"), 14))
	theme.set_color("font_selected_color", "TabBar", INK)
	theme.set_color("font_unselected_color", "TabBar", MUTED)
	for name in ["tab_selected", "tab_unselected"]:
		theme.set_stylebox(name, "TabContainer", theme.get_stylebox(name, "TabBar"))
	for name in ["normal", "pressed", "disabled"]:
		theme.set_stylebox(name, "CheckBox", StyleBoxEmpty.new())
	theme.set_stylebox("hover", "CheckBox", panel_style(Color("203e44"), Color("304953"), 4))
	theme.set_stylebox("focus", "CheckBox", panel_style(Color(0, 0, 0, 0), MINT, 4))

func _ready() -> void:
	position = Vector2(60, 135)
	size = Vector2(1800, 900)
	apply_theme()
	add_child(request)
	request.timeout = 40
	request.request_completed.connect(received)
	var outer := column(self)
	outer.add_theme_constant_override("separation", 16)
	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 16)
	outer.add_child(header)
	var brand := column(header)
	var title := caption("AGENT WORKSPACE")
	title.add_theme_font_size_override("font_size", 32)
	title.add_theme_color_override("font_color", INK)
	brand.add_child(title)
	brand.add_child(caption("Your team. Clear tasks. Observable progress."))
	var connection := HBoxContainer.new()
	connection.alignment = BoxContainer.ALIGNMENT_END
	header.add_child(connection)
	token = LineEdit.new()
	token.placeholder_text = "Management access token"
	token.custom_minimum_size = Vector2(340, 46)
	token.secret = true
	token.text = OS.get_environment("VAC_MANAGEMENT_TOKEN")
	token.text_submitted.connect(func(_text): refresh())
	connection.add_child(token)
	button(connection, "Connect / Refresh", refresh)
	button(connection, "Setup project", open_setup)
	button(connection, "Close", hide)
	notice = caption("Enter your access token, then connect to manage your team.")
	notice.custom_minimum_size.y = 28
	notice.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	outer.add_child(notice)
	tabs = TabContainer.new()
	tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	tabs.custom_minimum_size = Vector2(1700, 650)
	outer.add_child(tabs)
	build_agents(tabs)
	build_definitions(tabs)
	build_git(tabs)
	build_executions(tabs)
	build_setup(tabs)
	bind_form_changes()
	update_buttons()
	add_child(poll)
	poll.wait_time = 3.0
	poll.timeout.connect(poll_updates)
	poll.start()
	hide()
	if OS.get_environment("VAC_OPEN_SETUP") == "1":
		call_deferred("open_setup")

func page(parent_tabs: TabContainer, title: String) -> HBoxContainer:
	var page_margin := MarginContainer.new()
	page_margin.name = title
	parent_tabs.add_child(page_margin)
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 16)
	page_margin.add_child(row)
	return row

func build_agents(tabs: TabContainer) -> void:
	var row := page(tabs, "Agents")
	var left := card(row, "Your agents", 390)
	agents = ItemList.new()
	agents.custom_minimum_size = Vector2(350, 300)
	agents.item_selected.connect(load_agent)
	left.add_child(agents)
	agent_summary = caption("Select a teammate to see its task, roles and workspace.")
	agent_summary.custom_minimum_size = Vector2(300, 85)
	agent_summary.max_lines_visible = 6
	left.add_child(agent_summary)
	var new_button := button(left, "New agent", new_agent)
	left.move_child(new_button, 0)
	var middle := card(row, "Identity & instructions", 490)
	agent_id = line(middle, "Agent ID, e.g. backend-agent")
	agent_name = line(middle, "Agent name")
	workspace = option(middle, "Assigned workspace")
	workspace_info = caption("Select an approved workspace")
	workspace_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	workspace_info.custom_minimum_size.x = 320
	middle.add_child(workspace_info)
	workspace.item_selected.connect(func(_index): update_workspace_info())
	task_file = option(middle, "Markdown task")
	middle.add_child(caption("Roles — select multiple with Ctrl"))
	roles = ItemList.new()
	roles.select_mode = ItemList.SELECT_MULTI
	roles.custom_minimum_size = Vector2(350, 130)
	middle.add_child(roles)
	var settings := card(row, "Execution & Git", 480)
	git_enabled = CheckBox.new()
	git_enabled.text = "Use Git"
	settings.add_child(git_enabled)
	git_worktree = CheckBox.new()
	git_worktree.text = "Separate Git worktree"
	git_worktree.button_pressed = true
	settings.add_child(git_worktree)
	repository = option(settings, "Source repository workspace")
	branch = line(settings, "Branch (blank = agent/ID/task)")
	agent_remote_name = line(settings, "Git remote name")
	agent_remote_name.text = "origin"
	settings.add_child(caption("Timeout in seconds / retries"))
	timeout = SpinBox.new()
	timeout.min_value = 1
	timeout.max_value = 3600
	timeout.value = 300
	settings.add_child(timeout)
	retries = SpinBox.new()
	retries.max_value = 2
	settings.add_child(retries)
	publish_on_success = CheckBox.new()
	publish_on_success.text = "Publish committed results after successful execution"
	settings.add_child(publish_on_success)
	for name in ["fetch", "pull", "push"]:
		var flag := CheckBox.new()
		flag.text = "Allow " + name
		settings.add_child(flag)
		remote_flags[name] = flag
	publish_on_success.toggled.connect(func(enabled):
		if enabled:
			remote_flags.push.button_pressed = true)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 10)
	var outer = tabs.get_parent()
	outer.add_child(actions)
	outer.move_child(actions, outer.get_child_count() - 1)
	form_status = caption("Choose an agent or create a new one.")
	form_status.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	form_status.autowrap_mode = TextServer.AUTOWRAP_OFF
	form_status.clip_text = true
	form_status.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	actions.add_child(form_status)
	button(actions, "Save configuration", save_agent)
	tabs.tab_changed.connect(func(index): actions.visible = index == 0)
	button(actions, "Start agent", func(): control("start"))
	button(actions, "Stop agent", func(): control("stop"))
	button(actions, "Restart agent", func(): control("restart"))
	button(left, "Delete agent", ask_delete_agent)
	delete_dialog.title = "Delete agent"
	delete_dialog.ok_button_text = "Delete agent"
	delete_dialog.dialog_autowrap = true
	delete_dialog.theme = theme
	delete_dialog.confirmed.connect(confirm_delete_agent)
	delete_dialog.canceled.connect(func(): delete_candidate = "")
	add_child(delete_dialog)

func build_definitions(tabs: TabContainer) -> void:
	var row := page(tabs, "Markdown")
	var files := card(row, "Definition library", 350)
	definition_kind = option(files, "Definition type")
	definition_kind.add_item("tasks")
	definition_kind.add_item("roles")
	definition_kind.item_selected.connect(func(_index): populate_definitions())
	definition_select = option(files, "Existing definitions")
	button(files, "Load selected", load_definition)
	definition_file = line(files, "Filename, e.g. implement-login.md")
	button(files, "New definition", func():
		definition_file.text = ""
		markdown.text = "# Task or Role\n\n## Objective\n\n## Acceptance Criteria\n")
	button(files, "Save Markdown", save_definition)
	var editor := card(row, "Markdown editor", 970)
	editor.add_child(caption("Markdown is the source of truth; changes apply to the next execution."))
	markdown = TextEdit.new()
	markdown.custom_minimum_size = Vector2(750, 440)
	editor.add_child(markdown)

func build_git(tabs: TabContainer) -> void:
	var row := page(tabs, "Workspaces")
	var inputs := card(row, "Workspace & repository", 510)
	workspace_id = line(inputs, "New workspace ID")
	button(inputs, "Create workspace", create_workspace)
	git_workspace = option(inputs, "Workspace to inspect / edit")
	git_workspace.item_selected.connect(func(_index): update_buttons())
	button(inputs, "Inspect repository", func(): git_read("git"))
	button(inputs, "View diff", func(): git_read("diff"))
	button(inputs, "Initialize Git", func(): git_mutate({"operation": "init"}))
	button(inputs, "Connect existing Git repository", func(): git_mutate({"operation": "connect"}))
	remote = line(inputs, "SSH or HTTPS remote URL")
	remote_name = line(inputs, "Remote name")
	remote_name.text = "origin"
	button(inputs, "Configure Git remote", func():
		git_mutate({"operation": "remote", "remote": remote.text, "remote_name": remote_name.text}))
	button(inputs, "Clone remote (explicit action)", func():
		git_mutate({"operation": "clone", "remote": remote.text, "confirmed": true}))
	git_branch = line(inputs, "Branch name")
	var branch_actions := HBoxContainer.new()
	inputs.add_child(branch_actions)
	button(branch_actions, "Create branch", func(): git_mutate({"operation": "branch", "branch": git_branch.text}))
	button(branch_actions, "Switch branch", func(): git_mutate({"operation": "switch", "branch": git_branch.text}))
	stage_files = line(inputs, "Files to stage, separated by commas")
	button(inputs, "Stage selected files", func():
		var paths: Array = []
		for value in stage_files.text.split(",", false):
			paths.append(value.strip_edges())
		git_mutate({"operation": "stage", "files": paths}))
	commit_message = line(inputs, "Commit message")
	button(inputs, "Commit staged changes", func():
		git_mutate({"operation": "commit", "message": commit_message.text}))
	var output := card(row, "Changes & history", 920)
	output.add_child(caption("Git results — stop agents before changing their working trees."))
	git_result = TextEdit.new()
	git_result.editable = false
	git_result.custom_minimum_size = Vector2(740, 450)
	output.add_child(git_result)
	var remotes := HBoxContainer.new()
	output.add_child(remotes)
	for operation in ["fetch", "pull", "push"]:
		button(remotes, "Confirm " + operation, func():
			git_mutate({"operation": operation, "agent_id": active_agent, "confirmed": true}))

func build_executions(tabs: TabContainer) -> void:
	var row := page(tabs, "Executions")
	var list_column := card(row, "Execution timeline", 410)
	executions = ItemList.new()
	executions.custom_minimum_size = Vector2(340, 430)
	executions.item_selected.connect(func(index):
		selected_execution = str(executions.get_item_metadata(index))
		log_sequence = 0
		logs.text = ""
		call_api("logs", "/executions/" + selected_execution + "/logs"))
	list_column.add_child(executions)
	button(list_column, "Refresh execution history", func():
		selected_execution = ""
		refresh())
	var monitor := card(row, "Live activity & integration", 950)
	monitor.add_child(caption("Observed execution, shared requirements checks and main promotion."))
	execution_status = caption("Select an execution to monitor its current status.")
	execution_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	monitor.add_child(execution_status)
	logs = TextEdit.new()
	logs.editable = false
	logs.custom_minimum_size = Vector2(760, 360)
	monitor.add_child(logs)
	monitor.add_child(caption("Team runs integrate automatically. Main is updated only after shared requirements tests pass."))
	button(monitor, "Retry team integration", retry_integration)

func show_agent(identifier: String) -> void:
	tabs.current_tab = 0
	pending_agent = identifier
	show_management()

func show_management() -> void:
	get_parent().move_child(self, -1)
	show()
	if not token.text.is_empty():
		refresh()

func refresh() -> void:
	call_api("overview", "")

func poll_updates() -> void:
	if not visible or token.text.strip_edges().is_empty() or not active_request.is_empty() or not request_queue.is_empty():
		return
	# Rebuilding popup/list widgets while they hold the mouse interrupts a click.
	for popup in [workspace, task_file, repository, git_workspace, definition_kind, definition_select]:
		if popup.get_popup().visible:
			return
	if not selected_execution.is_empty():
		call_api("logs", "/executions/" + selected_execution + "/logs?after=" + str(log_sequence), HTTPClient.METHOD_GET, {}, true)
	else:
		call_api("overview", "", HTTPClient.METHOD_GET, {}, true)

func call_api(next_action: String, path: String, method := HTTPClient.METHOD_GET, body: Dictionary = {}, background := false) -> void:
	var command := {"action": next_action, "path": path, "method": method,
		"body": body.duplicate(true), "execution": selected_execution, "revision": form_revision, "background": background}
	if method != HTTPClient.METHOD_GET:
		var previous: Dictionary = request_queue.back() if not request_queue.is_empty() else active_request
		if not previous.is_empty() and previous.get("path") == path and previous.get("method") == method and previous.get("body") == body:
			return
	if request_queue.size() >= 16:
		set_notice("Please wait for the queued actions to finish.", true)
		return
	request_queue.append(command)
	update_buttons()
	# Commands are queued even if a poll is in flight. No clicks silently disappear.
	dispatch_next()

func dispatch_next() -> void:
	if not active_request.is_empty() or request_queue.is_empty():
		return
	active_request = request_queue.pop_front()
	action = active_request.action
	var method: int = active_request.method
	var headers := PackedStringArray(["Content-Type: application/json", "Authorization: Bearer " + token.text.strip_edges()])
	var result := request.request(backend_url + "/management" + str(active_request.path), headers, method,
		"" if method == HTTPClient.METHOD_GET else JSON.stringify(active_request.body))
	if result != OK:
		var failed := active_request.duplicate(true)
		active_request = {}
		request_error(failed, "Unable to contact backend. Check the connection and try again.")
		call_deferred("dispatch_next")
	else:
		if method != HTTPClient.METHOD_GET:
			set_notice("Checking project…" if action == "setup_check" else "Applying your changes…")
	update_buttons()

func set_notice(message: String, error := false) -> void:
	notice_is_error = error
	notice.text = message
	notice.add_theme_color_override("font_color", Color("f1959e") if error else MUTED)

func received(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var completed := active_request.duplicate(true)
	active_request = {}
	var data = JSON.parse_string(body.get_string_from_utf8())
	if code < 200 or code >= 300 or not data is Dictionary:
		var message := "Access token not accepted. Check your token and reconnect." if code == 401 else "Request failed: " + str(data.get("detail", "Backend unavailable") if data is Dictionary else "Backend unavailable")
		if _result == HTTPRequest.RESULT_TIMEOUT:
			message = "Request timed out. Check the backend and retry; disable the optional remote check first."
		request_error(completed, message)
		update_buttons()
		call_deferred("after_response")
		return
	var finished_action: String = completed.get("action", action)
	if finished_action == "setup_projects":
		fill_options(setup_project, data.get("projects", []))
		if not OS.get_environment("VAC_SETUP_PROJECT").is_empty():
			choose(setup_project, OS.get_environment("VAC_SETUP_PROJECT"))
		setup_ready = false
		setup_result.text = "Select your project, describe the goal and run Check project.\n\nApproved folder: " + str(data.get("approved_root", "")) + "\n\nProject missing? Run scripts/setup-project.py on your Docker host to select and mount its folder."
	elif finished_action in ["setup_docs_load", "setup_docs_save"]:
		if str(data.get("project", "")) == chosen(setup_project):
			setup_documents = data.get("documents", {})
			setup_document_project = str(data.project)
			if finished_action == "setup_docs_load":
				show_setup_document()
			set_notice("Project documents loaded." if finished_action == "setup_docs_load" else "Project document saved. Next agent runs receive the new snapshot.")
	elif finished_action == "setup_check":
		setup_checked_project = str(data.get("project", ""))
		setup_ready = bool(data.get("ready", false)) and setup_checked_project == chosen(setup_project)
		setup_feedback("Checks passed." if setup_ready else "Project blocked: resolve the FIX items in the report.", not setup_ready)
		setup_result.text = "PROJECT · " + setup_checked_project + "\n\n"
		for entry in data.get("checks", []):
			var prefix := "SKIP · " if entry.get("status", "") == "SKIPPED" else "PASS · " if entry.get("ok", false) else "FIX · "
			setup_result.text += prefix + str(entry.get("detail", "")) + "\n\n"
		setup_result.text += "Branch: " + str(data.get("git", {}).get("branch", "")) + "\nOrigin: " + str(data.get("remote", "")) + "\n" + str(data.get("remote_status", "")) + "\n\n" + str(data.get("dirty_warning", ""))
	elif finished_action == "setup_team":
		setup_feedback("Team ready. Open Agents to start each worker.")
		var publication_hint := "Publishing disabled. Enable it in Agents or rerun team setup with publication selected."
		if data.get("publish_results", false):
			publication_hint = "Successful runs will push their own branches. Shared integration disabled."
		if data.get("auto_integrate", false):
			publication_hint = "Automatic shared integration, requirements tests and main promotion enabled."
		setup_result.text = "TEAM READY\n\n" + "\n".join(data.get("agents", [])) + "\n\nTwo persistent worktrees and branches are ready. Worker files are saved there, not in your source folder. Start new worker runs from Agents; enabled integration uses ready published results automatically.\n\nNext: open Agents, review each Markdown task and its interface contract, then Start agent. Monitor execution logs and the shared test results. " + publication_hint
		setup_ready = false
		pending_refresh = true
		if data.get("auto_integrate", false):
			setup_result.text += "\n\nAUTOMATIC INTEGRATION ENABLED\nAfter both worker pushes, the integration/test worker merges their commits, builds the common requirements test plan, reruns its suites and promotes the green commit to main. No manual task acceptance."
		set_notice("Project configured. Start your workers in Agents.")
	elif finished_action == "overview":
		cache = data
		populate()
		if not bool(completed.get("background", false)) or not notice_is_error:
			set_notice("Connected · " + str(cache.get("agents", []).size()) + " agents · " + str(cache.get("workspaces", []).size()) + " workspaces")
	elif finished_action == "git":
		if data.has("diff"):
			git_result.text = str(data.diff) if not str(data.diff).is_empty() else "Working tree has no tracked file changes."
		else:
			git_result.text = "REPOSITORY\n" + str(data.get("repository", "")) + "\n\nBRANCH\n" + str(data.get("branch", "")) + "\n\nMODIFIED FILES\n" + ("\n".join(data.get("modified_files", [])) if not data.get("modified_files", []).is_empty() else "No changes") + "\n\nRECENT COMMITS\n" + ("\n".join(data.get("history", [])) if not data.get("history", []).is_empty() else "No commits yet")
		set_notice("Repository information updated.")
	elif finished_action == "logs" and completed.get("execution", "") == selected_execution:
		cache["projects"] = data.get("projects", cache.get("projects", []))
		var record: Dictionary = data.get("execution", {})
		execution_status.text = str(record.get("status", "")) + " · " + str(record.get("acceptance", "")) + " · Git: " + str(record.get("publication", "NOT_REQUESTED")) + " · Main: " + str(record.get("promotion", "NOT_PROMOTED")) + "\nFiles saved in: " + str(record.get("workspace_path", "")) + " · Branch: " + str(record.get("branch", ""))
		var published: Dictionary = record.get("published", {})
		if not published.is_empty():
			execution_status.text += "\nPushed: " + str(published.get("branch", "")) + " · " + str(published.get("commit", ""))
		var changelog := str(record.get("changelog", "")).strip_edges()
		if not changelog.is_empty():
			execution_status.text += "\n\nRECAP\n" + changelog.left(1400)
		if record.has("validation"):
			var validation: Dictionary = record.validation
			execution_status.text += "\nRequirements: " + str(validation.get("requirements", []).size()) + " · Shared tests: " + ("PASS" if validation.get("passed", false) else "FAIL")
		for entry in data.get("logs", []):
			if int(entry.get("sequence", 0)) <= log_sequence:
				continue
			log_sequence = int(entry.sequence)
			logs.text += str(entry.get("timestamp", "")).substr(11, 8) + "  " + str(entry.get("type", "")).trim_prefix("agent.").to_upper() + "\n" + str(entry.get("detail", "")) + "\n\n"
		logs.text = logs.text.right(48000)
		for project in cache.get("projects", []):
			if record.get("agent_id", "") in project.get("agents", []) or record.get("agent_id", "") == project.get("integrator", ""):
				var integration: Dictionary = project.get("integration", {})
				execution_status.text += "\nTeam: " + str(integration.get("status", "NOT_CONFIGURED")) + " · " + str(integration.get("detail", ""))
	elif finished_action in ["delete_project", "delete_projects"]:
		var removed_ids := project_delete_ids.duplicate()
		var removed_agents: Array = []
		var removed_workspaces: Array = []
		var remaining_projects: Array = []
		for project in cache.get("projects", []):
			if str(project.get("id", "")) not in removed_ids:
				remaining_projects.append(project)
			else:
				removed_agents.append_array(project.get("agents", []))
				if not str(project.get("integrator", "")).is_empty():
					removed_agents.append(str(project.integrator))
		cache["projects"] = remaining_projects
		for agent in cache.get("agents", []):
			if str(agent.get("config", {}).get("id", "")) in removed_agents:
				removed_workspaces.append(str(agent.get("config", {}).get("workspace", "")))
		cache["agents"] = cache.get("agents", []).filter(func(agent):
			return str(agent.get("config", {}).get("id", "")) not in removed_agents)
		cache["workspaces"] = cache.get("workspaces", []).filter(func(item):
			return str(item.get("id", "")) not in removed_workspaces)
		project_delete_ids.clear()
		delete_all_projects_pending = false
		setup_ready = false
		setup_result.text = "Project management entries and clean worker worktrees removed. Source repositories, Git branches and execution history kept."
		set_notice("Managed project and assigned worker workspaces deleted; source repository kept.")
		populate()
		call_api("setup_projects", "/setup")
	elif finished_action == "delete_agent":
		var removed := str(data.get("id", ""))
		if pending_agent == removed:
			pending_agent = ""
		if active_agent == removed:
			new_agent()
		set_notice("Agent deleted. Workspace, Git branches, Markdown and execution history kept.")
		pending_refresh = true
	elif finished_action in ["mutation", "control", "review"]:
		if finished_action == "mutation" and data.has("config") and str(completed.get("path", "")).begins_with("/agents") and completed.get("method") in [HTTPClient.METHOD_PUT, HTTPClient.METHOD_POST]:
			if int(completed.get("revision", -1)) == form_revision:
				dirty = false
				active_agent = str(data.config.id)
				editing = true
				agent_id.editable = false
				pending_agent = active_agent
		set_notice("Changes saved." if finished_action == "mutation" else "Action completed.")
		# Re-fetch only after the next queued user action; keep actions ahead of polls.
		pending_refresh = true
	if finished_action.begins_with("setup"):
		setup_result.scroll_vertical = 0
	update_buttons()
	call_deferred("after_response")

func after_response() -> void:
	if not request_queue.is_empty():
		dispatch_next()
	elif pending_refresh:
		pending_refresh = false
		call_api("overview", "", HTTPClient.METHOD_GET, {}, true)

func bind_form_changes() -> void:
	for edit in [agent_id, agent_name, branch, agent_remote_name]:
		edit.text_changed.connect(func(_value): mark_dirty())
	for select in [workspace, task_file, repository]:
		select.item_selected.connect(func(_index): mark_dirty())
	for checkbox in [git_enabled, git_worktree, publish_on_success] + remote_flags.values():
		checkbox.toggled.connect(func(_enabled): mark_dirty())
	for spinner in [timeout, retries]:
		spinner.value_changed.connect(func(_value): mark_dirty())
	roles.multi_selected.connect(func(_index, _selected): mark_dirty())

func mark_dirty() -> void:
	if loading_form:
		return
	dirty = true
	form_revision += 1
	form_status.text = "Unsaved configuration"
	form_status.add_theme_color_override("font_color", Color("e6bf7d"))
	update_buttons()

func update_buttons() -> void:
	var busy := not active_request.is_empty() and int(active_request.get("method", HTTPClient.METHOD_GET)) != HTTPClient.METHOD_GET
	for queued in request_queue:
		if int(queued.method) != HTTPClient.METHOD_GET:
			busy = true
	for node in mutation_buttons:
		node.disabled = busy
	if setup_project != null:
		buttons["Create backend + frontend team"].disabled = busy or not setup_ready or chosen(setup_project) != setup_checked_project or setup_goal().length() < 10
		var managed_ids: Array = []
		for project in cache.get("projects", []):
			managed_ids.append(project.get("id", ""))
		buttons["Delete selected project"].disabled = busy or not managed_ids.has(chosen(setup_project))
		buttons["Delete all managed projects"].disabled = busy or managed_ids.is_empty()
		buttons["Check project"].disabled = busy or chosen(setup_project).is_empty()
		var checking := str(active_request.get("action", "")) == "setup_check"
		for queued in request_queue:
			checking = checking or str(queued.action) == "setup_check"
		buttons["Check project"].text = "Checking…" if checking else "Check project"
		if setup_ready and not busy:
			if setup_goal().length() < 10:
				setup_feedback("Checks passed. Enter a goal (at least 10 characters) or load PLANNING.md.")
			else:
				setup_feedback("Checks passed. Create your team." + (" Using the next milestone from PLANNING.md." if setup_objective.text.strip_edges().is_empty() else ""))
		buttons["Create backend + frontend team"].tooltip_text = "Run Check project and resolve all FIX items first." if not setup_ready else "Enter a goal or load PLANNING.md." if setup_goal().length() < 10 else "Create workers and optionally enable shared integration."
		buttons["Load project documents"].disabled = busy or chosen(setup_project).is_empty()
		buttons["Save project document"].disabled = busy or setup_document_project != chosen(setup_project) or setup_documents.is_empty()
		buttons["Import Markdown file"].disabled = busy or setup_document_project != chosen(setup_project) or setup_documents.is_empty()
		setup_document_editor.editable = not busy and setup_document_project == chosen(setup_project) and not setup_documents.is_empty()
	var running := false
	var ready := false
	var selected: Dictionary = {}
	for record in cache.get("agents", []):
		if record.config.id == active_agent:
			running = record.state == "RUNNING"
			ready = record.config.get("task") != null
			selected = record.config
	buttons["Start agent"].disabled = busy or active_agent.is_empty() or running or not ready or dirty
	buttons["Stop agent"].disabled = busy or active_agent.is_empty() or not running
	buttons["Restart agent"].disabled = busy or active_agent.is_empty() or not ready or dirty
	var automatic := bool(selected.get("execution", {}).get("integration_validation", false))
	buttons["Start agent"].disabled = buttons["Start agent"].disabled or automatic
	buttons["Restart agent"].disabled = buttons["Restart agent"].disabled or automatic
	buttons["Delete agent"].disabled = busy or running or active_agent.is_empty()
	buttons["Delete agent"].tooltip_text = "Stop the agent before deleting it." if running else "Remove this agent; keep its workspace, Git branches and history."
	buttons["Save configuration"].disabled = busy or running
	var can_retry := false
	for execution in cache.get("executions", []):
		if execution.id == selected_execution:
			for project in cache.get("projects", []):
				if project.get("auto_integrate", false) and (execution.agent_id in project.get("agents", []) or execution.agent_id == project.get("integrator", "")):
					can_retry = project.get("integration", {}).get("status", "") != "RUNNING"
	buttons["Retry team integration"].disabled = busy or not can_retry
	buttons["Start agent"].tooltip_text = "Save your changes before starting." if dirty else "Run the assigned Markdown task."
	if automatic:
		buttons["Start agent"].tooltip_text = "Starts automatically after both worker branches are published. Use Retry team integration after a failure."
	buttons["Stop agent"].tooltip_text = "Cancel the running task." if running else "This agent has no active task."
	buttons["Save configuration"].tooltip_text = "Stop the agent before editing its configuration." if running else "Save this agent and its assignments."
	var capabilities: Dictionary = cache.get("capabilities", {})
	if not bool(capabilities.get("can_start", true)):
		buttons["Start agent"].disabled = true
		buttons["Start agent"].tooltip_text = "Use live Codex mode to run agents."
		buttons["Restart agent"].disabled = true
	for operation in ["fetch", "pull", "push"]:
		buttons["Confirm " + operation].disabled = busy or not bool(capabilities.get("remote_git", false)) or not bool(selected.get("git", {}).get("allow_" + operation, false)) or not bool(selected.get("git", {}).get("enabled", false)) or chosen(git_workspace) != str(selected.get("workspace", ""))
	buttons["Clone remote (explicit action)"].disabled = busy or not bool(capabilities.get("remote_git", false))

func fill_options(target: OptionButton, values: Array, empty := false) -> void:
	var previous := chosen(target)
	var expected: Array = ["(none)"] if empty else []
	expected.append_array(values)
	var existing: Array = []
	for index in target.item_count:
		existing.append(target.get_item_text(index))
	if existing == expected:
		return
	target.clear()
	if empty:
		target.add_item("(none)")
	for value in values:
		target.add_item(str(value))
	choose(target, previous)

func sync_list(list: ItemList, rows: Array) -> void:
	var selected: Array = []
	for index in list.get_selected_items():
		selected.append(list.get_item_metadata(index))
	var same_ids := list.item_count == rows.size()
	if same_ids:
		for index in rows.size():
			if list.get_item_metadata(index) != rows[index].id:
				same_ids = false
	if not same_ids:
		list.clear()
	for index in rows.size():
		if same_ids:
			if list.get_item_text(index) != rows[index].text:
				list.set_item_text(index, rows[index].text)
		else:
			list.add_item(rows[index].text)
			list.set_item_metadata(index, rows[index].id)
			if rows[index].id in selected:
				list.select(index, false)

func populate() -> void:
	var agent_rows: Array = []
	for item in cache.get("agents", []):
		var config: Dictionary = item.config
		agent_rows.append({"id": config.id, "text": str(config.name) + " · " + str(item.state).capitalize()})
	sync_list(agents, agent_rows)
	if editing and not active_agent.is_empty():
		var still_present := false
		for row in agent_rows:
			still_present = still_present or str(row.id) == active_agent
		if not still_present:
			new_agent()
	var spaces: Array = []
	for item in cache.get("workspaces", []):
		spaces.append(item.id)
	fill_options(workspace, spaces)
	update_workspace_info()
	fill_options(repository, spaces, true)
	fill_options(git_workspace, spaces)
	var tasks: Array = []
	for item in cache.get("tasks", []):
		tasks.append(item.file)
	fill_options(task_file, tasks, true)
	var role_rows: Array = []
	for item in cache.get("roles", []):
		role_rows.append({"id": item.file, "text": str(item.file)})
	sync_list(roles, role_rows)
	populate_definitions()
	if not pending_agent.is_empty() and not dirty:
		for index in agents.item_count:
			if str(agents.get_item_metadata(index)) == pending_agent:
				agents.select(index)
				load_agent(index)
				pending_agent = ""
				break
	var execution_rows: Array = []
	var history: Array = cache.get("executions", []).duplicate()
	history.reverse()
	for item in history:
		execution_rows.append({"id": item.id, "text": str(item.agent_id) + " · " + str(item.status).capitalize()})
	sync_list(executions, execution_rows)
	update_buttons()

func update_workspace_info() -> void:
	for item in cache.get("workspaces", []):
		if item.id == chosen(workspace):
			workspace_info.text = str(item.path)

func chosen(target: OptionButton) -> String:
	if target.selected < 0:
		return ""
	var text := target.get_item_text(target.selected)
	return "" if text == "(none)" else text

func choose(target: OptionButton, text: String) -> void:
	for index in target.item_count:
		if target.get_item_text(index) == text:
			target.select(index)
			return
	if target.item_count > 0:
		target.select(0)

func new_agent() -> void:
	pending_agent = ""
	form_revision += 1
	loading_form = true
	dirty = false
	agents.deselect_all()
	editing = false
	active_agent = ""
	agent_id.editable = true
	agent_id.text = ""
	agent_name.text = ""
	branch.text = ""
	git_enabled.button_pressed = false
	git_worktree.button_pressed = true
	agent_remote_name.text = "origin"
	timeout.value = 300
	retries.value = 0
	roles.deselect_all()
	publish_on_success.button_pressed = false
	for flag in remote_flags.values():
		flag.button_pressed = false
	loading_form = false
	agent_summary.text = "New teammate\nAssign a workspace, task and roles, then save.\nYou can start the saved agent immediately."
	form_status.text = "New agent · save to add it to your team"
	update_buttons()

func load_agent(index: int) -> void:
	pending_agent = ""
	form_revision += 1
	loading_form = true
	dirty = false
	agents.select(index)
	active_agent = str(agents.get_item_metadata(index))
	for record in cache.get("agents", []):
		var config: Dictionary = record.config
		if config.id != active_agent:
			continue
		editing = true
		agent_id.editable = false
		agent_id.text = config.id
		agent_name.text = config.name
		choose(workspace, config.workspace)
		choose(git_workspace, config.workspace)
		update_workspace_info()
		choose(task_file, str(config.get("task", "")))
		roles.deselect_all()
		for role_index in roles.item_count:
			if roles.get_item_text(role_index) in config.roles:
				roles.select(role_index, false)
		git_enabled.button_pressed = config.git.enabled
		git_worktree.button_pressed = bool(config.git.get("worktree", true))
		choose(repository, str(config.git.get("repository", "")))
		agent_remote_name.text = str(config.git.get("remote_name", "origin"))
		publish_on_success.button_pressed = bool(config.git.get("push_on_success", false))
		branch.text = str(config.git.get("branch", "")) if config.git.get("branch") != null else ""
		timeout.value = config.execution.timeout_seconds
		retries.value = config.execution.max_retries
		for operation in remote_flags:
			remote_flags[operation].button_pressed = bool(config.git.get("allow_" + operation, false))
		agent_summary.text = "ID: " + str(config.id) + "\n" + str(config.get("task", "No task")) + "\nRoles: " + ", ".join(config.roles) + "\nWorkspace: " + str(config.workspace)
		notice.text = "Workspace: " + config.workspace + " · " + str(record.state) + " · Task: " + str(record.get("task_state", ""))

	loading_form = false
	form_status.text = agent_name.text + " · configuration loaded"
	form_status.add_theme_color_override("font_color", MUTED)
	update_buttons()

func save_agent() -> void:
	var identifier := RegEx.new()
	identifier.compile("^[a-z][a-z0-9_-]{0,63}$")
	if identifier.search(agent_id.text) == null or agent_id.text in ["ada", "turing"]:
		set_notice("Choose a new agent ID: lowercase letters, numbers, hyphens or underscores.", true)
		agent_id.grab_focus()
		return
	if agent_name.text.strip_edges().is_empty() or chosen(workspace).is_empty():
		set_notice("Enter an agent name and select a workspace before saving.", true)
		return
	if git_enabled.button_pressed and chosen(repository).is_empty():
		set_notice("Select a source repository, or turn off Git for this agent.", true)
		return
	var assigned_roles: Array = []
	for index in roles.get_selected_items():
		assigned_roles.append(roles.get_item_text(index))
	var git := {"enabled": git_enabled.button_pressed, "repository": chosen(repository) if git_enabled.button_pressed else null, "branch": branch.text if not branch.text.is_empty() else null}
	git["remote_name"] = agent_remote_name.text
	git["worktree"] = git_worktree.button_pressed
	git["push_on_success"] = publish_on_success.button_pressed
	for operation in remote_flags:
		git["allow_" + operation] = remote_flags[operation].button_pressed
	var execution := {}
	for record in cache.get("agents", []):
		if record.config.id == active_agent:
			execution = record.config.execution.duplicate(true)
	execution["timeout_seconds"] = int(timeout.value)
	execution["max_retries"] = int(retries.value)
	var config := {"id": agent_id.text, "name": agent_name.text, "workspace": chosen(workspace), "task": chosen(task_file) if not chosen(task_file).is_empty() else null, "roles": assigned_roles, "git": git, "execution": execution}
	call_api("mutation", "/agents/" + agent_id.text if editing else "/agents", HTTPClient.METHOD_PUT if editing else HTTPClient.METHOD_POST, config)

func ask_delete_agent() -> void:
	if active_agent.is_empty():
		return
	delete_candidate = active_agent
	delete_dialog.dialog_text = "Delete agent '" + delete_candidate + "' from management?\n\nWorkspace, Git branches, Markdown and execution history will be kept. Automatic integration for its team will be disabled. Stop all team workers first."
	delete_dialog.popup_centered(Vector2i(760, 280))

func confirm_delete_agent() -> void:
	if delete_candidate.is_empty():
		return
	var identifier := delete_candidate
	delete_candidate = ""
	call_api("delete_agent", "/agents/" + identifier, HTTPClient.METHOD_DELETE, {"confirmed": true})

func control(operation: String) -> void:
	if active_agent.is_empty():
		notice.text = "Save and select an agent first."
		return
	call_api("control", "/agents/" + active_agent + "/" + operation, HTTPClient.METHOD_POST)

func populate_definitions() -> void:
	var values: Array = []
	for item in cache.get(chosen(definition_kind), []):
		values.append(item.file)
	fill_options(definition_select, values)

func load_definition() -> void:
	for item in cache.get(chosen(definition_kind), []):
		if item.file == chosen(definition_select):
			definition_file.text = item.file
			markdown.text = item.content

func create_workspace() -> void:
	var pattern := RegEx.new()
	pattern.compile("^[a-z][a-z0-9_-]{0,63}$")
	if pattern.search(workspace_id.text) == null:
		set_notice("Enter a workspace ID using lowercase letters, numbers, hyphens or underscores.", true)
		workspace_id.grab_focus()
		return
	call_api("mutation", "/workspaces", HTTPClient.METHOD_POST, {"id": workspace_id.text})

func save_definition() -> void:
	var pattern := RegEx.new()
	pattern.compile("^[a-z][a-z0-9_-]{0,63}\\.md$")
	if pattern.search(definition_file.text) == null:
		set_notice("Use a Markdown filename such as implement-login.md.", true)
		return
	if not markdown.text.strip_edges().begins_with("#"):
		set_notice("Start your task or role with a Markdown heading (#).", true)
		return
	call_api("mutation", "/definitions/" + chosen(definition_kind) + "/" + definition_file.text, HTTPClient.METHOD_PUT, {"content": markdown.text})

func git_read(resource: String) -> void:
	if chosen(git_workspace).is_empty():
		set_notice("Select a workspace to inspect first.", true)
		return
	call_api("git", "/workspaces/" + chosen(git_workspace) + "/" + resource)

func git_mutate(body: Dictionary) -> void:
	call_api("git", "/workspaces/" + chosen(git_workspace) + "/git", HTTPClient.METHOD_POST, body)

func retry_integration() -> void:
	for project in cache.get("projects", []):
		for execution in cache.get("executions", []):
			if execution.id == selected_execution and (execution.agent_id in project.get("agents", []) or execution.agent_id == project.get("integrator", "")):
				call_api("control", "/projects/" + str(project.id) + "/integrate", HTTPClient.METHOD_POST, {})
				return
	set_notice("Select a run belonging to a team with automatic integration enabled.", true)

func _unhandled_key_input(event: InputEvent) -> void:
	if visible and event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE:
		hide()
		get_viewport().set_input_as_handled()


func ask_delete_selected_project() -> void:
	var identifier := chosen(setup_project)
	if identifier.is_empty():
		return
	project_delete_ids = [identifier]
	delete_all_projects_pending = false
	project_delete_dialog.dialog_text = "Delete managed project '" + identifier + "'?\n\nClean worker and integration worktrees plus project agent settings will be removed. Uncommitted changes block deletion. The selected source repository, local and remote Git branches, and execution history are preserved."
	project_delete_dialog.popup_centered(Vector2i(800, 320))

func ask_delete_all_projects() -> void:
	project_delete_ids.clear()
	for project in cache.get("projects", []):
		project_delete_ids.append(str(project.get("id", "")))
	if project_delete_ids.is_empty():
		return
	delete_all_projects_pending = true
	project_delete_dialog.dialog_text = "Delete ALL " + str(project_delete_ids.size()) + " managed projects and their clean worker worktrees?\n\nUncommitted work blocks deletion. Source repositories, branches, and execution history are preserved."
	project_delete_dialog.popup_centered(Vector2i(800, 320))

func confirm_project_delete() -> void:
	if project_delete_ids.is_empty():
		return
	var identifiers := project_delete_ids.duplicate()
	if delete_all_projects_pending:
		call_api("delete_projects", "/projects", HTTPClient.METHOD_DELETE, {"confirmed": true, "project_ids": identifiers})
	else:
		call_api("delete_project", "/projects/" + identifiers[0], HTTPClient.METHOD_DELETE, {"confirmed": true})

func open_setup() -> void:
	show_management()
	tabs.current_tab = 4
	if token.text.strip_edges().is_empty():
		set_notice("Connect with your local management token first. The project starter connects automatically.", true)
		return
	call_api("setup_projects", "/setup")

func build_setup(parent_tabs: TabContainer) -> void:
	var row := page(parent_tabs, "Setup")
	var form := card(row, "1 · Your project and goal", 700)
	form.add_child(caption("Choose an existing Git project. Start workers from Agents. With automatic integration enabled, ready published results start the integration/test worker automatically."))
	setup_project = option(form, "Approved Git project")
	setup_project.item_selected.connect(func(_index):
		setup_ready = false
		update_buttons())
	button(form, "Find projects", func(): call_api("setup_projects", "/setup"))
	button(form, "Delete selected project", ask_delete_selected_project)
	button(form, "Delete all managed projects", ask_delete_all_projects)
	form.add_child(caption("Optional goal override. A loaded PLANNING.md supplies the next incomplete milestone. Define the shared API contract when possible."))
	setup_objective = TextEdit.new()
	setup_objective.placeholder_text = "Build a task tracker. Backend: task API. Frontend: task list and creation form. Shared contract: GET /api/tasks → [{id, title}], POST /api/tasks accepts {title}."
	setup_objective.custom_minimum_size = Vector2(500, 170)
	setup_objective.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	setup_objective.text_changed.connect(update_buttons)
	form.add_child(setup_objective)
	setup_remote = CheckBox.new()
	setup_remote.text = "Also check remote access (read only)"
	form.add_child(setup_remote)
	setup_publish = CheckBox.new()
	setup_publish.text = "Push successful results to each agent's own Git branch"
	setup_publish.tooltip_text = "Requires starter --publish-results and SSH access. Never merges main."
	form.add_child(setup_publish)
	setup_integrate = CheckBox.new()
	setup_integrate.text = "Integrate + requirements tests + promote green result to main"
	setup_integrate.button_pressed = true
	setup_publish.button_pressed = true
	setup_publish.disabled = true
	setup_integrate.toggled.connect(func(enabled):
		setup_publish.disabled = enabled
		if enabled:
			setup_publish.button_pressed = true)
	form.add_child(setup_integrate)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 12)
	form.get_parent().get_parent().add_child(actions)
	button(actions, "Check project", check_setup_project)
	button(actions, "Create backend + frontend team", func():
		call_api("setup_team", "/setup/team", HTTPClient.METHOD_POST, {"project": chosen(setup_project), "objective": setup_goal(), "publish_results": setup_publish.button_pressed, "auto_integrate": setup_integrate.button_pressed}))
	project_delete_dialog.title = "Delete managed project data"
	project_delete_dialog.ok_button_text = "Delete project data"
	project_delete_dialog.dialog_autowrap = true
	project_delete_dialog.theme = theme
	project_delete_dialog.confirmed.connect(confirm_project_delete)
	project_delete_dialog.canceled.connect(func():
		project_delete_ids.clear()
		delete_all_projects_pending = false)
	add_child(project_delete_dialog)
	var results := card(row, "2 · Readiness and next steps", 750)
	setup_status = caption("Choose your project, then Check project. A loaded plan can supply the goal.")
	setup_status.custom_minimum_size.y = 56
	var result_shell := results.get_parent().get_parent()
	result_shell.add_child(setup_status)
	result_shell.move_child(setup_status, 2)
	setup_result = TextEdit.new()
	setup_result.editable = false
	setup_result.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	setup_result.custom_minimum_size = Vector2(600, 170)
	setup_result.size_flags_vertical = Control.SIZE_FILL
	setup_result.text = "LOCAL STARTER\n\nRun python3 scripts/setup-project.py on Linux/WSL. Select your repository folder. The starter mounts only that project, connects Godot and opens this assistant.\n\nCODEX\n\nBoth agents use the backend's Codex login, with separate roles, tasks and worktrees. Use starter --login if needed.\n\nSSH\n\nThe starter forwards an existing SSH-agent socket and known_hosts to the Git service. It never copies private keys. Remote checks are optional and do not test push permission."
	results.add_child(setup_result)
	setup_document = option(results, "Project instructions · saved to the selected source repository")
	setup_document.add_item("AGENTS.md")
	setup_document.add_item("PLANNING.md")
	setup_document.item_selected.connect(func(_index): show_setup_document())
	var document_actions := HBoxContainer.new()
	document_actions.add_theme_constant_override("separation", 12)
	results.add_child(document_actions)
	button(document_actions, "Load project documents", func(): call_api("setup_docs_load", "/setup/documents/load", HTTPClient.METHOD_POST, {"project": chosen(setup_project)}))
	button(document_actions, "Save project document", save_setup_document)
	button(document_actions, "Import Markdown file", func():
		setup_file_dialog.title = "Import " + chosen(setup_document)
		setup_file_dialog.popup_centered(Vector2i(1400, 900)))
	setup_file_dialog = FileDialog.new()
	setup_file_dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	setup_file_dialog.access = FileDialog.ACCESS_FILESYSTEM
	setup_file_dialog.filters = PackedStringArray(["*.md ; Markdown"])
	setup_file_dialog.use_native_dialog = true
	setup_file_dialog.theme = theme
	setup_file_dialog.content_scale_factor = 2.0
	setup_file_dialog.file_selected.connect(import_setup_document)
	add_child(setup_file_dialog)
	setup_document_editor = TextEdit.new()
	setup_document_editor.wrap_mode = TextEdit.LINE_WRAPPING_BOUNDARY
	setup_document_editor.custom_minimum_size = Vector2(600, 230)
	results.add_child(setup_document_editor)
	results.add_child(caption("Load before editing. Saving changes the project file without committing. Next agent runs read a protected snapshot; security rules always take priority."))


func show_setup_document() -> void:
	var name := chosen(setup_document)
	var document: Dictionary = setup_documents.get(name, {})
	if document.get("exists", false):
		setup_document_editor.text = str(document.get("content", ""))
	elif name == "AGENTS.md":
		setup_document_editor.text = "# Project agent instructions\n\n## Architecture\nFollow the existing project architecture and conventions.\n\n## Quality\nRun relevant tests and document results.\n\n## Collaboration\nBackend and frontend use separate branches. Agree on the interface contract.\n\n## Restrictions\nDo not push or merge automatically. Never expose credentials.\n"
	else:
		setup_document_editor.text = "# Project planning\n\n## Objective\n" + setup_objective.text.strip_edges() + "\n\n## Milestones\n- [ ] Agree on the API contract\n- [ ] Implement backend with tests\n- [ ] Implement frontend with tests\n- [ ] Review both branches and run integration tests\n\n## Acceptance Criteria\n- Tests pass\n- Changes reviewed by the user\n"

func save_setup_document() -> void:
	var name := chosen(setup_document)
	var document: Dictionary = setup_documents.get(name, {})
	call_api("setup_docs_save", "/setup/documents", HTTPClient.METHOD_PUT, {"project": chosen(setup_project), "name": name, "content": setup_document_editor.text, "expected_sha256": str(document.get("sha256", ""))})


func import_setup_document(path: String) -> void:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 12000:
		set_notice("Choose a readable Markdown file of at most 12 KiB.", true)
		return
	var content := file.get_as_text().trim_prefix("\ufeff")
	if not content.strip_edges().begins_with("#"):
		set_notice("The Markdown file needs a heading.", true)
		return
	setup_document_editor.text = content
	set_notice("File imported into editor. Review it, then Save project document to apply.")


func setup_goal() -> String:
	var goal := setup_objective.text.strip_edges()
	if goal.is_empty() and setup_document_project == chosen(setup_project) and setup_documents.get("PLANNING.md", {}).get("exists", false):
		return "Implement the next incomplete milestone from PLANNING.md following AGENTS.md. Split backend and frontend responsibilities and document integration steps."
	return goal

func setup_feedback(message: String, error := false) -> void:
	if setup_status != null:
		setup_status.text = message
		setup_status.add_theme_color_override("font_color", Color("f1959e") if error else MINT)

func request_error(command: Dictionary, message: String) -> void:
	set_notice(message, true)
	if command.get("action") == "git":
		git_result.text = "GIT ACTION FAILED\n\nWorkspace: " + str(command.get("path", "")) + "\n\n" + message
	if str(command.get("action", "")).begins_with("setup"):
		if command.get("action") == "setup_check":
			setup_ready = false
		setup_feedback(message, true)
		setup_result.text = "PROJECT ACTION FAILED\n\n" + message + "\n\nCorrect the issue and try again. Your Markdown files and edits are preserved."
		setup_result.scroll_vertical = 0

func check_setup_project() -> void:
	setup_ready = false
	setup_feedback("Checking project… Please wait for sandbox, Codex and Git results.")
	setup_result.text = "Checking " + chosen(setup_project) + "…\n\nValidating workspace isolation, Codex login and Git."
	setup_result.scroll_vertical = 0
	call_api("setup_check", "/setup/check", HTTPClient.METHOD_POST, {"project": chosen(setup_project), "check_remote": setup_remote.button_pressed})

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
var review_note: LineEdit
var selected_execution := ""
var log_sequence := 0
var action := ""
var editing := false
var active_agent := ""
var pending_agent := ""
var poll := Timer.new()

func caption(value: String) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_size_override("font_size", 22)
	return label

func line(parent: Node, placeholder: String) -> LineEdit:
	var edit := LineEdit.new()
	edit.placeholder_text = placeholder
	edit.custom_minimum_size.x = 420
	parent.add_child(edit)
	return edit

func button(parent: Node, text: String, callback: Callable) -> Button:
	var result := Button.new()
	result.text = text
	result.pressed.connect(callback)
	parent.add_child(result)
	return result

func option(parent: Node, title: String) -> OptionButton:
	parent.add_child(caption(title))
	var result := OptionButton.new()
	result.custom_minimum_size.x = 360
	parent.add_child(result)
	return result

func column(parent: Node) -> VBoxContainer:
	var result := VBoxContainer.new()
	result.add_theme_constant_override("separation", 10)
	parent.add_child(result)
	return result

func _ready() -> void:
	position = Vector2(70, 145)
	size = Vector2(1780, 890)
	add_child(request)
	request.timeout = 40
	request.request_completed.connect(received)
	var outer := column(self)
	var header := HBoxContainer.new()
	outer.add_child(header)
	header.add_child(caption("AGENT MANAGEMENT"))
	token = line(header, "Management access token")
	token.secret = true
	token.text = OS.get_environment("VAC_MANAGEMENT_TOKEN")
	button(header, "Connect / Refresh", refresh)
	button(header, "Close", hide)
	notice = caption("Connect with your management token to configure agents.")
	notice.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	outer.add_child(notice)
	var tabs := TabContainer.new()
	tabs.custom_minimum_size = Vector2(1730, 760)
	outer.add_child(tabs)
	build_agents(tabs)
	build_definitions(tabs)
	build_git(tabs)
	build_executions(tabs)
	add_child(poll)
	poll.wait_time = 3.0
	poll.timeout.connect(func():
		if visible and not token.text.is_empty():
			if not selected_execution.is_empty():
				call_api("logs", "/executions/" + selected_execution + "/logs?after=" + str(log_sequence))
			else:
				refresh())
	poll.start()
	hide()

func page(tabs: TabContainer, title: String) -> HBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = title
	tabs.add_child(scroll)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 24)
	scroll.add_child(row)
	return row

func build_agents(tabs: TabContainer) -> void:
	var row := page(tabs, "Agents")
	var left := column(row)
	agents = ItemList.new()
	agents.custom_minimum_size = Vector2(500, 580)
	agents.item_selected.connect(load_agent)
	left.add_child(agents)
	button(left, "New agent", new_agent)
	var middle := column(row)
	agent_id = line(middle, "Agent ID, e.g. backend-agent")
	agent_name = line(middle, "Agent name")
	workspace = option(middle, "Assigned workspace")
	workspace_info = caption("Select an approved workspace")
	workspace_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	workspace_info.custom_minimum_size.x = 420
	middle.add_child(workspace_info)
	workspace.item_selected.connect(func(_index): update_workspace_info())
	task_file = option(middle, "Markdown task")
	middle.add_child(caption("Roles — select multiple with Ctrl"))
	roles = ItemList.new()
	roles.select_mode = ItemList.SELECT_MULTI
	roles.custom_minimum_size = Vector2(420, 180)
	middle.add_child(roles)
	var settings := column(row)
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
	for name in ["fetch", "pull", "push"]:
		var flag := CheckBox.new()
		flag.text = "Allow " + name + " (manual confirmation required)"
		settings.add_child(flag)
		remote_flags[name] = flag
	button(settings, "Save configuration", save_agent)
	button(settings, "Start agent", func(): control("start"))
	button(settings, "Stop agent", func(): control("stop"))
	button(settings, "Restart agent", func(): control("restart"))

func build_definitions(tabs: TabContainer) -> void:
	var row := page(tabs, "Markdown tasks and roles")
	var files := column(row)
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
	var editor := column(row)
	editor.add_child(caption("Markdown is the source of truth; changes apply to the next execution."))
	markdown = TextEdit.new()
	markdown.custom_minimum_size = Vector2(1120, 600)
	editor.add_child(markdown)

func build_git(tabs: TabContainer) -> void:
	var row := page(tabs, "Workspaces and Git")
	var inputs := column(row)
	var workspace_id := line(inputs, "New workspace ID")
	button(inputs, "Create workspace", func():
		call_api("mutation", "/workspaces", HTTPClient.METHOD_POST, {"id": workspace_id.text}))
	git_workspace = option(inputs, "Workspace to inspect / edit")
	button(inputs, "Repository / branch / modified files / history", func(): git_read("git"))
	button(inputs, "View diff", func(): git_read("diff"))
	button(inputs, "Initialize Git", func(): git_mutate({"operation": "init"}))
	button(inputs, "Connect existing Git repository", func(): git_mutate({"operation": "connect"}))
	remote = line(inputs, "SSH or HTTPS remote URL")
	var remote_name := line(inputs, "Remote name")
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
	var output := column(row)
	output.add_child(caption("Git results — stop agents before changing their working trees."))
	git_result = TextEdit.new()
	git_result.editable = false
	git_result.custom_minimum_size = Vector2(1050, 620)
	output.add_child(git_result)
	var remotes := HBoxContainer.new()
	output.add_child(remotes)
	for operation in ["fetch", "pull", "push"]:
		button(remotes, "Confirm " + operation, func():
			git_mutate({"operation": operation, "agent_id": active_agent, "confirmed": true}))

func build_executions(tabs: TabContainer) -> void:
	var row := page(tabs, "Execution history and logs")
	var list_column := column(row)
	executions = ItemList.new()
	executions.custom_minimum_size = Vector2(470, 560)
	executions.item_selected.connect(func(index):
		selected_execution = str(executions.get_item_metadata(index))
		log_sequence = 0
		logs.text = ""
		call_api("logs", "/executions/" + selected_execution + "/logs"))
	list_column.add_child(executions)
	button(list_column, "Refresh execution history", func():
		selected_execution = ""
		refresh())
	var monitor := column(row)
	monitor.add_child(caption("Observed activity only; successful runtime still requires task review."))
	execution_status = caption("Select an execution to monitor its current status.")
	execution_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	monitor.add_child(execution_status)
	logs = TextEdit.new()
	logs.editable = false
	logs.custom_minimum_size = Vector2(1160, 500)
	monitor.add_child(logs)
	review_note = line(monitor, "Review evidence / acceptance note")
	var reviews := HBoxContainer.new()
	monitor.add_child(reviews)
	button(reviews, "Accept task", func(): review(true))
	button(reviews, "Reject task", func(): review(false))

func show_agent(identifier: String) -> void:
	pending_agent = identifier
	show_management()

func show_management() -> void:
	get_parent().move_child(self, -1)
	show()
	if not token.text.is_empty():
		refresh()

func refresh() -> void:
	call_api("overview", "")

func call_api(next_action: String, path: String, method := HTTPClient.METHOD_GET, body: Dictionary = {}) -> void:
	if request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return
	action = next_action
	var headers := PackedStringArray(["Content-Type: application/json", "Authorization: Bearer " + token.text.strip_edges()])
	var result := request.request(backend_url + "/management" + path, headers, method,
		"" if method == HTTPClient.METHOD_GET else JSON.stringify(body))
	if result != OK:
		notice.text = "Unable to contact backend."

func received(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var data = JSON.parse_string(body.get_string_from_utf8())
	if code < 200 or code >= 300:
		notice.text = "Management access token required." if code == 401 else "Request rejected: " + str(data.get("detail", "Backend unavailable") if data is Dictionary else "Backend unavailable")
		return
	notice.text = "Saved / synchronized. Select an agent to edit or monitor it."
	if action == "overview" and data is Dictionary:
		cache = data
		populate()
	elif action == "git" and data is Dictionary:
		git_result.text = str(data.get("diff", JSON.stringify(data, "  ")))
	elif action == "logs" and data is Dictionary:
		var record: Dictionary = data.get("execution", {})
		execution_status.text = str(record.get("status", "")) + " · Task: " + str(record.get("task_state", "")) + " · " + str(record.get("acceptance", "")) + " · " + str(record.get("workspace_path", "")) + " · " + str(record.get("branch", ""))
		for entry in data.get("logs", []):
			log_sequence = maxi(log_sequence, int(entry.get("sequence", 0)))
			logs.text += str(entry.get("timestamp", "")) + "  " + str(entry.get("type", "")) + "\n" + str(entry.get("detail", "")) + "\n\n"
		logs.text = logs.text.right(48000)
	elif action in ["mutation", "control", "review"]:
		call_deferred("refresh")

func fill_options(target: OptionButton, values: Array, empty := false) -> void:
	var previous := chosen(target)
	target.clear()
	if empty:
		target.add_item("(none)")
	for value in values:
		target.add_item(str(value))
	choose(target, previous)

func populate() -> void:
	agents.clear()
	for item in cache.get("agents", []):
		var config: Dictionary = item.config
		agents.add_item(str(config.name) + " [" + str(config.id) + "]\n" + str(item.state) + " / " + str(item.get("task_state", "")) + "\n" + str(config.workspace) + " · " + str(config.get("task", "(none)")) + "\n" + ", ".join(config.roles) + "\n" + str(item.get("branch", config.git.get("branch", ""))))
		agents.set_item_metadata(agents.item_count - 1, config.id)
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
	var selected_roles: Array = []
	for index in roles.get_selected_items():
		selected_roles.append(roles.get_item_text(index))
	roles.clear()
	for item in cache.get("roles", []):
		roles.add_item(str(item.file))
		if item.file in selected_roles:
			roles.select(roles.item_count - 1, false)
	populate_definitions()
	if not pending_agent.is_empty():
		for index in agents.item_count:
			if str(agents.get_item_metadata(index)) == pending_agent:
				agents.select(index)
				load_agent(index)
				pending_agent = ""
				break
	executions.clear()
	var history: Array = cache.get("executions", []).duplicate()
	history.reverse()
	for item in history:
		executions.add_item(str(item.agent_id) + " · " + str(item.status) + "\n" + str(item.get("acceptance", "UNVERIFIED")) + "\n" + str(item.get("started_at", "")))
		executions.set_item_metadata(executions.item_count - 1, item.id)

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
	for flag in remote_flags.values():
		flag.button_pressed = false

func load_agent(index: int) -> void:
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
		branch.text = str(config.git.get("branch", "")) if config.git.get("branch") != null else ""
		timeout.value = config.execution.timeout_seconds
		retries.value = config.execution.max_retries
		for operation in remote_flags:
			remote_flags[operation].button_pressed = bool(config.git.get("allow_" + operation, false))
		notice.text = "Workspace: " + config.workspace + " · " + str(record.state) + " · Task: " + str(record.get("task_state", ""))

func save_agent() -> void:
	var assigned_roles: Array = []
	for index in roles.get_selected_items():
		assigned_roles.append(roles.get_item_text(index))
	var git := {"enabled": git_enabled.button_pressed, "repository": chosen(repository) if git_enabled.button_pressed else null, "branch": branch.text if not branch.text.is_empty() else null}
	git["remote_name"] = agent_remote_name.text
	git["worktree"] = git_worktree.button_pressed
	for operation in remote_flags:
		git["allow_" + operation] = remote_flags[operation].button_pressed
	var config := {"id": agent_id.text, "name": agent_name.text, "workspace": chosen(workspace), "task": chosen(task_file) if not chosen(task_file).is_empty() else null, "roles": assigned_roles, "git": git, "execution": {"timeout_seconds": int(timeout.value), "max_retries": int(retries.value)}}
	call_api("mutation", "/agents/" + agent_id.text if editing else "/agents", HTTPClient.METHOD_PUT if editing else HTTPClient.METHOD_POST, config)

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

func save_definition() -> void:
	call_api("mutation", "/definitions/" + chosen(definition_kind) + "/" + definition_file.text, HTTPClient.METHOD_PUT, {"content": markdown.text})

func git_read(resource: String) -> void:
	call_api("git", "/workspaces/" + chosen(git_workspace) + "/" + resource)

func git_mutate(body: Dictionary) -> void:
	call_api("git", "/workspaces/" + chosen(git_workspace) + "/git", HTTPClient.METHOD_POST, body)

func review(accepted: bool) -> void:
	if selected_execution.is_empty() or review_note.text.strip_edges().is_empty():
		notice.text = "Select an execution and enter your review evidence."
		return
	call_api("review", "/executions/" + selected_execution + "/review", HTTPClient.METHOD_POST, {"accepted": accepted, "note": review_note.text})

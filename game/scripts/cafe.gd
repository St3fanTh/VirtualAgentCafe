extends Node2D

const EventState = preload("res://scripts/event_state.gd")
const Network = preload("res://scripts/network.gd")
const Character = preload("res://scripts/character.gd")
const World = preload("res://scripts/world.gd")
var state = EventState.new()
var network = Network.new()
var characters: Dictionary = {}
var connection_label: Label
var status_label: Label
var result_label: Label
var task_panel: PanelContainer
var task_input: TextEdit
var task_info: Label
var task_button: Button
var selected_id := "ada"
var backend_url := "http://127.0.0.1:8000"
var mode := "unknown"
var request_action := "task"
var task_request := HTTPRequest.new()
var health_request := HTTPRequest.new()

func label(value: String, size := 16) -> Label:
	var node := Label.new()
	node.text = value
	node.add_theme_font_size_override("font_size", size)
	return node

func _ready() -> void:
	var configured := OS.get_environment("VAC_BACKEND_URL")
	if configured != "":
		backend_url = configured.trim_suffix("/")
	var world = World.new()
	world.position = Vector2(0, 96)
	world.scale = Vector2(3, 3)
	add_child(world)
	for id in ["ada", "turing"]:
		var character = Character.new()
		character.agent_id = id
		character.position = Vector2(64 if id == "ada" else 104, 132)
		character.tint = Color("64d8b1") if id == "ada" else Color("e9af6e")
		character.selected.connect(select_agent)
		world.add_child(character)
		characters[id] = character
	build_ui()
	network.frame_received.connect(on_frame)
	network.connection_changed.connect(on_connection)
	add_child(network)
	add_child(task_request)
	add_child(health_request)
	task_request.timeout = 10
	health_request.timeout = 5
	task_request.request_completed.connect(on_task_result)
	health_request.request_completed.connect(on_health)

func build_ui() -> void:
	var ui := CanvasLayer.new()
	add_child(ui)
	var title := label("VIRTUAL AGENT CAFE", 27)
	title.position = Vector2(24, 12)
	ui.add_child(title)
	connection_label = label("OFFLINE · reconnecting…", 15)
	connection_label.position = Vector2(610, 22)
	ui.add_child(connection_label)
	var hint := label("Click Ada or Turing to assign a task · animations follow observed events", 15)
	hint.position = Vector2(24, 54)
	hint.modulate = Color("b9b4c5")
	ui.add_child(hint)
	status_label = label("Ada · Waiting     |     Turing · Waiting", 17)
	status_label.position = Vector2(24, 590)
	ui.add_child(status_label)
	result_label = label("Results appear in each agent's workspace", 13)
	result_label.position = Vector2(24, 618)
	result_label.modulate = Color("b9b4c5")
	ui.add_child(result_label)
	task_panel = PanelContainer.new()
	task_panel.position = Vector2(185, 150)
	task_panel.size = Vector2(590, 330)
	task_panel.visible = false
	ui.add_child(task_panel)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 18)
	task_panel.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 12)
	margin.add_child(column)
	task_info = label("Task", 17)
	task_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(task_info)
	task_input = TextEdit.new()
	task_input.custom_minimum_size = Vector2(550, 160)
	task_input.placeholder_text = "Describe a concrete coding task…"
	column.add_child(task_input)
	var row := HBoxContainer.new()
	column.add_child(row)
	task_button = Button.new()
	task_button.text = "Run with Codex"
	task_button.pressed.connect(submit_task)
	row.add_child(task_button)
	var message_button := Button.new()
	message_button.text = "Message other agent"
	message_button.pressed.connect(send_peer_message)
	row.add_child(message_button)
	var cancel_button := Button.new()
	cancel_button.text = "Cancel running task"
	cancel_button.pressed.connect(cancel_running_task)
	row.add_child(cancel_button)
	var close := Button.new()
	close.text = "Close"
	close.pressed.connect(func(): task_panel.hide())
	row.add_child(close)

func on_frame(frame: Dictionary) -> void:
	if state.apply(frame):
		for id in state.agents:
			characters[id].update_state(state.agents[id])
		status_label.text = "Ada · %s     |     Turing · %s" % [state.state_label("ada"), state.state_label("turing")]
	elif state.needs_snapshot:
		network.force_reconnect()

func on_connection(online: bool) -> void:
	connection_label.text = "ONLINE · syncing…" if online else "OFFLINE · reconnecting…"
	connection_label.modulate = Color("8dd7b6") if online else Color("ef8290")
	if online:
		health_request.request(backend_url + "/health")

func on_health(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if code != 200:
		return
	var health = JSON.parse_string(body.get_string_from_utf8())
	if health is Dictionary:
		mode = str(health.get("mode", "unknown"))
		connection_label.text = "ONLINE · " + ("DEMO (simulated)" if mode == "demo" else "CODEX (live)")

func select_agent(id: String) -> void:
	selected_id = id
	for key in characters:
		characters[key].is_selected = key == id
	task_info.text = "Task for " + id.capitalize() + (" · Codex" if mode == "codex" else " · start backend in Codex mode to run tasks")
	task_button.disabled = mode != "codex" or not network.online
	if mode == "codex":
		task_info.text += "\n" + str(state.agents.get(id, {}).get("detail", "Ready"))
	task_panel.show()
	task_input.grab_focus()

func send_peer_message() -> void:
	var message := task_input.text.strip_edges()
	if message.is_empty() or message.length() > 256:
		task_info.text = "Enter a public message between 1 and 256 characters."
		return
	send_action("message", "/messages", {"recipient": "turing" if selected_id == "ada" else "ada", "text": message})

func cancel_running_task() -> void:
	send_action("cancel", "/cancel", {})

func send_action(action: String, path: String, body: Dictionary) -> void:
	if mode != "codex" or not network.online:
		task_info.text = "Connect to a backend in Codex mode first."
		return
	if task_request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		task_info.text = "A request is still pending."
		return
	request_action = action
	task_button.disabled = true
	var result := task_request.request(backend_url + "/agents/" + selected_id + path, ["Content-Type: application/json"], HTTPClient.METHOD_POST, JSON.stringify(body))
	if result != OK:
		task_info.text = "Request could not be sent."
		task_button.disabled = false

func submit_task() -> void:
	var prompt := task_input.text.strip_edges()
	if prompt.is_empty() or prompt.length() > 8000:
		task_info.text = "Enter a task between 1 and 8000 characters."
		return
	send_action("task", "/tasks", {"prompt": prompt})

func on_task_result(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	task_button.disabled = mode != "codex" or not network.online
	if code == 202 or (request_action == "cancel" and code == 200):
		var accepted = JSON.parse_string(body.get_string_from_utf8())
		if request_action == "task" and accepted is Dictionary:
			result_label.text = "Files: " + str(accepted.get("workspace", "")).left(100)
		task_input.text = ""
		task_panel.hide()
	else:
		var response = JSON.parse_string(body.get_string_from_utf8())
		var detail := str(response.get("detail", "Request failed")) if response is Dictionary else "Backend unreachable"
		task_info.text = detail.left(100)

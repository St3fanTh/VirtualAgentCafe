extends Node2D

const EventState = preload("res://scripts/event_state.gd")
const Network = preload("res://scripts/network.gd")
const Character = preload("res://scripts/character.gd")
const ActivityCard = preload("res://scripts/activity_card.gd")
const Management = preload("res://scripts/management.gd")
var management = Management.new()

const World = preload("res://scripts/world.gd")
var ui_font := FontFile.new()
var world = World.new()
var state = EventState.new()
var network = Network.new()
var characters: Dictionary = {}
var activity_cards: Dictionary = {}
var connection_label: Label
var status_label: Label
var result_label: Label
var task_panel: PanelContainer
var task_input: TextEdit
var task_info: Label
var task_button: Button
var task_actions: Array[Button] = []
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
	# Distance-field glyphs keep both native 4K and smaller windows crisp.
	ui_font.multichannel_signed_distance_field = true
	ui_font.msdf_pixel_range = 16
	ui_font.msdf_size = 96
	ui_font.data = ThemeDB.fallback_font.data
	var configured := OS.get_environment("VAC_BACKEND_URL")
	if configured != "":
		backend_url = configured.trim_suffix("/")
	world.position = Vector2(88, 310)
	world.scale = Vector2(8.8, 8.8)
	add_child(world)
	for id in ["ada", "turing"]:
		var character = Character.new()
		character.agent_id = id
		character.z_index = 2
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

func ui_style(color: Color, border: Color) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.border_color = border
	style.set_border_width_all(2)
	style.set_corner_radius_all(16)
	style.content_margin_left = 22
	style.content_margin_right = 22
	style.content_margin_top = 14
	style.content_margin_bottom = 14
	return style

func build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	layer.transform = Transform2D.IDENTITY.scaled(Vector2(2, 2))
	var ui := Control.new()
	ui.name = "HUD"
	ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var theme := Theme.new()
	theme.default_font_size = 26
	theme.default_font = ui_font
	for control_type in ["Label", "Button", "TextEdit"]:
		theme.set_font("font", control_type, ui_font)
	theme.set_color("font_color", "Label", Color("f1e6d1"))
	theme.set_color("font_color", "Button", Color("eee4d1"))
	theme.set_stylebox("normal", "Button", ui_style(Color("293b40"), Color("536b69")))
	theme.set_stylebox("hover", "Button", ui_style(Color("405c5b"), Color("93b5a0")))
	theme.set_stylebox("pressed", "Button", ui_style(Color("557970"), Color("c8d9b2")))
	theme.set_stylebox("disabled", "Button", ui_style(Color("262c33"), Color("39414b")))
	theme.set_stylebox("focus", "Button", ui_style(Color(0, 0, 0, 0), Color("e1bc89")))
	theme.set_stylebox("panel", "PanelContainer", ui_style(Color("1f2b32"), Color("6c7e78")))
	theme.set_stylebox("normal", "TextEdit", ui_style(Color("141e26"), Color("455e61")))
	theme.set_stylebox("focus", "TextEdit", ui_style(Color(0, 0, 0, 0), Color("a5bfa7")))
	ui.theme = theme
	layer.add_child(ui)
	management.backend_url = backend_url
	ui.add_child(management)
	var manage_button := Button.new()
	manage_button.text = "Manage agents"
	manage_button.position = Vector2(1280, 84)
	manage_button.pressed.connect(management.show_management)
	ui.add_child(manage_button)
	var title := label("VIRTUAL AGENT CAFE", 46)
	title.position = Vector2(44, 20)
	ui.add_child(title)
	var subtitle := label("A quiet place for busy minds.", 24)
	subtitle.position = Vector2(46, 75)
	subtitle.modulate = Color("c3ab90")
	ui.add_child(subtitle)
	connection_label = label("OFFLINE · reconnecting…", 25)
	connection_label.position = Vector2(1360, 30)
	ui.add_child(connection_label)
	var hint := label("Click Ada or Turing to assign a task · animations follow observed events", 22)
	hint.position = Vector2(44, 113)
	hint.modulate = Color("9eacb0")
	ui.add_child(hint)
	var effects := Button.new()
	effects.text = "Atmosphere"
	effects.toggle_mode = true
	effects.button_pressed = true
	effects.position = Vector2(1620, 84)
	effects.size = Vector2(235, 60)
	effects.toggled.connect(world.set_effects)
	ui.add_child(effects)
	for id in ["ada", "turing"]:
		var card = ActivityCard.new()
		card.agent_id = id
		card.position = Vector2(1490, 155 if id == "ada" else 514)
		card.size = Vector2(386, 340)
		ui.add_child(card)
		activity_cards[id] = card
	var footer := PanelContainer.new()
	footer.position = Vector2(44, 887)
	footer.size = Vector2(1832, 155)
	footer.mouse_filter = Control.MOUSE_FILTER_IGNORE
	ui.add_child(footer)
	status_label = label("Ada / Backend · Idle     |     Turing / Frontend · Idle", 28)
	status_label.position = Vector2(70, 902)
	ui.add_child(status_label)
	var legend := label("CODING  </>     CLI TESTS  >_     PEER EXCHANGE  ↔     IDLE  ☕", 20)
	legend.position = Vector2(70, 953)
	legend.modulate = Color("bca88e")
	ui.add_child(legend)
	result_label = label("Results appear in each agent's workspace", 20)
	result_label.position = Vector2(70, 1000)
	result_label.modulate = Color("9eacb0")
	ui.add_child(result_label)
	task_panel = PanelContainer.new()
	task_panel.theme = management.theme
	task_panel.position = Vector2(430, 230)
	task_panel.size = Vector2(1060, 600)
	task_panel.visible = false
	ui.add_child(task_panel)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 30)
	task_panel.add_child(margin)
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 20)
	margin.add_child(column)
	task_info = label("Task", 28)
	task_info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	column.add_child(task_info)
	task_input = TextEdit.new()
	task_input.custom_minimum_size = Vector2(950, 300)
	task_input.placeholder_text = "Describe a concrete coding task…"
	column.add_child(task_input)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	column.add_child(row)
	task_button = Button.new()
	task_button.text = "Run with Codex"
	task_button.add_theme_stylebox_override("normal", management.panel_style(Color("75d9bb"), Color("75d9bb"), 12))
	task_button.add_theme_color_override("font_color", Color("10292c"))
	task_button.pressed.connect(submit_task)
	row.add_child(task_button)
	task_actions.append(task_button)
	var message_button := Button.new()
	message_button.text = "Ask other agent"
	message_button.pressed.connect(send_peer_message)
	row.add_child(message_button)
	task_actions.append(message_button)
	var cancel_button := Button.new()
	cancel_button.text = "Cancel task"
	cancel_button.pressed.connect(cancel_running_task)
	row.add_child(cancel_button)
	task_actions.append(cancel_button)
	var close := Button.new()
	close.text = "Close"
	close.pressed.connect(func(): task_panel.hide())
	row.add_child(close)
	var scrim := ColorRect.new()
	scrim.name = "ManagementBackdrop"
	scrim.position = Vector2.ZERO
	scrim.size = Vector2(1920, 1080)
	scrim.color = Color(0.02, 0.06, 0.09, 0.76)
	scrim.visible = false
	ui.add_child(scrim)
	var update_modal := func():
		scrim.visible = management.visible or task_panel.visible
		if management.visible:
			ui.move_child(scrim, -1)
			ui.move_child(management, -1)
		elif task_panel.visible:
			ui.move_child(scrim, -1)
			ui.move_child(task_panel, -1)
	management.visibility_changed.connect(func():
		if management.visible:
			task_panel.hide()
		update_modal.call())
	task_panel.visibility_changed.connect(update_modal)

func ensure_character(id: String, data: Dictionary) -> void:
	if characters.has(id):
		return
	var character = Character.new()
	character.agent_id = id
	character.role_label = str(data.get("role", "custom")).trim_suffix(".md")
	character.position = Vector2(145 + (characters.size() - 2) % 5 * 20, 140)
	character.tint = Color.from_hsv(float(characters.size()) * 0.15, 0.4, 0.9)
	character.z_index = 3
	character.selected.connect(select_agent)
	world.add_child(character)
	characters[id] = character

func on_frame(frame: Dictionary) -> void:
	if state.apply(frame):
		if frame.get("kind") == "snapshot":
			for id in state.agents:
				ensure_character(id, state.agents[id])
				characters[id].reset_state(state.agents[id])
				if id in ["ada", "turing"]:
					world.set_agent_status(id, state.agents[id].status, state.agents[id].get("detail", ""))
				if activity_cards.has(id):
					activity_cards[id].history.clear()
					activity_cards[id].history_label.text = "Snapshot synchronized"
					activity_cards[id].update_state(state.agents[id])
		else:
			var id: String = frame.event.agent_id
			characters[id].enqueue_state(state.agents[id])
			if id in ["ada", "turing"]:
				world.set_agent_status(id, state.agents[id].status, state.agents[id].get("detail", ""))
			if activity_cards.has(id):
				activity_cards[id].update_state(state.agents[id], frame.event)
		status_label.text = "Ada / Backend · %s     |     Turing / Frontend · %s" % [state.state_label("ada"), state.state_label("turing")]
	elif state.needs_snapshot:
		network.force_reconnect()

func on_connection(online: bool) -> void:
	connection_label.text = "ONLINE · syncing…" if online else "OFFLINE · reconnecting…"
	update_task_actions()
	connection_label.modulate = Color("8dd7b6") if online else Color("ef8290")
	if online:
		health_request.request(backend_url + "/health")

func on_health(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if code != 200:
		return
	var health = JSON.parse_string(body.get_string_from_utf8())
	if health is Dictionary:
		mode = str(health.get("mode", "unknown"))
		update_task_actions()
		connection_label.text = "ONLINE · " + ("DEMO (simulated)" if mode == "demo" else "CODEX (live)")

func select_agent(id: String) -> void:
	if id not in ["ada", "turing"]:
		management.show_agent(id)
		return
	selected_id = id
	for key in characters:
		characters[key].is_selected = key == id
	task_info.text = "Task for " + id.capitalize() + (" / Backend" if id == "ada" else " / Frontend") + (" · Codex" if mode == "codex" else " · start backend in Codex mode to run tasks")
	update_task_actions()
	if mode == "codex":
		task_info.text += "\n" + str(state.agents.get(id, {}).get("detail", "Ready"))
	task_panel.show()
	task_input.grab_focus()

func send_peer_message() -> void:
	var message := task_input.text.strip_edges()
	if message.is_empty() or message.length() > 256:
		task_info.text = "Enter a public message between 1 and 256 characters."
		return
	send_action("message", "/messages", {"recipient": "turing" if selected_id == "ada" else "ada", "text": message, "request_reply": true})

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
	for button in task_actions:
		button.disabled = true
	var headers := PackedStringArray(["Content-Type: application/json"])
	if not management.token.text.is_empty():
		headers.append("Authorization: Bearer " + management.token.text.strip_edges())
	var result := task_request.request(backend_url + "/agents/" + selected_id + path, headers, HTTPClient.METHOD_POST, JSON.stringify(body))
	if result != OK:
		task_info.text = "Request could not be sent."
		update_task_actions()

func submit_task() -> void:
	var prompt := task_input.text.strip_edges()
	if prompt.is_empty() or prompt.length() > 8000:
		task_info.text = "Enter a task between 1 and 8000 characters."
		return
	send_action("task", "/tasks", {"prompt": prompt})

func update_task_actions() -> void:
	var ready: bool = mode == "codex" and network.online and task_request.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED
	for button in task_actions:
		button.disabled = not ready

func on_task_result(_result: int, code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	update_task_actions()
	call_deferred("update_task_actions")
	if code == 202 or (request_action == "cancel" and code == 200):
		var accepted = JSON.parse_string(body.get_string_from_utf8())
		if request_action == "task" and accepted is Dictionary:
			result_label.text = "Files: " + str(accepted.get("response_file", accepted.get("workspace", ""))).left(110)
		task_input.text = ""
		task_panel.hide()
	else:
		var response = JSON.parse_string(body.get_string_from_utf8())
		var detail := str(response.get("detail", "Request failed")) if response is Dictionary else "Backend unreachable"
		task_info.text = detail.left(100)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_ESCAPE and task_panel.visible:
		task_panel.hide()
		get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F11:
		var window := get_window()
		window.mode = Window.MODE_WINDOWED if window.mode == Window.MODE_FULLSCREEN else Window.MODE_FULLSCREEN

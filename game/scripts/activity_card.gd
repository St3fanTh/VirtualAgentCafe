extends PanelContainer

const EventState = preload("res://scripts/event_state.gd")
var compact := false
var agent_id := "ada"
var heading: Label
var status_label: Label
var detail_label: Label
var history_label: Label
var history: Array[String] = []

func _ready() -> void:
	var column := VBoxContainer.new()
	column.add_theme_constant_override("separation", 4 if compact else 8)
	add_child(column)
	heading = Label.new()
	heading.add_theme_font_size_override("font_size", 22)
	heading.text = "ADA / BACKEND" if agent_id == "ada" else "TURING / FRONTEND"
	heading.modulate = Color("86ddb8") if agent_id == "ada" else Color("edbd86")
	column.add_child(heading)
	status_label = Label.new()
	status_label.add_theme_font_size_override("font_size", 26 if compact else 32)
	status_label.text = "Idle"
	column.add_child(status_label)
	detail_label = Label.new()
	detail_label.add_theme_font_size_override("font_size", 18)
	detail_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	detail_label.custom_minimum_size = Vector2(0, 48)
	detail_label.max_lines_visible = 2
	column.add_child(detail_label)
	var separator := HSeparator.new()
	column.add_child(separator)
	var title := Label.new()
	title.text = "OBSERVED ACTIVITY"
	title.add_theme_font_size_override("font_size", 14)
	title.modulate = Color("9eacb0")
	column.add_child(title)
	history_label = Label.new()
	history_label.add_theme_font_size_override("font_size", 16)
	history_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	history_label.max_lines_visible = 2 if compact else 6
	column.add_child(history_label)

func update_state(state: Dictionary, event: Dictionary = {}) -> void:
	var kind := str(state.get("status", "agent.waiting"))
	var detail := str(state.get("detail", "Ready"))
	status_label.text = EventState.STATES.get(kind, "Idle")
	if kind == "agent.waiting" and detail.begins_with("CLI:"):
		status_label.text = "CLI command"
	if kind == "agent.message" and state.get("recipient") == null:
		status_label.text = "Response"
	status_label.modulate = Color("f1e6d1")
	if kind == "agent.testing": status_label.modulate = Color("f5ce84")
	if kind == "agent.error": status_label.modulate = Color("f2818d")
	if kind == "agent.coding": status_label.modulate = Color("7fe3b0")
	detail_label.text = detail
	if not event.is_empty():
		var timestamp := str(event.get("timestamp", "")).substr(11, 8)
		history.push_front(timestamp + "  " + detail.replace("\n", " ").left(34))
		if history.size() > 5:
			history.pop_back()
		history_label.text = "\n".join(history)

extends Node2D

signal selected(agent_id: String)

var agent_id := "ada"
var status := "agent.waiting"
var detail := "Ready"
var source := "system"
var tint := Color("64d8b1")
var clock := 0.0
var route: Array[Vector2] = []
var is_selected := false
var last_sequence := -1
var bubble := ""
var bubble_left := 0.0
var presentation_queue: Array[Dictionary] = []
var dwell := 0.0
const MAX_PRESENTATION_QUEUE := 16
const MIN_EVENT_DWELL := 0.65

func reset_state(state: Dictionary) -> void:
	presentation_queue.clear()
	last_sequence = -1
	update_state(state)

func enqueue_state(state: Dictionary) -> void:
	if presentation_queue.size() >= MAX_PRESENTATION_QUEUE:
		# Keep newest evidence when visual presentation falls behind.
		presentation_queue.clear()
	if presentation_queue.is_empty() and dwell <= 0:
		update_state(state)
	else:
		presentation_queue.append(state.duplicate(true))

func update_state(state: Dictionary) -> void:
	var new_status := str(state.get("status", "agent.waiting"))
	var changed := int(state.get("sequence", 0)) != last_sequence
	status = new_status
	detail = str(state.get("detail", "")).left(256)
	source = str(state.get("source", "system"))
	if changed:
		dwell = MIN_EVENT_DWELL
		clock = 0.0
		last_sequence = int(state.get("sequence", 0))
		var target := destination()
		route.clear()
		if position.distance_to(target) > 2:
			route.append(Vector2(position.x, 94))
			route.append(Vector2(target.x, 94))
			route.append(target)
		bubble = detail if status == "agent.message" else ""
		bubble_left = 8.0
	queue_redraw()

func destination() -> Vector2:
	var second := agent_id == "turing"
	match status:
		"agent.coding", "agent.thinking", "agent.started":
			return Vector2(112 if second else 60, 63)
		"agent.testing":
			return Vector2(282 if second else 252, 65)
		"agent.message":
			return Vector2(211 if second else 177, 116)
		_:
			return Vector2(104 if second else 64, 132)

func _process(delta: float) -> void:
	clock += delta
	dwell = maxf(0, dwell - delta)
	if dwell <= 0 and not presentation_queue.is_empty():
		update_state(presentation_queue.pop_front())
	bubble_left = maxf(0, bubble_left - delta)
	if not route.is_empty():
		position = position.move_toward(route[0], delta * 45)
		if position.distance_to(route[0]) < 0.1:
			route.pop_front()
	queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if get_local_mouse_position().length() < 12:
			selected.emit(agent_id)
			get_viewport().set_input_as_handled()

func rect(x: float, y: float, w: float, h: float, color: Color) -> void:
	draw_rect(Rect2(x, y, w, h), color)

func _draw() -> void:
	var dark := Color("253044")
	var skin := Color("f3c897")
	var phase := int(clock * 5) % 2
	var bounce := -2.0 if status == "agent.finished" and phase == 1 else 0.0
	if is_selected:
		draw_rect(Rect2(-11, -19, 22, 24), Color("eee4ad"), false, 1)
	rect(-7, 2, 14, 3, Color(0, 0, 0, 0.25))
	rect(-5, -10 + bounce, 10, 10, tint)
	rect(-5, -19 + bounce, 10, 9, dark)
	rect(-4, -16 + bounce, 8, 7, skin)
	rect(-5, -19 + bounce, 11, 4, Color("493446"))
	rect(-2, -13 + bounce, 1, 1, dark)
	rect(2, -13 + bounce, 1, 1, dark)
	var stride := phase * 2 if not route.is_empty() else 0
	rect(-4, 0 + bounce, 3, 3 + stride, dark)
	rect(1, 0 + bounce, 3, 5 - stride, dark)
	match status:
		"agent.coding":
			rect(-8, -8 + phase, 4, 3, skin)
			rect(4, -7 - phase, 4, 3, skin)
			rect(-7, -3, 14, 2, dark)
		"agent.testing":
			rect(5, -12, 6, 9, Color("f8ce6a"))
			rect(6, -10 + phase * 2, 4, 1, dark)
		"agent.thinking":
			for i in range(3):
				rect(-4 + i * 4, -27, 2, 2, Color("aab5f5") if int(clock * 3) % 3 == i else dark)
		"agent.message":
			rect(7, -10 - phase, 4, 3, skin)
		"agent.finished":
			rect(-8, -14 + phase * 2, 3, 5, skin)
			rect(5, -14 + phase * 2, 3, 5, skin)
			rect(-2, -26, 4, 4, Color("70df95"))
		"agent.error":
			rect(-1, -28, 3, 7, Color("ef7183"))
			rect(-1, -19, 3, 2, Color("ef7183"))
		"agent.waiting":
			rect(6, -8 + phase, 4, 5, Color("e9dfba"))
	var font := ThemeDB.fallback_font
	draw_string(font, Vector2(-11, 15), agent_id.capitalize(), HORIZONTAL_ALIGNMENT_LEFT, -1, 6, Color("f2e9dc"))
	if bubble != "" and bubble_left > 0:
		var text := bubble.left(42)
		var width := minf(128, font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 6).x + 8)
		rect(-width / 2, -44, width, 13, Color("f0e7d6"))
		rect(-2, -31, 4, 3, Color("f0e7d6"))
		draw_string(font, Vector2(-width / 2 + 4, -35), text, HORIZONTAL_ALIGNMENT_LEFT, width - 8, 6, dark)

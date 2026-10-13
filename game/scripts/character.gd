extends Node2D

signal selected(agent_id: String)

var agent_id := "ada"
var role_label := ""
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
var peer_id = null
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
	peer_id = state.get("recipient")
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
	var second := agent_id == "turing" or "frontend" in role_label.to_lower()
	match status:
		"agent.coding", "agent.thinking", "agent.started":
			return Vector2(112 if second else 60, 63)
		"agent.testing":
			return Vector2(282 if second else 252, 65)
		"agent.message":
			return Vector2(211 if second else 177, 116) if peer_id != null else Vector2(112 if second else 60, 63)
		"agent.waiting":
			if detail.begins_with("CLI:"):
				return Vector2(282 if second else 252, 65)
			return Vector2(104 if second else 64, 132)
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
	rect(-5, -10 + bounce, 10, 10, tint.darkened(0.15))
	rect(-4.5, -10 + bounce, 8.5, 8, tint)
	rect(-4, -9 + bounce, 1.5, 7, tint.lightened(0.22))
	rect(3, -8 + bounce, 1, 6, tint.darkened(0.3))
	rect(-1, -10 + bounce, 2, 1, Color("eee0c4"))
	rect(-5, -19 + bounce, 10, 9, dark)
	rect(-4, -16 + bounce, 8, 7, skin)
	rect(3, -15 + bounce, 1, 5, skin.darkened(0.16))
	rect(-3, -10 + bounce, 5, 0.5, Color("bc806d"))
	rect(-5, -19 + bounce, 11, 4, Color("493446"))
	rect(-4, -18 + bounce, 5, 0.5, Color("806064"))
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
			rect(5, -16, 17, 13, Color("f8ce6a"))
			rect(6, -15, 15, 10, dark)
			rect(8, -12 + phase, 3, 1, Color("82d8aa"))
			rect(12, -10, 6, 0.5, Color("82d8aa"))
			rect(7, -6, 12, 1, Color("9a8472"))
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
	var draw_scale := maxf(1.0, get_global_transform().get_scale().x)
	var badge := "IDLE"
	match status:
		"agent.coding": badge = "</> CODE"
		"agent.testing": badge = ">_ TEST"
		"agent.message": badge = "↔ CHAT" if peer_id != null else "RESPONSE"
		"agent.thinking": badge = "THINKING"
		"agent.started": badge = "STARTING"
		"agent.error": badge = "ERROR"
		"agent.finished": badge = "DONE"
		"agent.waiting": badge = ">_ CLI" if detail.begins_with("CLI:") else "IDLE"
	var badge_width := font.get_string_size(badge, HORIZONTAL_ALIGNMENT_LEFT, -1, 36).x / draw_scale + 5
	rect(-badge_width / 2, -36, badge_width, 7, Color("1e2c34"))
	draw_set_transform(Vector2(-badge_width / 2 + 2.5, -31), 0.0, Vector2.ONE / draw_scale)
	draw_string(font, Vector2.ZERO, badge, HORIZONTAL_ALIGNMENT_LEFT, -1, 36, tint.lightened(0.25))
	draw_set_transform(Vector2.ZERO)
	draw_set_transform(Vector2(-9, 15), 0.0, Vector2.ONE / draw_scale)
	draw_string(font, Vector2.ZERO, agent_id.capitalize() + (" · " + role_label if not role_label.is_empty() else (" · Backend" if agent_id == "ada" else " · Frontend")), HORIZONTAL_ALIGNMENT_LEFT, -1, 36, Color("f2e9dc"))
	draw_set_transform(Vector2.ZERO)
	if bubble != "" and bubble_left > 0:
		var text := bubble.left(42)
		var width := minf(128, font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 40).x / draw_scale + 8)
		rect(-width / 2, -44, width, 13, Color("f0e7d6"))
		rect(-2, -31, 4, 3, Color("f0e7d6"))
		draw_set_transform(Vector2(-width / 2 + 4, -35), 0.0, Vector2.ONE / draw_scale)
		draw_string(font, Vector2.ZERO, text, HORIZONTAL_ALIGNMENT_LEFT, (width - 8) * draw_scale, 40, dark)
		draw_set_transform(Vector2.ZERO)

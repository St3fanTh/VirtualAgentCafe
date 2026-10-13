extends "res://tests/test_gui_input.gd"

var saw_message := false
var saw_cancel := false

func visible_button(text: String) -> Button:
	for node in cafe.find_children("*", "Button", true, false):
		if node.text == text and node.is_visible_in_tree():
			return node
	check(false, "Visible café button exists: " + text)
	return null

func click_avatar() -> void:
	await frames()
	var position: Vector2 = cafe.characters.ada.get_global_transform_with_canvas() * Vector2.ZERO
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
	check(cafe.task_panel.visible, "Pointer on avatar opens its task dialog")

func wait_for(predicate: Callable, message: String) -> void:
	var deadline := Time.get_ticks_msec() + 10000
	while not predicate.call():
		check(Time.get_ticks_msec() < deadline, message)
		await process_frame
	await frames()

func run() -> void:
	root.gui_embed_subwindows = true
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	cafe.network.frame_received.connect(func(frame):
		if frame.get("kind") == "event":
			var event: Dictionary = frame.event
			if event.type == "agent.message" and event.agent_id == "turing" and "Please review" in str(event.payload.detail):
				saw_message = true
			if event.type == "agent.error" and event.payload.detail == "Codex task cancelled":
				saw_cancel = true)
	await wait_for(func(): return cafe.mode == "codex", "Café connects to fixture backend")
	await click_avatar()
	await type_text(cafe.task_input, "fixture: create and test")
	await click(visible_button("Run with Codex"))
	await wait_for(func(): return cafe.state.agents.ada.status == "agent.finished", "Run button reaches CLI completion")
	check(not cafe.task_panel.visible, "Successful submission closes task dialog")
	await click_avatar()
	await type_text(cafe.task_input, "Please review")
	await click(visible_button("Ask other agent"))
	await wait_for(func(): return saw_message, "Message button delivers a public peer event")
	await click_avatar()
	await type_text(cafe.task_input, "fixture: wait")
	await click(visible_button("Run with Codex"))
	await wait_for(func(): return cafe.state.agents.ada.status == "agent.thinking", "Waiting CLI actually running")
	await click_avatar()
	await click(visible_button("Cancel task"))
	await wait_for(func(): return saw_cancel, "Cancel button terminates actual CLI process")
	await click_avatar()
	await click(visible_button("Close"))
	check(not cafe.task_panel.visible, "Task close button works")
	print("Godot café avatar/task/message/cancel pointer and keyboard tests: PASS")
	quit(0)

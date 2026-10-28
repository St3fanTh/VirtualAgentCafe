extends SceneTree

func _initialize() -> void:
	call_deferred("run")

func frames() -> void:
	await process_frame
	await process_frame
	await process_frame

func run() -> void:
	var cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	await frames()
	var ui = cafe.management
	ui.poll.stop()
	ui.request.cancel_request()
	ui.request_queue.clear()
	ui.show()
	ui.tabs.current_tab = 3
	ui.logs.text = "History line\n".repeat(300)
	await frames()
	ui.logs.scroll_vertical = 60
	await frames()
	var before: float = ui.logs.scroll_vertical
	assert(before > 0)
	ui.append_live_logs([])
	await frames()
	assert(is_equal_approx(ui.logs.scroll_vertical, before), "Empty poll must not move the viewport")
	ui.append_live_logs([{"sequence": 1, "type": "agent.testing", "detail": "New event"}])
	await frames()
	assert(is_equal_approx(ui.logs.scroll_vertical, before), "New logs must preserve reading position")
	ui.append_live_logs([{"sequence": 1, "detail": "Duplicate"}])
	await frames()
	assert(not "Duplicate" in ui.logs.text)
	assert(is_equal_approx(ui.logs.scroll_vertical, before))
	ui.logs.scroll_vertical = ui.logs.get_line_count()
	await frames()
	ui.append_live_logs([{"sequence": 2, "detail": "New live event\n".repeat(30)}])
	await frames()
	var bar = ui.logs.get_v_scroll_bar()
	assert(bar.value >= bar.max_value - bar.page - 1, "At bottom, follow new events")
	ui.logs.text = "0123456789\n".repeat(4300)
	await frames()
	ui.logs.scroll_vertical = 2000
	await frames()
	var old_text: String = ui.logs.text
	before = ui.logs.scroll_vertical
	ui.append_live_logs([{"sequence": 3, "detail": "extra\n".repeat(200)}])
	await frames()
	assert(ui.logs.text.length() <= 48000)
	# Trimming old lines should shift the viewport by exactly the removed lines.
	var combined := old_text + "  \n" + "extra\n".repeat(200) + "\n\n"
	var cut: int = combined.find("\n", combined.length() - 48000) + 1
	assert(is_equal_approx(ui.logs.scroll_vertical, before - combined.left(cut).count("\n")))
	cafe.queue_free()
	await frames()
	print("Godot live log scrolling tests: PASS")
	quit(0)

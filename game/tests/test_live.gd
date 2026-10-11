extends SceneTree

var cafe: Node
var observed: Dictionary = {}
var started := 0
var tested_click := false

func _initialize() -> void:
	started = Time.get_ticks_msec()
	call_deferred("start")

func start() -> void:
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	cafe.network.frame_received.connect(on_frame)

func on_frame(frame: Dictionary) -> void:
	if frame.get("kind") == "event":
		observed[frame.event.type] = true

func _process(_delta: float) -> bool:
	if cafe != null and cafe.network.online and not tested_click:
		cafe.characters.ada.selected.emit("ada")
		if not cafe.task_panel.visible or cafe.selected_id != "ada":
			push_error("Character selection did not open task UI")
			quit(1)
		tested_click = true
	for kind in ["agent.coding", "agent.testing", "agent.message", "agent.finished"]:
		if not observed.has(kind):
			if Time.get_ticks_msec() - started > 10000:
				push_error("Godot live integration timed out; missing " + kind)
				quit(1)
			return false
	if tested_click:
		print("Godot live WebSocket and selection tests: PASS")
		quit(0)
	return false

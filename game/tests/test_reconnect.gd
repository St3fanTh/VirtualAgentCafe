extends SceneTree

var cafe: Node
var marker_root := ""
var started := 0
var snapshots := 0
var offline_seen := false

func _initialize() -> void:
	started = Time.get_ticks_msec()
	marker_root = OS.get_environment("VAC_TEST_MARKERS")
	call_deferred("start")

func start() -> void:
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	cafe.network.frame_received.connect(on_frame)
	cafe.network.connection_changed.connect(on_connection)

func marker(name: String) -> void:
	var file := FileAccess.open(marker_root.path_join(name), FileAccess.WRITE)
	if file == null:
		push_error("Cannot write test marker")
		quit(1)
		return
	file.store_string("ok")
	file.close()

func on_frame(frame: Dictionary) -> void:
	if frame.get("kind") == "snapshot":
		snapshots += 1
		if snapshots == 1:
			marker("connected")
		elif offline_seen:
			if cafe.state.agents.size() != 2:
				push_error("Reconnect snapshot did not restore agents")
				quit(1)
			else:
				print("Godot offline/backoff/reconnect snapshot tests: PASS")
				quit(0)

func on_connection(online: bool) -> void:
	if not online and snapshots > 0:
		offline_seen = true
		marker("offline")

func _process(_delta: float) -> bool:
	if Time.get_ticks_msec() - started > 15000:
		push_error("Godot reconnect timed out")
		quit(1)
	return false

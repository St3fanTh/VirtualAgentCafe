extends SceneTree

var cafe: Node
var started := 0
var stage := 0
var saw_coding := false
var saw_testing := false
var saw_finished := false
var saw_peer_message := false
var saw_cancelled := false

func _initialize() -> void:
	started = Time.get_ticks_msec()
	call_deferred("start")

func start() -> void:
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	cafe.network.frame_received.connect(on_frame)

func on_frame(frame: Dictionary) -> void:
	if frame.get("kind") != "event":
		return
	var event: Dictionary = frame.event
	if event.type == "agent.coding":
		saw_coding = true
	if event.type == "agent.testing":
		saw_testing = true
	if event.type == "agent.finished":
		saw_finished = true
	if event.agent_id == "turing" and event.type == "agent.message":
		saw_peer_message = true
	if event.type == "agent.error" and event.payload.detail == "Codex task cancelled":
		saw_cancelled = true

func _process(_delta: float) -> bool:
	if Time.get_ticks_msec() - started > 15000:
		push_error("Godot task integration timed out at stage " + str(stage))
		quit(1)
		return false
	if cafe == null or cafe.mode != "codex":
		return false
	match stage:
		0:
			cafe.characters.ada.selected.emit("ada")
			cafe.task_input.text = "fixture: create and test"
			cafe.submit_task()
			stage = 1
		1:
			if saw_finished and cafe.task_request.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
				if not saw_coding or not saw_testing:
					push_error("Task did not produce editing and test evidence")
					quit(1)
				cafe.select_agent("ada")
				cafe.task_input.text = "Please review"
				cafe.send_peer_message()
				stage = 2
		2:
			if saw_peer_message and cafe.task_request.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
				cafe.select_agent("ada")
				cafe.task_input.text = "fixture: wait"
				cafe.submit_task()
				stage = 3
		3:
			if cafe.state.state_label("ada") == "Thinking" and cafe.task_request.get_http_client_status() == HTTPClient.STATUS_DISCONNECTED:
				cafe.cancel_running_task()
				stage = 4
		4:
			if saw_cancelled:
				print("Godot task submission, peer delivery and cancellation tests: PASS")
				quit(0)
	return false

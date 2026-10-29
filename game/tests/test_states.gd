extends SceneTree

const EventState = preload("res://scripts/event_state.gd")
const Character = preload("res://scripts/character.gd")
var failures := 0

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func _init() -> void:
	var integrator = Character.new()
	integrator.agent_id = "project-integration"
	integrator.role_label = "backend-frontend-integration.md"
	integrator.status = "agent.coding"
	check(integrator.short_label() == "Integration", "Integration takes precedence over worker role names")
	check(integrator.destination() == Vector2(193, 65), "Integrator has a separate workstation")
	integrator.status = "agent.waiting"
	check(integrator.destination() == Vector2(193, 145), "Integrator has a separate idle position")
	integrator.free()
	var state = EventState.new()
	check(state.apply({"kind": "snapshot", "version": 1, "sequence": 0, "agents": [
		{"agent_id": "ada", "status": "agent.waiting"},
		{"agent_id": "turing", "status": "agent.waiting"}
	]}), "Initial snapshot accepted")
	var seq := 0
	for kind in EventState.STATES:
		seq += 1
		var frame := {"kind": "event", "version": 1, "event": {
			"agent_id": "ada", "type": kind, "sequence": seq,
			"payload": {"detail": "Observed activity", "source": "codex", "recipient": "turing"}}}
		check(state.apply(frame), "Accept event " + kind)
		check(state.state_label("ada") == EventState.STATES[kind], "Map state " + kind)
		check(not state.apply(frame), "Reject duplicate")
		var character = Character.new()
		character.update_state(state.agents.ada)
		check(character.status == kind, "Character animation follows " + kind)
		check(character.source == "codex", "Preserve source")
		if kind == "agent.coding":
			check(character.destination() == Vector2(60, 63), "Coding desk")
		if kind == "agent.testing":
			check(character.destination() == Vector2(252, 65), "Test station")
		if kind == "agent.message":
			check(character.bubble == "Observed activity", "Message bubble")
		character.free()
	check(not state.apply({"kind": "event", "version": 1, "event": {"sequence": seq + 2}}), "Gap rejected")
	check(state.needs_snapshot, "Gap requires snapshot")
	check(state.apply({"kind": "snapshot", "version": 1, "sequence": 0, "agents": [
		{"agent_id": "ada", "status": "agent.waiting"},
		{"agent_id": "turing", "status": "agent.finished"}
	]}), "Reconnect after backend restart resets sequence")
	check(state.sequence == 0, "Reset baseline")
	var visual = Character.new()
	visual.reset_state({"status": "agent.coding", "sequence": 1})
	visual.enqueue_state({"status": "agent.testing", "sequence": 2})
	visual.enqueue_state({"status": "agent.finished", "sequence": 3})
	check(visual.status == "agent.coding", "Short coding event remains visible")
	visual._process(0.7)
	check(visual.status == "agent.testing", "Observed testing shown next")
	visual._process(0.7)
	check(visual.status == "agent.finished", "Observed completion shown next")
	for index in range(100):
		visual.enqueue_state({"status": "agent.waiting", "sequence": index + 4})
	check(visual.presentation_queue.size() <= visual.MAX_PRESENTATION_QUEUE, "Visual queue bounded")
	visual.reset_state({"status": "agent.error", "sequence": 0})
	check(visual.presentation_queue.is_empty(), "Snapshot clears stale animation queue")
	check(visual.status == "agent.error", "Snapshot immediately authoritative")
	visual.role_label = "simulationworld-9e6a873f-backend.md"
	check(visual.short_label() == "Backend", "Managed labels omit project IDs and role filenames")
	visual.role_label = "custom"
	visual.display_name = "An extremely long agent name that must fit"
	check(visual.short_label().length() <= 18, "Custom agent label is bounded")
	visual.reset_state({"status": "agent.coding", "sequence": 101})
	visual._process(0.3)
	var elapsed: float = visual.clock
	visual.reset_state({"status": "agent.coding", "sequence": 101})
	check(visual.clock == elapsed, "Unchanged snapshots preserve animation progress")
	visual.free()
	check(state.apply({"kind": "snapshot", "version": 1, "sequence": 0, "agents": [
		{"agent_id": "ada", "status": "agent.waiting"},
		{"agent_id": "turing", "status": "agent.waiting"},
		{"agent_id": "backend-agent", "status": "agent.coding"}
	]}), "Managed agent snapshot accepted")
	check(state.state_label("backend-agent") == "Coding", "Managed agent observed state mapped")
	check(not state.valid_agent({"agent_id": "../escape", "status": "agent.waiting"}), "Invalid managed ID rejected")
	var connection = preload("res://scripts/local_connection.gd")
	var connection_path := "user://test-connection.json"
	var connection_file := FileAccess.open(connection_path, FileAccess.WRITE)
	connection_file.store_string(JSON.stringify({"backend_url": "http://127.0.0.1:8000", "token": "fixture-private"}))
	connection_file.close()
	check(connection.read_token(connection_path, "http://127.0.0.1:8000/") == "fixture-private", "Load saved local connection")
	check(connection.read_token(connection_path, "http://example.org:8000").is_empty(), "Do not send local token to another backend")
	connection_file = FileAccess.open(connection_path, FileAccess.WRITE)
	connection_file.store_string("broken json")
	connection_file.close()
	check(connection.read_token(connection_path, "http://127.0.0.1:8000").is_empty(), "Invalid connection file is ignored")
	DirAccess.remove_absolute(ProjectSettings.globalize_path(connection_path))
	print("Godot state tests: ", "PASS" if failures == 0 else "FAIL")
	quit(0 if failures == 0 else 1)

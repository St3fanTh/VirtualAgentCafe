extends SceneTree

const EventState = preload("res://scripts/event_state.gd")
const Character = preload("res://scripts/character.gd")
var failures := 0

func check(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)

func _init() -> void:
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
			"payload": {"detail": "Observed activity", "source": "codex"}}}
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
	print("Godot state tests: ", "PASS" if failures == 0 else "FAIL")
	quit(0 if failures == 0 else 1)

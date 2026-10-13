extends RefCounted

const STATES := {
	"agent.started": "Starting", "agent.thinking": "Thinking",
	"agent.coding": "Coding", "agent.testing": "Testing",
	"agent.message": "Communication", "agent.waiting": "Idle",
	"agent.finished": "Finished", "agent.error": "Error"
}
var sequence: int = 0
var agents: Dictionary = {}
var needs_snapshot: bool = true

func apply(frame: Dictionary) -> bool:
	if int(frame.get("version", 0)) != 1:
		return false
	if frame.get("kind") == "snapshot":
		var incoming: Dictionary = {}
		for agent in frame.get("agents", []):
			if not agent is Dictionary or not valid_agent(agent):
				return false
			incoming[agent.agent_id] = agent.duplicate(true)
		if incoming.size() < 2 or incoming.size() > 64:
			return false
		agents = incoming
		sequence = int(frame.get("sequence", 0))
		needs_snapshot = false
		return true
	if frame.get("kind") != "event" or needs_snapshot:
		return false
	var event: Dictionary = frame.get("event", {})
	var next_sequence := int(event.get("sequence", 0))
	if next_sequence <= sequence:
		return false
	if next_sequence != sequence + 1:
		needs_snapshot = true
		return false
	if not valid_agent({"agent_id": event.get("agent_id"), "status": event.get("type")}):
		return false
	if not agents.has(event.agent_id):
		needs_snapshot = true
		return false
	var payload: Dictionary = event.get("payload", {})
	var agent: Dictionary = agents[event.agent_id].duplicate(true)
	agent.status = event.type
	agent.sequence = next_sequence
	agent.detail = str(payload.get("detail", "")).left(256)
	agent.source = payload.get("source", "system")
	agent.recipient = payload.get("recipient")
	agent.correlation_id = event.get("correlation_id")
	agents[event.agent_id] = agent
	sequence = next_sequence
	return true

func valid_agent(agent: Dictionary) -> bool:
	var id = agent.get("agent_id")
	if not id is String or id.is_empty() or id.length() > 64:
		return false
	for character in id:
		if not character in "abcdefghijklmnopqrstuvwxyz0123456789_-":
			return false
	return STATES.has(agent.get("status"))

func state_label(agent_id: String) -> String:
	var agent: Dictionary = agents.get(agent_id, {})
	if agent.get("status") == "agent.waiting" and str(agent.get("detail", "")).begins_with("CLI:"):
		return "CLI command"
	if agent.get("status") == "agent.message" and agent.get("recipient") == null:
		return "Response"
	return STATES.get(agent.get("status", "agent.waiting"), "Idle")

extends RefCounted

const STATES := {
	"agent.started": "Starting", "agent.thinking": "Thinking",
	"agent.coding": "Coding", "agent.testing": "Testing",
	"agent.message": "Communication", "agent.waiting": "Waiting",
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
		if incoming.size() != 2:
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
	return agent.get("agent_id") in ["ada", "turing"] and STATES.has(agent.get("status"))

func state_label(agent_id: String) -> String:
	return STATES.get(agents.get(agent_id, {}).get("status", "agent.waiting"), "Waiting")

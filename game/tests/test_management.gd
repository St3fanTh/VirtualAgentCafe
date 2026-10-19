extends SceneTree

var cafe: Node
var started := 0
var stage := 0
var execution_id := ""
var managed_id := "backend-agent"

func _initialize() -> void:
	started = Time.get_ticks_msec()
	call_deferred("start")

func start() -> void:
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)

func contains(items: Array, key: String, value: String) -> bool:
	for item in items:
		if str(item.get(key, "")) == value:
			return true
	return false

func _process(_delta: float) -> bool:
	if Time.get_ticks_msec() - started > 25000:
		push_error("Management integration timed out at stage " + str(stage))
		quit(1)
		return false
	if cafe == null or cafe.mode != "codex":
		return false
	var ui = cafe.management
	if ui.request.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		return false
	match stage:
		0:
			ui.show_management()
			stage = 1
		1:
			if not ui.cache.has("agents"):
				return false
			ui.call_api("mutation", "/workspaces", HTTPClient.METHOD_POST, {"id": "project"})
			stage = 2
		2:
			if not contains(ui.cache.get("workspaces", []), "id", "project"):
				return false
			ui.definition_kind.select(1)
			ui.definition_file.text = "backend.md"
			ui.markdown.text = "# Backend\nFollow the architecture and write tests."
			ui.save_definition()
			stage = 3
		3:
			if not contains(ui.cache.get("roles", []), "file", "backend.md"):
				return false
			ui.definition_kind.select(0)
			ui.definition_file.text = "task.md"
			ui.markdown.text = "# Task\nCreate and test a result file."
			ui.save_definition()
			stage = 4
		4:
			if not contains(ui.cache.get("tasks", []), "file", "task.md"):
				return false
			ui.new_agent()
			ui.agent_id.text = managed_id
			ui.agent_name.text = "Backend Engineer"
			ui.choose(ui.workspace, "project")
			ui.choose(ui.task_file, "task.md")
			ui.roles.select(0)
			ui.save_agent()
			stage = 5
		5:
			if ui.agents.item_count != 1:
				return false
			ui.load_agent(0)
			ui.control("start")
			stage = 6
		6:
			if cafe.state.agents.get(managed_id, {}).get("status") != "agent.finished":
				return false
			if not cafe.characters.has(managed_id):
				push_error("Managed agent not visible in café")
				quit(1)
			if cafe.characters.ada.visible or cafe.activity_cards.ada.agent_id != managed_id:
				push_error("Idle placeholder/card must follow the managed worker")
				quit(1)
			if cafe.activity_cards.ada.status_label.text != "Finished":
				push_error("Managed completion must reach the activity card")
				quit(1)
			ui.refresh()
			stage = 7
		7:
			for record in ui.cache.get("executions", []):
				if record.status == "COMPLETED":
					execution_id = record.id
			if execution_id.is_empty():
				return false
			ui.selected_execution = execution_id
			ui.call_api("logs", "/executions/" + execution_id + "/logs")
			stage = 8
		8:
			if not "CODING" in ui.logs.text or not "TESTING" in ui.logs.text:
				return false
			ui.review_note.text = "Reviewed fixture result and recorded test evidence."
			ui.review(true)
			stage = 9
		9:
			var accepted := false
			for record in ui.cache.get("executions", []):
				accepted = accepted or (record.id == execution_id and record.acceptance == "ACCEPTED")
			if not accepted:
				return false
			ui.selected_execution = ""
			ui.definition_kind.select(0)
			ui.definition_file.text = "task.md"
			ui.markdown.text = "# Task\nfixture: wait"
			ui.save_definition()
			stage = 10
		10:
			if ui.cache.tasks[0].content != "# Task\nfixture: wait":
				return false
			ui.control("start")
			stage = 11
		11:
			if cafe.state.agents.get(managed_id, {}).get("status") == "agent.thinking":
				ui.control("stop")
				stage = 12
		12:
			if ui.cache.agents[0].state == "CANCELLED":
				print("Godot managed agent, Markdown, workspace, runtime, logs, acceptance and stop tests: PASS")
				quit(0)
	return false

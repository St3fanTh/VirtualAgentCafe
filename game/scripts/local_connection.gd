extends RefCounted

static func read_token(path: String, backend_url: String) -> String:
	if not FileAccess.file_exists(path):
		return ""
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 8192:
		return ""
	var parser := JSON.new()
	if parser.parse(file.get_as_text()) != OK:
		return ""
	var data = parser.data
	if not data is Dictionary or not data.get("backend_url") is String or not data.get("token") is String:
		return ""
	# Never send a saved local capability to a different backend.
	if data.backend_url.trim_suffix("/") != backend_url.trim_suffix("/"):
		return ""
	return data.token.strip_edges()

static func load_token(backend_url: String) -> String:
	var supplied := OS.get_environment("VAC_MANAGEMENT_TOKEN")
	if not supplied.is_empty():
		return supplied.strip_edges()
	var path := OS.get_environment("VAC_CONNECTION_FILE")
	if path.is_empty():
		path = ProjectSettings.globalize_path("res://").path_join("../.runtime/setup/godot-connection.json")
	return read_token(path, backend_url)

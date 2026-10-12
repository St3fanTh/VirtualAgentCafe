extends SceneTree

var cafe: Node
var directory := ""

func _initialize() -> void:
	directory = OS.get_environment("VAC_PREVIEW_DIR")
	if directory == "":
		push_error("Set VAC_PREVIEW_DIR to an existing directory")
		quit(1)
		return
	call_deferred("capture")

func save_frame(filename: String) -> void:
	await RenderingServer.frame_post_draw
	var screenshot := root.get_texture().get_image()
	if screenshot == null or screenshot.is_empty():
		push_error("Preview requires a rendering display; headless mode cannot capture shaders")
		quit(1)
		return
	var error := screenshot.save_png(directory.path_join(filename))
	if error != OK:
		push_error("Cannot save preview")
		quit(1)

func capture() -> void:
	cafe = load("res://scenes/cafe.tscn").instantiate()
	root.add_child(cafe)
	await create_timer(2.0).timeout
	# Freeze the latest observed demo state at its destination for stable comparisons.
	cafe.network.set_process(false)
	for id in cafe.state.agents:
		var character: Node2D = cafe.characters[id]
		character.reset_state(cafe.state.agents[id])
		character.position = character.destination()
		character.route.clear()
		character.set_process(false)
	await save_frame("cafe-effects.png")
	cafe.world.set_effects(false)
	await save_frame("cafe-without-effects.png")
	cafe.world.set_effects(true)
	cafe.select_agent("ada")
	await save_frame("cafe-task-panel.png")
	print("Rendered cafe preview: PASS")
	quit(0)

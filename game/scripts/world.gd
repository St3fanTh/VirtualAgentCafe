extends Node2D

const WoodShader = preload("res://shaders/wood.gdshader")
const GlassShader = preload("res://shaders/glass.gdshader")
const MonitorShader = preload("res://shaders/monitor.gdshader")
const SteamShader = preload("res://shaders/steam.gdshader")
const AtmosphereShader = preload("res://shaders/atmosphere.gdshader")
var effects_enabled := true
var effect_materials: Array[ShaderMaterial] = []
var monitors: Dictionary = {}
var active_statuses: Dictionary = {}

func shader_panel(area: Rect2, shader: Shader, depth: int) -> ShaderMaterial:
	var panel := ColorRect.new()
	panel.position = area.position
	panel.size = area.size
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.z_index = depth
	var shader_material := ShaderMaterial.new()
	shader_material.shader = shader
	panel.material = shader_material
	add_child(panel)
	effect_materials.append(shader_material)
	return shader_material

func set_effects(enabled: bool) -> void:
	effects_enabled = enabled
	for shader_material in effect_materials:
		shader_material.set_shader_parameter("strength", 1.0 if enabled else 0.0)

func set_agent_status(agent_id: String, status: String, detail := "") -> void:
	if not monitors.has(agent_id):
		return
	var color := Color("628b9a")
	match status:
		"agent.coding", "agent.finished": color = Color("7fe3b0")
		"agent.testing": color = Color("f5ce84")
		"agent.error": color = Color("f2818d")
		"agent.thinking": color = Color("ada4f0")
		"agent.message": color = Color("8cd4e1")
	monitors[agent_id].set_shader_parameter("activity_color", color)
	active_statuses[agent_id] = status == "agent.testing" or (status == "agent.waiting" and detail.begins_with("CLI:"))
	var lab_color := Color("d9b56c") if true in active_statuses.values() else Color("547b84")
	monitors.lab.set_shader_parameter("activity_color", lab_color)

func _ready() -> void:
	# Native tilemap generated from a tiny original pixel atlas; no external assets.
	var atlas := Image.create(32, 16, false, Image.FORMAT_RGBA8)
	for x in range(32):
		for y in range(16):
			var color := Color("685048") if x < 16 else Color("72594d")
			if y == 15 or x % 16 == 15:
				color = Color("443b3b")
			if y == 7 and x % 16 > 2:
				color = color.lightened(0.05)
			atlas.set_pixel(x, y, color)
	var source := TileSetAtlasSource.new()
	source.texture = ImageTexture.create_from_image(atlas)
	source.texture_region_size = Vector2i(16, 16)
	source.create_tile(Vector2i(0, 0))
	source.create_tile(Vector2i(1, 0))
	var tiles := TileSet.new()
	tiles.tile_size = Vector2i(16, 16)
	var source_id := tiles.add_source(source)
	var layer := TileMapLayer.new()
	layer.tile_set = tiles
	layer.z_index = -2
	var wood := ShaderMaterial.new()
	wood.shader = WoodShader
	layer.material = wood
	effect_materials.append(wood)
	for x in range(20):
		for y in range(10):
			layer.set_cell(Vector2i(x, y), source_id, Vector2i((x + y) % 2, 0))
	add_child(layer)
	for x in [16, 132, 240]:
		shader_panel(Rect2(x + 2, 6, 44, 14), GlassShader, 1)
	monitors.ada = shader_panel(Rect2(49, 25, 18, 10), MonitorShader, 1)
	monitors.turing = shader_panel(Rect2(101, 25, 18, 10), MonitorShader, 1)
	monitors.lab = shader_panel(Rect2(242, 39, 55, 11), MonitorShader, 1)
	shader_panel(Rect2(286, 77, 16, 29), SteamShader, 3)
	shader_panel(Rect2(0, 0, 320, 160), AtmosphereShader, 8)

func box(x: float, y: float, w: float, h: float, color: String) -> void:
	draw_rect(Rect2(x, y, w, h), Color(color))

func text(at: Vector2, value: String, color := Color("eadbc7")) -> void:
	# Render glyphs at viewport resolution instead of scaling a tiny bitmap font.
	draw_set_transform(at, 0.0, Vector2.ONE / maxf(1.0, get_global_transform().get_scale().x))
	draw_string(ThemeDB.fallback_font, Vector2.ZERO, value, HORIZONTAL_ALIGNMENT_LEFT, -1, 44, color)
	draw_set_transform(Vector2.ZERO)

func _draw() -> void:
	# Contact shadows and layered joinery keep furniture readable at larger sizes.
	for area in [Rect2(43, 48, 36, 16), Rect2(95, 48, 36, 16), Rect2(239, 50, 64, 16), Rect2(177, 130, 36, 8), Rect2(256, 139, 57, 11)]:
		draw_rect(area, Color(0.06, 0.04, 0.06, 0.24))
	box(0, 0, 320, 28, "2b293e")
	box(0, 27, 320, 3, "a7806d")
	for x in range(0, 320, 8):
		box(x, 28, 1, 2, "735c59")
	# Back-wall shelves, warm pendant lamps and small framed prints.
	box(182, 8, 42, 3, "a7806d")
	for x in range(185, 221, 7):
		box(x, 2, 4, 6, "927b77")
		box(x, 2, 1, 6, "d0a875")
	for x in [60, 112, 194, 283]:
		box(x, 0, 0.5, 8, "a17e67")
		box(x - 5, 8, 10, 3, "dcb386")
		box(x - 4, 11, 8, 1, "f9d7a2")
	# Windows, dusk skyline and indoor plants.
	for x in [16, 132, 240]:
		box(x, 4, 48, 18, "96879a")
		box(x + 2, 6, 44, 14, "444e75")
		box(x + 22, 5, 2, 16, "96879a")
		box(x + 3, 17, 42, 3, "30374d")
	for x in [12, 304]:
		box(x - 4, 54, 8, 10, "b97a65")
		box(x - 3, 37, 1, 18, "427b67")
		for leaf in range(5):
			var left := leaf % 2 == 0
			var center := Vector2(x - 2, 38 + leaf * 3)
			var tip := center + Vector2(-8 if left else 9, -5)
			draw_colored_polygon(PackedVector2Array([center, center + Vector2(-5 if left else 6, 0), tip, center + Vector2(-2 if left else 3, -4)]), Color("6aab7f") if left else Color("43856e"))
			draw_line(center, tip, Color("9bb991"), 0.4)
		box(x - 4, 54, 8, 1, "dbad88")
	# Soft patterned rugs under the seating and discussion table.
	box(40, 118, 85, 35, "4c6365")
	draw_rect(Rect2(42, 120, 81, 31), Color("78938b"), false, 0.6)
	for x in range(45, 121, 4):
		box(x, 151, 1, 3, "a4aa91")
	box(164, 105, 62, 35, "755963")
	draw_rect(Rect2(166, 107, 58, 31), Color("b58b82"), false, 0.6)
	# Coding desks, monitors, keyboard and coffee.
	for x in [44, 96]:
		box(x, 48, 33, 5, "342d3c")
		box(x, 39, 33, 10, "ba8668")
		box(x, 39, 33, 1, "e3b18b")
		box(x + 1, 48, 31, 1, "8c5f52")
		for seam in range(3):
			box(x + 1, 41 + seam * 2, 31, 0.3, "ac775f")
		box(x + 3, 23, 22, 15, "24283b")
		box(x + 5, 25, 18, 10, "4f8390")
		for row in range(3):
			box(x + 7, 27 + row * 2, 10 - row * 2, 1, "9edbb5")
		box(x + 12, 37, 5, 2, "24283b")
		box(x + 6, 42, 17, 3, "6c5665")
		for key in range(7):
			box(x + 7 + key * 2, 42.5, 1, 1, "b8aaa0")
		box(x + 27, 39, 4, 5, "edd3a1")
		box(x + 3, 53, 3, 9, "755768")
		box(x + 27, 53, 3, 9, "755768")
	text(Vector2(45, 87), "BACKEND / ADA")
	text(Vector2(97, 87), "FRONTEND / TURING")
	# Test station.
	box(239, 36, 61, 18, "739494")
	box(242, 39, 55, 11, "273449")
	for x in range(247, 293, 8):
		box(x, 42, 4, 4, "82c79e")
	box(244, 55, 3, 8, "394454")
	box(291, 55, 3, 8, "394454")
	text(Vector2(247, 87), "CLI TEST LAB")
	# Conversation nook, lounge and café counter.
	box(179, 119, 30, 13, "b98773")
	box(182, 116, 24, 3, "d6a381")
	box(189, 117, 4, 3, "f1d3a0")
	box(198, 117, 4, 3, "f1d3a0")
	text(Vector2(168, 147), "PEER EXCHANGE")
	box(47, 138, 72, 8, "8b6583")
	box(47, 145, 72, 7, "65465f")
	for x in [51, 72, 93]:
		box(x, 139, 19, 5, "a17c93")
		box(x + 1, 139, 17, 0.5, "bb97a6")
	text(Vector2(57, 158), "COFFEE / IDLE")
	box(260, 111, 48, 35, "714e52")
	box(257, 108, 54, 8, "d09a78")
	box(258, 108, 52, 1, "f0c297")
	for x in range(263, 306, 9):
		box(x, 118, 1, 27, "926759")
	# Decorative shelving and brass fittings on the coffee bar.
	box(272, 83, 24, 2, "bc8b71")
	for x in [274, 282, 290]:
		box(x, 78, 4, 5, "ead2a7")
		box(x + 1, 78, 2, 0.5, "fff0d1")
	box(263, 130, 9, 1, "c19b80")
	box(280, 130, 9, 1, "c19b80")
	text(Vector2(178, 91), "MEET. MAKE. REPEAT.", Color("c9a788"))
	box(266, 92, 21, 16, "343846")
	box(269, 95, 15, 6, "9babaa")
	box(291, 102, 6, 6, "eee1be")
	text(Vector2(267, 155), "CAFE")

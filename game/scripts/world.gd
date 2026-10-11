extends Node2D

func _ready() -> void:
	# Native tilemap generated from a tiny original pixel atlas; no external assets.
	var atlas := Image.create(32, 16, false, Image.FORMAT_RGBA8)
	for x in range(32):
		for y in range(16):
			var color := Color("554651") if x < 16 else Color("5d4c55")
			if y == 15 or x % 16 == 15:
				color = Color("403846")
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
	layer.z_index = -1
	for x in range(20):
		for y in range(10):
			layer.set_cell(Vector2i(x, y), source_id, Vector2i((x + y) % 2, 0))
	add_child(layer)

func box(x: float, y: float, w: float, h: float, color: String) -> void:
	draw_rect(Rect2(x, y, w, h), Color(color))

func text(at: Vector2, value: String, color := Color("eadbc7")) -> void:
	draw_string(ThemeDB.fallback_font, at, value, HORIZONTAL_ALIGNMENT_LEFT, -1, 7, color)

func _draw() -> void:
	box(0, 0, 320, 28, "2b293e")
	box(0, 27, 320, 3, "8c6470")
	# Windows, dusk skyline and indoor plants.
	for x in [16, 132, 240]:
		box(x, 4, 48, 18, "96879a")
		box(x + 2, 6, 44, 14, "444e75")
		box(x + 22, 5, 2, 16, "96879a")
		box(x + 3, 17, 42, 3, "30374d")
	for x in [12, 304]:
		box(x - 4, 54, 8, 10, "b97a65")
		box(x - 7, 42, 14, 12, "427b67")
		box(x - 3, 35, 6, 12, "6cad7f")
	# Coding desks, monitors, keyboard and coffee.
	for x in [44, 96]:
		box(x, 48, 33, 5, "342d3c")
		box(x, 39, 33, 10, "ba8668")
		box(x + 3, 23, 22, 15, "24283b")
		box(x + 5, 25, 18, 10, "4f8390")
		for row in range(3):
			box(x + 7, 27 + row * 2, 10 - row * 2, 1, "9edbb5")
		box(x + 12, 37, 5, 2, "24283b")
		box(x + 6, 42, 17, 3, "6c5665")
		box(x + 27, 39, 4, 5, "edd3a1")
		box(x + 3, 53, 3, 9, "755768")
		box(x + 27, 53, 3, 9, "755768")
	text(Vector2(45, 77), "CODE / ADA")
	text(Vector2(97, 77), "CODE / TURING")
	# Test station.
	box(239, 36, 61, 18, "739494")
	box(242, 39, 55, 11, "273449")
	for x in range(247, 293, 8):
		box(x, 42, 4, 4, "82c79e")
	box(244, 55, 3, 8, "394454")
	box(291, 55, 3, 8, "394454")
	text(Vector2(247, 78), "TEST LAB")
	# Conversation nook, lounge and café counter.
	box(179, 119, 30, 13, "b98773")
	box(182, 116, 24, 3, "d6a381")
	box(189, 117, 4, 3, "f1d3a0")
	box(198, 117, 4, 3, "f1d3a0")
	text(Vector2(168, 147), "CONVERSATION")
	box(47, 138, 72, 8, "8b6583")
	box(47, 145, 72, 7, "65465f")
	text(Vector2(57, 158), "COFFEE / WAIT")
	box(260, 111, 48, 35, "714e52")
	box(257, 108, 54, 8, "d09a78")
	box(266, 92, 21, 16, "343846")
	box(269, 95, 15, 6, "9babaa")
	box(291, 102, 6, 6, "eee1be")
	text(Vector2(267, 155), "CAFE")

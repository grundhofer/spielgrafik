extends SceneTree
## Baut res://tiles/harbour_tileset.tres aus den Atlanten und tiles/tiles.json (von scripts/build_tiles.py).
##   godot --headless --path demo --import
##   godot --headless --path demo --script res://tools/build_tileset.gd
## Je Ebene eine TileSetAtlasSource und ein Terrain-Set im Modus "Match Corners" mit einem Terrain gegen "leer":
## 15 Übergangskacheln mit Ecken-Bits (-1 = leer), volle Kacheln mit Varianten (probability), Wasser und
## Schaum als Kachel-Animation. Dasselbe TileSet taugt damit auch für das Terrain-Malen im Editor.

const ORDER := ["water", "sand", "grass", "stone", "jetty"]
const NAMES := {"water": "Wasser", "sand": "Sand", "grass": "Gras", "stone": "Kaipflaster", "jetty": "Steg"}
const COLORS := {"water": Color(0.1, 0.45, 0.6), "sand": Color(0.95, 0.8, 0.55), "grass": Color(0.35, 0.6, 0.3),
		"stone": Color(0.55, 0.57, 0.65), "jetty": Color(0.6, 0.4, 0.25)}
const CORNERS := [TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER, TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER,
		TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER, TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER]


func _init() -> void:
	var desc: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://tiles/tiles.json"))
	var ts := TileSet.new()
	ts.tile_size = Vector2i(16, 16)
	for i in ORDER.size():
		var lname: String = ORDER[i]
		var L: Dictionary = desc["layers"][lname]
		ts.add_terrain_set(i)
		ts.set_terrain_set_mode(i, TileSet.TERRAIN_MODE_MATCH_CORNERS)
		ts.add_terrain(i, 0)
		ts.set_terrain_name(i, 0, NAMES[lname])
		ts.set_terrain_color(i, 0, COLORS[lname])
		var src := TileSetAtlasSource.new()
		src.resource_name = NAMES[lname]
		src.texture = load("res://tiles/" + String(L["texture"]))
		src.texture_region_size = Vector2i(16, 16)
		ts.add_source(src, i)
		for t in L["tiles"]:
			var c := Vector2i(int(t["atlas"][0]), int(t["atlas"][1]))
			src.create_tile(c)
			var frames := int(t["frames"])
			if frames > 1:
				src.set_tile_animation_columns(c, frames)
				src.set_tile_animation_frames_count(c, frames)
				src.set_tile_animation_speed(c, 1.0)
				for f in frames:
					src.set_tile_animation_frame_duration(c, f, float(L["frame_duration"]))
			var td := src.get_tile_data(c, 0)
			td.terrain_set = i
			td.terrain = 0
			for k in 4:
				td.set_terrain_peering_bit(CORNERS[k], 0 if int(t["corners"][k]) == 1 else -1)
			td.probability = float(t["probability"])
	var err := ResourceSaver.save(ts, "res://tiles/harbour_tileset.tres")
	print("harbour_tileset.tres: ", error_string(err), ", Quellen ", ts.get_source_count())
	quit(0 if err == OK else 1)

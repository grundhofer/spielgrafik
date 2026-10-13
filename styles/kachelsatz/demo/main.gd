extends Node2D
## Kachelsätze & Autotiling: der Hafen von Lornholm als Kachelkarte in Draufsicht (426x240, Kacheln 16 px).
##
## Die Karte steht als Text in map/harbour.txt (eine logische Zelle je Zeichen). Fünf TileMapLayer liegen eine
## halbe Kachel versetzt darüber (Dual-Grid): Jede Anzeigekachel nimmt die vier logischen Zellen an ihren Ecken
## und sucht im TileSet die Kachel mit passenden Ecken-Bits (Terrain-Set "Match Corners" je Ebene).
## Wasser und Brandung sind Kachel-Animationen des TileSets, alles andere läuft über die aufsummierte Zeit.
##
## Benutzerargumente (nach "--"): --t0=<s> startet später (Dauerlauf-Prüfung), --tiles-only zeigt nur die
## Kachelebenen ohne Licht (Vergleich mit scripts/preview_map.py), --badger-only nur den Dachs auf Schwarz
## (Fußmessung), --godot-terrain füllt die Ebenen zum Vergleich mit set_cells_terrain_connect.

const T := 16
const LAYERS := ["water", "sand", "grass", "stone", "jetty"]
const LAYER_NAMES := ["Wasser", "Sand", "Gras", "Kai", "Steg"]
const COVERS := {"water": "*", "sand": "SGC", "grass": "G", "stone": "C", "jetty": "J"}
const SALT := {"water": 1, "sand": 2, "grass": 3, "stone": 4, "jetty": 5}
const CORNERS := [TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER, TileSet.CELL_NEIGHBOR_TOP_RIGHT_CORNER,
		TileSet.CELL_NEIGHBOR_BOTTOM_LEFT_CORNER, TileSet.CELL_NEIGHBOR_BOTTOM_RIGHT_CORNER]

# Requisiten: Name -> Fußpunkt (unten Mitte) in Weltpixeln
const PROPS := {
	"cottage": Vector2(54, 84), "lantern": Vector2(104, 88), "barrel_a": Vector2(186, 88),
	"barrel_b": Vector2(201, 91), "crates": Vector2(226, 90), "rope": Vector2(64, 124),
	"parcel": Vector2(170, 112), "boat_a": Vector2(110, 160), "boat_b": Vector2(197, 170),
	"lighthouse": Vector2(400, 116), "rock_a": Vector2(340, 158), "rock_b": Vector2(258, 76),
	"rock_c": Vector2(318, 30),
}
const WINDOW_POS := Vector2(72, 71)
const LAMP_POS := Vector2(113, 72)
const BEACON_POS := Vector2(400, 25)

# Dachs: Blatt mit 40x36-Zellen, Anker (Fußmitte) bei (20, 34); 8 Laufphasen, dann vorn, blinzeln, grüßen
const CELL := Vector2i(40, 36)
const ANCHOR := Vector2i(20, 34)
const WALK_FPS := 15.0
const WALK_STEP := 2           # px je Laufphase, gleich dem Rückweg des Standfußes (Füße rutschen nicht)
const WALK_START := 0.4
const WALK_FRAMES := 54        # endet auf Phase 6 (Füße beisammen), danach Drehung nach vorn
const BADGER_X0 := 38
const BADGER_Y := 96
const DUSK := Color(0.56, 0.58, 0.82)

var tileset: TileSet = preload("res://tiles/harbour_tileset.tres")
var rows := PackedStringArray()
var t := 0.0
var args := {}
var badger: Sprite2D
var boats := []
var gull: Sprite2D
var gull_shadow: Sprite2D
var tex_gull: Texture2D = preload("res://art/gull.png")
var tex_gull_flap: Texture2D = preload("res://art/gull_flap.png")
var lamp_light: PointLight2D
var window_light: PointLight2D
var beacon: PointLight2D
var beacon_glow: PointLight2D
var rng := RandomNumberGenerator.new()
var flicker := PackedFloat32Array()

@onready var karte: Node2D = $Welt/Karte
@onready var objekte: Node2D = $Welt/Objekte
@onready var effekte: Node2D = $Welt/Effekte
@onready var rauch: Node2D = $Welt/Rauch
@onready var ui: Node2D = $UI/Oberflaeche


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	t = float(args.get("t0", "0"))
	rows = _load_map("res://map/harbour.txt")
	for i in LAYERS.size():
		_build_layer(i)
	if args.has("tiles-only"):
		objekte.visible = false
		effekte.visible = false
		rauch.visible = false
		$UI.visible = false
		$Daemmerung.visible = false
		return
	_build_props()
	_build_badger()
	_build_lights()
	_build_gull()
	rng.seed = 4711
	for i in 400:
		flicker.append(rng.randf())
	if args.has("badger-only"):
		karte.visible = false
		for c in objekte.get_children():
			c.visible = c == badger
		effekte.visible = false
		rauch.visible = false
		$UI.visible = false
		$Daemmerung.visible = false
		badger.light_mask = 0
	_update(0.0)


# ------------------------------------------------------------------ Karte (Dual-Grid)
func _load_map(path: String) -> PackedStringArray:
	var out := PackedStringArray()
	for line in FileAccess.get_file_as_string(path).split("\n"):
		var s := line.strip_edges()
		if s != "" and not s.begins_with("#"):
			out.append(s)
	return out


func _cell(x: int, y: int) -> String:
	y = clampi(y, 0, rows.size() - 1)
	x = clampi(x, 0, rows[0].length() - 1)
	return rows[y][x]


func _lookup(source_id: int) -> Dictionary:
	## Ecken-Bits -> Liste [Atlas-Koordinate, Wahrscheinlichkeit], gelesen aus dem TileSet selbst
	var src := tileset.get_source(source_id) as TileSetAtlasSource
	var lk := {}
	for i in src.get_tiles_count():
		var c := src.get_tile_id(i)
		var td := src.get_tile_data(c, 0)
		var key := 0
		for k in 4:
			if td.get_terrain_peering_bit(CORNERS[k]) == 0:
				key |= 1 << k
		if not lk.has(key):
			lk[key] = []
		lk[key].append([c, td.probability])
	for key in lk:
		lk[key].sort_custom(func(a, b): return a[0].y < b[0].y)
	return lk


static func hash2(x: int, y: int, salt: int) -> float:
	var h := (x * 374761393 + y * 668265263 + salt * 2246822519) & 0xFFFFFFFF
	h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
	return float(h ^ (h >> 16)) / float(0xFFFFFFFF)


static func pick(cands: Array, h: float) -> Vector2i:
	var total := 0.0
	for c in cands:
		total += c[1]
	var acc := 0.0
	for c in cands:
		acc += c[1]
		if h * total < acc:
			return c[0]
	return cands[-1][0]


func _build_layer(i: int) -> void:
	var lname: String = LAYERS[i]
	var layer := TileMapLayer.new()
	layer.name = LAYER_NAMES[i]
	layer.tile_set = tileset
	layer.position = Vector2(-T / 2, -T / 2)
	layer.light_mask = 3
	karte.add_child(layer)
	if args.has("godot-terrain"):
		_fill_godot_terrain(layer, i)
		return
	var lk := _lookup(i)
	var cov: String = COVERS[lname]
	for dy in rows.size() + 1:
		for dx in rows[0].length() + 1:
			var cs := [_cell(dx - 1, dy - 1), _cell(dx, dy - 1), _cell(dx - 1, dy), _cell(dx, dy)]
			var key := 0
			for k in 4:
				if cov == "*" or cov.contains(cs[k]):
					key |= 1 << k
			if key == 0 or not lk.has(key):
				continue
			layer.set_cell(Vector2i(dx, dy), i, pick(lk[key], hash2(dx, dy, SALT[lname])))


func _fill_godot_terrain(layer: TileMapLayer, i: int) -> void:
	## Vergleich: Godots eigener Terrain-Löser malt die logischen Zellen (ohne Versatz) mit dem Terrain.
	layer.position = Vector2.ZERO
	var cov: String = COVERS[LAYERS[i]]
	var cells: Array[Vector2i] = []
	for y in rows.size():
		for x in rows[0].length():
			if cov == "*" or cov.contains(rows[y][x]):
				cells.append(Vector2i(x, y))
	layer.set_cells_terrain_connect(cells, i, 0, false)


# ------------------------------------------------------------------ Requisiten und Figur
func _sprite(tex: Texture2D, foot: Vector2) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.light_mask = 3          # Bit 2: vom Leuchtturmstrahl erfasst
	s.centered = false
	s.offset = Vector2(-floorf(tex.get_width() / 2.0), -tex.get_height())
	s.position = foot
	objekte.add_child(s)
	return s


func _build_props() -> void:
	for n in PROPS:
		var s := _sprite(load("res://art/%s.png" % n), PROPS[n])
		s.name = n
		if n == "lighthouse":
			s.light_mask = 1      # der Turm wird nicht von seinem eigenen Strahl beleuchtet
		if n.begins_with("boat"):
			boats.append([s, PROPS[n]])


func _build_badger() -> void:
	badger = Sprite2D.new()
	badger.name = "Dachs"
	badger.texture = load("res://art/badger.png")
	badger.centered = false
	badger.region_enabled = true
	badger.light_mask = 3
	badger.offset = -Vector2(ANCHOR)
	objekte.add_child(badger)


func _badger_frame(i: int) -> void:
	badger.region_rect = Rect2(i * CELL.x, 0, CELL.x, CELL.y)


func _update_badger() -> void:
	var tw := t - WALK_START
	if tw < 0.0:
		_badger_frame(8)
		badger.position = Vector2(BADGER_X0, BADGER_Y)
		return
	var n := int(floor(tw * WALK_FPS + 1e-6))
	if n <= WALK_FRAMES:
		_badger_frame(n % 8)
		badger.position = Vector2(BADGER_X0 + WALK_STEP * n, BADGER_Y)
		return
	badger.position = Vector2(BADGER_X0 + WALK_STEP * WALK_FRAMES, BADGER_Y)
	var ts := tw - float(WALK_FRAMES + 1) / WALK_FPS
	var f := 8
	if ts > 0.5 and ts < 0.65:
		f = 9                      # blinzeln
	elif ts > 0.9 and ts < 1.7:
		f = 10                     # grüßen
	_badger_frame(f)


# ------------------------------------------------------------------ Licht und Umgebung
func _light(tex: String, pos: Vector2, col: Color, energy: float, scale_: float) -> PointLight2D:
	var l := PointLight2D.new()
	l.texture = load(tex)
	l.position = pos
	l.color = col
	l.energy = energy
	l.texture_scale = scale_
	effekte.add_child(l)
	return l


func _build_lights() -> void:
	$Daemmerung.color = DUSK
	window_light = _light("res://art/light_round.png", WINDOW_POS + Vector2(0, 10), Color(1.0, 0.72, 0.38), 0.85, 0.75)
	lamp_light = _light("res://art/light_round.png", LAMP_POS + Vector2(0, 6), Color(1.0, 0.70, 0.36), 1.1, 1.05)
	beacon_glow = _light("res://art/light_round.png", BEACON_POS, Color(1.0, 0.85, 0.55), 1.4, 0.32)
	beacon = _light("res://art/light_beam.png", BEACON_POS, Color(1.0, 0.92, 0.7), 0.75, 1.8)
	beacon.range_item_cull_mask = 2


func _build_gull() -> void:
	gull_shadow = Sprite2D.new()
	gull_shadow.texture = tex_gull
	gull_shadow.modulate = Color(0, 0.05, 0.1, 0.35)
	gull_shadow.z_index = 5
	effekte.add_child(gull_shadow)
	gull = Sprite2D.new()
	gull.texture = tex_gull
	gull.z_index = 6
	gull.flip_h = true
	effekte.add_child(gull)


func _update(_delta: float) -> void:
	_update_badger()
	# Boote schaukeln um ganze Pixel
	for i in boats.size():
		var b: Sprite2D = boats[i][0]
		var base: Vector2 = boats[i][1]
		b.position = base + Vector2(0, roundf(sin(t * 2.2 + i * 2.1) * 0.9))
	# Laterne und Fenster flackern (feste Zufallsfolge, 12 Werte je Sekunde, linear überblendet)
	var k := t * 12.0
	var i0 := int(k) % flicker.size()
	var fr: float = k - floorf(k)
	var fl := lerpf(flicker[i0], flicker[(i0 + 1) % flicker.size()], fr)
	lamp_light.energy = 0.95 + 0.3 * fl
	window_light.energy = 0.8 + 0.08 * sin(t * 3.1)
	# Leuchtfeuer: Strahl dreht sich, Lampe glimmt auf, wenn der Strahl vorbeikommt
	# 95° (unten) bis 215° (links oben) in 6 s: der Strahl streicht über Wasser, Kai und Bucht
	beacon.rotation = deg_to_rad(95.0 + 20.0 * t)
	beacon_glow.energy = 1.2 + 0.4 * sin(t * 5.0) * sin(t * 5.0)
	# Möwe fliegt von rechts nach links über die Bucht, mit Schatten am Boden
	var gx := 450.0 - fmod(t * 52.0, 560.0)
	var gy := 44.0 + sin(t * 1.3) * 10.0
	gull.position = Vector2(roundf(gx), roundf(gy))
	var flap := fmod(t, 2.4) < 0.9 and int(t * 6.0) % 2 == 1
	gull.texture = tex_gull_flap if flap else tex_gull
	gull_shadow.texture = gull.texture
	gull_shadow.flip_h = true
	gull_shadow.position = gull.position + Vector2(10, 30)
	rauch.set_time(t)
	ui.set_time(t)


func _process(delta: float) -> void:
	t += delta
	if args.has("tiles-only"):
		return
	_update(delta)

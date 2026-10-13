extends Node2D
# Isometrische Pixel-Art: der Hafen von Lornholm als Diorama-Insel in 2:1-Iso, 426×240, ganzzahlig ×3.
# Boden aus Würfelkacheln (TileMapLayer je Höhenebene, TileSet isometrisch 32×16), Requisiten und Dachs als
# Sprites mit Bodenpunkt, alles auf ganzen Pixeln. Zeit nur über delta (Movie Maker mit fester Bildrate),
# Zufall mit festem Seed.
#
# Benutzerargumente (nach "--"): --t0=<s> startet später (Dauerlauf-Prüfung), --solo zeigt nur den Dachs auf
# Schwarz (Fußmessung), --nolight blendet Lichter aus, --noui blendet die Oberfläche aus, --tiles zeigt nur die
# Kachelebenen und den Steg (Vergleich mit der Python-Zusammensetzung in scripts/build_tiles.py).

const ORIGIN := Vector2(120, 66)          # obere Ecke von Zelle (0, 0) auf Höhe 0
const WALK_FPS := 15.0
const WALK_CYCLES := 5
const HALT_BACK := Vector2(2, 1)           # Hülle beim Halt zurück, damit der Standfuß nicht springt
const BADGER_START := Vector2(1.0, 5.375)  # Zelle; Bildpunkt ganzzahlig
const BEAM_PERIOD := 5.0

var t := 0.0
var t0 := 0.0
var solo := false
var nolight := false
var noui := false
var tiles_only := false

var map: Dictionary
var props: Dictionary
var binfo: Dictionary

var objects: Node2D
var badger_root: Node2D
var badger: Sprite2D
var badger_shadow: Sprite2D
var badger_start_px: Vector2
var boats := []
var beam_node: Node2D
var beam_outer: Polygon2D
var beam_inner: Polygon2D
var beacon: Sprite2D
var flare: Sprite2D
var lamp_halo: Sprite2D
var lamp_pool: Sprite2D
var window_halos := []
var window_pool: Sprite2D
var smoke_root: Node2D
var smoke_src := Vector2.ZERO
var puffs := []
var gulls := []
var clouds := []
var stars_node: Node2D
var star_list: Array = []
var cursor: Sprite2D
var tex := {}
var rng := RandomNumberGenerator.new()
var flicker := 1.0
var flicker_next := 0.0
var ui: Control


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--solo":
			solo = true
		elif a == "--nolight":
			nolight = true
		elif a == "--noui":
			noui = true
		elif a == "--tiles":
			tiles_only = true
	rng.seed = 20261013
	map = JSON.parse_string(FileAccess.get_file_as_string("res://map/harbour.json"))
	props = JSON.parse_string(FileAccess.get_file_as_string("res://art/props.json"))
	binfo = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger.json"))
	for n in ["smoke_0", "smoke_1", "smoke_2", "smoke_3", "smoke_0_f", "smoke_1_f", "smoke_2_f", "smoke_3_f",
			"gull_0", "gull_1", "gull_2", "cursor_0", "cursor_1", "halo_lamp", "halo_lamp_small"]:
		tex[n] = load("res://art/fx/%s.png" % n)
	if solo:
		RenderingServer.set_default_clear_color(Color.BLACK)
		_build_badger(self)
		_update(0.0)
		return
	_build_sky()
	_build_world()
	if not noui:
		var layer := CanvasLayer.new()
		add_child(layer)
		ui = preload("res://ui.gd").new()
		ui.main = self
		layer.add_child(ui)
	_update(0.0)
	if tiles_only:
		RenderingServer.set_default_clear_color(Color.BLACK)
		for c in get_children():
			if not (c is TileMapLayer) and c != ui:
				c.visible = false


func iso(cx: float, cy: float, h: float) -> Vector2:
	return (ORIGIN + Vector2(16.0 * (cx - cy), 8.0 * (cx + cy) - h)).round()


func sprite_at(texture: Texture2D, anchor: Vector2, pos: Vector2, parent: Node) -> Node2D:
	# Hülle am Bodenpunkt (für y-Sortierung), Sprite darin um den Ankerpunkt versetzt
	var w := Node2D.new()
	w.position = pos
	var s := Sprite2D.new()
	s.texture = texture
	s.centered = false
	s.offset = -anchor
	w.add_child(s)
	parent.add_child(w)
	return w


func additive() -> CanvasItemMaterial:
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	return m


# --------------------------------------------------------------------------------------------------------
func _build_sky() -> void:
	var sky := Sprite2D.new()
	sky.texture = load("res://art/sky.png")
	sky.centered = false
	sky.z_index = -20
	add_child(sky)
	star_list = JSON.parse_string(FileAccess.get_file_as_string("res://art/fx/stars.json")).stars
	stars_node = Node2D.new()
	stars_node.z_index = -19
	stars_node.draw.connect(_draw_stars)
	add_child(stars_node)
	var cl := [["cloud_0", Vector2(-14, 136)], ["cloud_2", Vector2(24, 168)], ["cloud_1", Vector2(244, 198)],
			["cloud_0", Vector2(190, 214)]]
	for c in cl:
		var s := Sprite2D.new()
		s.texture = load("res://art/fx/%s.png" % c[0])
		s.centered = false
		s.z_index = -18
		add_child(s)
		clouds.append([s, c[1]])


func _draw_stars() -> void:
	var bright := Color("f2ecdc")
	var dim := Color("8c86a8")
	for s in star_list:
		var phase: float = s[3]
		var on := int(floor(t * 2.0 + phase * 13.0)) % 5 != 0
		var c := bright if on else dim
		if s[2] == 1:
			c = bright
			stars_node.draw_rect(Rect2(s[0], s[1], 1, 1), c)
			if on:
				stars_node.draw_rect(Rect2(s[0] - 1, s[1], 1, 1), dim)
				stars_node.draw_rect(Rect2(s[0] + 1, s[1], 1, 1), dim)
				stars_node.draw_rect(Rect2(s[0], s[1] - 1, 1, 1), dim)
				stars_node.draw_rect(Rect2(s[0], s[1] + 1, 1, 1), dim)
		else:
			stars_node.draw_rect(Rect2(s[0], s[1], 1, 1), c if phase > 0.4 else dim)


# --------------------------------------------------------------------------------------------------------
func _build_world() -> void:
	var ts := TileSet.new()
	ts.tile_shape = TileSet.TILE_SHAPE_ISOMETRIC
	ts.tile_layout = TileSet.TILE_LAYOUT_DIAMOND_DOWN
	ts.tile_size = Vector2i(32, 16)
	var src := TileSetAtlasSource.new()
	src.texture = load("res://art/tiles.png")
	src.texture_region_size = Vector2i(32, 24)
	for ti in map.tiles:
		var c := Vector2i(0, int(ti.row))
		src.create_tile(c)
		if int(ti.frames) > 1:
			src.set_tile_animation_columns(c, 0)
			src.set_tile_animation_frames_count(c, int(ti.frames))
			src.set_tile_animation_speed(c, 5.0)
	ts.add_source(src, 0)
	var jsrc := TileSetAtlasSource.new()
	jsrc.texture = load("res://art/jetty.png")
	jsrc.texture_region_size = Vector2i(32, 32)
	jsrc.create_tile(Vector2i(0, 0))
	ts.add_source(jsrc, 1)

	# Kachelbild 32×24 wird um die Zellmitte zentriert gezeichnet; die Raute liegt im Bild 4 px über der
	# Bildmitte, deshalb jede Ebene 4 px tiefer (Steg 32×32: 8 px).
	var base := ORIGIN - Vector2(16, 0)
	for L in range(-3, 3):
		if L == 0:
			_build_water_things(ts, base)
		var layer := TileMapLayer.new()
		layer.name = "Level%d" % L
		layer.tile_set = ts
		layer.y_sort_enabled = true
		layer.position = base + Vector2(0, -8 * L - 8 + 4)
		for c in map.layers[str(L)]:
			layer.set_cell(Vector2i(int(c[0]), int(c[1])), 0, Vector2i(int(c[2]), int(c[3])))
		add_child(layer)

	# Lichtpfützen und Schatten auf dem Boden
	var ground := Node2D.new()
	ground.z_index = 1
	add_child(ground)
	var lantern_pos := iso(5.85, 4.1, 8)
	lamp_pool = Sprite2D.new()
	lamp_pool.texture = load("res://art/fx/pool_lamp.png")
	lamp_pool.material = additive()
	lamp_pool.position = lantern_pos + Vector2(-4, 2)
	ground.add_child(lamp_pool)
	var cottage_pos := iso(1.15, 2.9, 8)
	window_pool = Sprite2D.new()
	window_pool.texture = load("res://art/fx/pool_window.png")
	window_pool.material = additive()
	window_pool.position = cottage_pos + Vector2(-22, 14)
	ground.add_child(window_pool)
	var shadows := [["shadow_small", 0.45, 4.3], ["shadow_small", 0.3, 4.8], ["shadow_crates", 7.45, 6.45],
			["shadow_small", 4.3, 4.4]]
	for sh in shadows:
		var s := Sprite2D.new()
		s.texture = load("res://art/fx/%s.png" % sh[0])
		s.position = iso(sh[1], sh[2], 8)
		ground.add_child(s)
	badger_shadow = Sprite2D.new()
	badger_shadow.texture = load("res://art/fx/shadow_badger.png")
	ground.add_child(badger_shadow)
	cursor = Sprite2D.new()
	cursor.position = iso(5.5, 5.5, 8)
	cursor.visible = false
	ground.add_child(cursor)

	# Objekte, nach Bodenpunkt sortiert
	objects = Node2D.new()
	objects.y_sort_enabled = true
	objects.z_index = 2
	add_child(objects)
	_prop("cottage", 1.15, 2.9, 8)
	_prop("lighthouse", 9.5, 0.5, 24)
	_prop("barrel", 0.45, 4.3, 8)
	_prop("barrel", 0.3, 4.8, 8)
	_prop("crates", 7.45, 6.45, 8)
	_prop("rope", 4.3, 4.4, 8)
	_prop("lantern", 5.85, 4.1, 8)
	for b in [[3.6, 4.08], [6.75, 4.2], [7.9, 5.12], [7.9, 6.4]]:
		sprite_at(load("res://art/bollard.png"), Vector2(2, 7), iso(b[0], b[1], 8), objects)
	sprite_at(load("res://art/parcel.png"), Vector2(6, 8), iso(5.5, 5.5, 8), objects)
	# Grasbüschel auf Gras-Oberseiten (fester Seed)
	for key in map.cells.keys():
		var cell = map.cells[key]
		var code: String = cell[0]
		if code in ["G", "H", "R"]:
			var xy: PackedStringArray = key.split(",")
			var cx := float(xy[0]) + rng.randf_range(0.2, 0.8)
			var cy := float(xy[1]) + rng.randf_range(0.2, 0.8)
			if code == "G" and cx < 2.4 and cy > 1.8:
				continue      # unter dem Häuschen
			if code == "R" and abs(cx - 9.5) < 0.9 and abs(cy - 0.5) < 0.9:
				continue      # unter dem Leuchtturm
			var h := 8.0 * float(cell[1]) + 8.0
			sprite_at(load("res://art/tuft_%d.png" % (rng.randi() % 3)), Vector2(2, 2), iso(cx, cy, h), objects)
	_build_badger(objects)

	# Lichter über den Objekten
	var lights := Node2D.new()
	lights.z_index = 4
	add_child(lights)
	var lp: Dictionary = props.lantern
	lamp_halo = Sprite2D.new()
	lamp_halo.texture = tex.halo_lamp
	lamp_halo.material = additive()
	lamp_halo.position = lantern_pos - Vector2(lp.anchor[0], lp.anchor[1]) + Vector2(5, 12)
	lights.add_child(lamp_halo)
	var cp: Dictionary = props.cottage
	for wpos in [Vector2(16, 54), Vector2(59, 57)]:
		var h := Sprite2D.new()
		h.texture = load("res://art/fx/halo_window.png")
		h.material = additive()
		h.position = cottage_pos - Vector2(cp.anchor[0], cp.anchor[1]) + wpos
		lights.add_child(h)
		window_halos.append(h)
	smoke_src = cottage_pos - Vector2(cp.anchor[0], cp.anchor[1]) + Vector2(31, 1)
	var lh: Dictionary = props.lighthouse
	# Lampe auf der Turmachse (Bodenpunkt), 15 px unter der Spriteoberkante
	var lamp := iso(9.5, 0.5, 24) - Vector2(lh.anchor[0], lh.anchor[1]) + Vector2(lh.anchor[0], 15)
	beacon = Sprite2D.new()
	beacon.texture = load("res://art/fx/halo_beacon.png")
	beacon.material = additive()
	beacon.position = lamp
	lights.add_child(beacon)
	flare = Sprite2D.new()
	flare.texture = load("res://art/fx/flare.png")
	flare.material = additive()
	flare.position = lamp
	lights.add_child(flare)
	beam_node = Node2D.new()
	beam_node.position = lamp
	add_child(beam_node)
	var sh := ShaderMaterial.new()
	sh.shader = load("res://shaders/light_dither.gdshader")
	beam_outer = Polygon2D.new()
	beam_outer.material = sh
	beam_outer.color = Color("fff0c0")
	beam_inner = Polygon2D.new()
	beam_inner.material = sh
	beam_inner.color = Color("fff6dc")
	beam_node.add_child(beam_outer)
	beam_node.add_child(beam_inner)
	if nolight:
		for n in [lamp_pool, window_pool, lamp_halo, beacon, beam_node, flare]:
			n.visible = false
		for h in window_halos:
			h.visible = false

	smoke_root = Node2D.new()
	smoke_root.z_index = 5
	add_child(smoke_root)
	for i in range(8):                      # Rauch schon vorhanden zu Beginn: Ballen mit negativem Geburtsdatum
		puffs.append({"born": -3.4 + i * 0.45, "node": null})
	for g in [[-14.0, 26.0, 21.0, 0.0, 1.0], [300.0, 12.0, -16.0, 0.35, 0.7]]:
		var s := Sprite2D.new()
		s.centered = false
		s.z_index = 6
		s.flip_h = g[2] < 0
		add_child(s)
		gulls.append({"node": s, "x0": g[0], "y0": g[1], "vx": g[2], "ph": g[3], "amp": g[4]})


func _build_water_things(ts: TileSet, base: Vector2) -> void:
	# zwischen Wasser (Ebene −1) und Kai (Ebene 0): Felsen, Boot A, Steg, Boot B
	for r in [["rock_0", 10.3, 3.5], ["rock_1", 7.6, 0.4], ["rock_1", 9.4, 5.9]]:
		var tx: Texture2D = load("res://art/%s.png" % r[0])
		sprite_at(tx, Vector2(tx.get_width() / 2, tx.get_height() - 2), iso(r[1], r[2], -4), self)
	boats.append([_prop("boat_a", 4.1, 1.7, -4, self), 0.0])
	var jetty := TileMapLayer.new()
	jetty.name = "Jetty"
	jetty.tile_set = ts
	jetty.y_sort_enabled = true
	jetty.position = base + Vector2(0, -8 + 8)
	for c in map.jetty:
		jetty.set_cell(Vector2i(int(c[0]), int(c[1])), 1, Vector2i(0, 0))
	add_child(jetty)
	boats.append([_prop("boat_b", 8.45, 4.55, -4, self), 1.3])


func _prop(name: String, cx: float, cy: float, h: float, parent: Node = null) -> Node2D:
	var p: Dictionary = props[name]
	return sprite_at(load("res://art/props/%s.png" % name), Vector2(p.anchor[0], p.anchor[1]), iso(cx, cy, h),
			parent if parent else objects)


func _build_badger(parent: Node) -> void:
	badger_start_px = iso(BADGER_START.x, BADGER_START.y, 8)
	badger_root = Node2D.new()
	parent.add_child(badger_root)
	badger = Sprite2D.new()
	badger.texture = load("res://art/badger.png")
	badger.hframes = 16
	badger.vframes = 4
	badger.centered = false
	badger.offset = -Vector2(binfo.anchor[0], binfo.anchor[1])
	badger_root.add_child(badger)


# --------------------------------------------------------------------------------------------------------
func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(_delta: float) -> void:
	var tt := t + t0
	var n := int(floor(tt * 30.0 + 0.5))          # Aufnahmebild (30 fps), ganzzahlig gegen Rundungsfehler
	_update_badger(n)
	if solo:
		return
	# Boote schaukeln um ganze Pixel
	for b in boats:
		var node: Node2D = b[0]
		var base_y: float = node.get_meta("y0", node.position.y)
		node.set_meta("y0", base_y)
		node.position.y = base_y + round(sin(tt * TAU / 2.4 + b[1]) * 1.0)
	# Wolken ziehen langsam, ganze Pixel
	for c in clouds:
		var s: Sprite2D = c[0]
		var p: Vector2 = c[1]
		s.position = Vector2(round(fposmod(p.x - tt * 2.0 + 90.0, 400.0) - 90.0), p.y)
	stars_node.queue_redraw()
	# Leuchtturm: Strahl dreht, hinter dem Turm, wenn er vom Betrachter weg zeigt
	var phi := -PI * 0.25 + TAU * (tt - 1.6) / BEAM_PERIOD
	# Zeigt der Strahl zum Betrachter, wäre er nur ein heller Fleck über dem Turm: dort ausblenden, dafür blitzt
	# die Lampe auf
	var away := 1.0 - pow(max(0.0, cos(phi + PI * 0.25)), 3.0)
	_set_beam(beam_outer, phi, 0.11, 150.0, 0.42 * away)
	_set_beam(beam_inner, phi, 0.045, 140.0, 0.55 * away)
	var dy := cos(phi) - sin(phi)
	beam_node.z_index = 3 if dy > -0.15 else 1
	var toward := pow(max(0.0, cos(phi + PI * 0.25)), 6.0)
	beacon.modulate.a = 0.55 + 0.45 * snapped(toward, 0.34)
	flare.visible = toward > 0.35 and not nolight
	flare.modulate.a = 0.5 if toward < 0.75 else 1.0
	# Laterne flackert (Stufen, fester Seed)
	if tt >= flicker_next:
		flicker = [1.0, 0.85, 1.0, 0.7, 1.0, 0.9][rng.randi() % 6]
		flicker_next = tt + rng.randf_range(0.08, 0.22)
	lamp_halo.modulate.a = flicker
	lamp_halo.texture = tex.halo_lamp if flicker > 0.8 else tex.halo_lamp_small
	lamp_pool.modulate.a = 0.75 + 0.25 * flicker
	for h in window_halos:
		h.modulate.a = 0.85 + 0.15 * (1.0 if (n / 7) % 9 != 0 else 0.0)
	_update_smoke(tt)
	_update_gulls(tt, n)
	# Kachel-Cursor auf dem Paket, sobald der Dachs steht
	var stop_t := WALK_CYCLES * 10.0 / WALK_FPS
	cursor.visible = tt > stop_t + 0.2
	cursor.texture = tex.cursor_0 if (n / 9) % 2 == 0 else tex.cursor_1
	if ui:
		ui.t = tt
		ui.queue_redraw()


func _set_beam(poly: Polygon2D, phi: float, half: float, length: float, alpha: float) -> void:
	var pts := PackedVector2Array([Vector2.ZERO, _beam_dir(phi - half) * length, _beam_dir(phi + half) * length])
	poly.polygon = pts
	poly.vertex_colors = PackedColorArray([Color(1, 1, 1, alpha), Color(1, 1, 1, 0.0), Color(1, 1, 1, 0.0)])


func _beam_dir(phi: float) -> Vector2:
	# Weltrichtung (cos, sin) in der Bodenebene -> 2:1-Iso-Bildrichtung
	return Vector2(0.7071 * (cos(phi) + sin(phi)), 0.3536 * (cos(phi) - sin(phi)))


func _update_badger(n: int) -> void:
	var walk_frames := WALK_CYCLES * 10
	var f := n / 2                                    # Laufbild bei 15 Bildern/s
	var rows: Dictionary = binfo.rows
	var pos := badger_start_px
	var frame := 0
	var shadow_off := Vector2.ZERO
	if f < walk_frames:
		var cyc := f / 10
		var i := f % 10
		pos = badger_start_px + Vector2(10, 5) * cyc
		frame = int(rows.walk_se.row) * 16 + i
		shadow_off = Vector2(i, round(i * 0.5))
	else:
		# Halt: Das letzte Laufbild (Zyklus 4, Bild 9) hat den aufgesetzten Fuß bei etwa +(8, 4) im Zyklus, nicht
		# bei +(10, 5). Die Hülle deshalb um (2, 1) zurück, damit der Fuß beim Wechsel zu Idle pixelgleich bleibt
		# (gemessen mit scripts/measure_badger.py, "halt").
		pos = badger_start_px + Vector2(10, 5) * WALK_CYCLES - HALT_BACK
		var ts := n - walk_frames * 2                 # Aufnahmebilder seit dem Halt
		if ts < 15:                                   # 0,5 s stehen nach Südost, 6 Bilder/s (auf Fünfen)
			frame = int(rows.idle_se.row) * 16 + (ts / 5) % 12
		elif ts < 20:                                 # zur Kamera gedreht
			frame = int(rows.idle_s.row) * 16 + 0
		elif ts < 20 + 48:                            # winken, 10 Bilder/s
			frame = int(rows.wave_s.row) * 16 + min(15, (ts - 20) / 3)
		else:
			frame = int(rows.idle_s.row) * 16 + ((ts - 68) / 5) % 12
	badger_root.position = pos
	badger.frame = frame
	if badger_shadow:
		badger_shadow.position = pos + shadow_off + Vector2(0, 1)


func _update_smoke(tt: float) -> void:
	var period := 0.45
	var k := int(floor(tt / period))
	while puffs.size() > 0 and tt - float(puffs[0].born) > 3.6:
		var p = puffs.pop_front()
		if p.node:
			p.node.queue_free()
	var last: float = puffs[puffs.size() - 1].born if puffs.size() > 0 else -99.0
	while last + period <= tt:
		last += period
		if tt - last <= 3.6:                      # beim Start mit --t0 keine längst verwehten Ballen anlegen
			puffs.append({"born": last, "node": null})
	if puffs.is_empty() or float(puffs[puffs.size() - 1].born) < last:
		puffs.append({"born": last, "node": null})
	for p in puffs:
		var age := tt - float(p.born)
		if age < 0:
			continue
		if p.node == null:
			var s := Sprite2D.new()
			smoke_root.add_child(s)
			p.node = s
		var size := mini(3, int(age / 0.8))
		var fade := age > 2.7
		var key := "smoke_%d%s" % [size, "_f" if fade else ""]
		p.node.texture = tex[key]
		# Wind von links: die Fahne zieht flach nach rechts über das Dach
		var sway := sin(age * 2.2 + float(p.born) * 3.0) * 1.5
		p.node.position = (smoke_src + Vector2(age * 11.0, -age * 4.5 + sway)).round()


func _update_gulls(tt: float, n: int) -> void:
	for g in gulls:
		var s: Sprite2D = g.node
		var x: float = fposmod(g.x0 + g.vx * tt + 20.0, 360.0) - 20.0      # Schleife für den Dauerlauf
		var y: float = g.y0 + sin(tt * 1.3 + g.ph * 6.0) * 4.0 * g.amp
		s.position = Vector2(round(x), round(y))
		# Flügelschlag 6 Bilder/s über den Aufnahmebild-Zähler: jede Stellung steht genau 5 Aufnahmebilder
		var fr: int = [0, 1, 2, 1][((n + int(round(g.ph * 20.0))) / 5) % 4]
		s.texture = tex["gull_%d" % fr]

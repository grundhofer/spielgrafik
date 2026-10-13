extends Node2D
## polygon-kino: Hafen von Lornholm aus flachen, einfarbigen Polygonen wie auf 16-Bit-Heimcomputern 1991–1993.
## 320x200 ohne Kantenglättung, 16 Farben je Einstellung (Palettenwechsel beim Schnitt), Szenenband 320x148,
## darunter die Textleiste (ui.gd).
## Hafen, Boote und alle Dachs-Phasen kommen als Polygonlisten aus data/scenes.json: rotoskopiert aus
## shared/3d mit blender/rotoscope.py (Kennbilder) und scripts/vectorize.py (Umrisse -> Polygone).
## Himmel (Ringverlauf), Meer, Wellen, Leuchtfeuer-Strahl, Rauch, Möwen und Sterne erzeugt dieses Skript.
## Zeit = aufsummiertes delta, Zufall nur mit festen Seeds.
## Prüfschalter nach "--": --t0=<s>, --shot=A|B (Einstellung festhalten), --probe-badger (nur Dachs auf
## Magenta), --probe-nobadger (ohne Dachs), --probe-nobake (jedes Polygon einzeln), --probe-stats (Zeichenaufrufe und sichtbare Polygone je Bild),
## --probe-norock (Boote ruhig, Vergleich für scripts/measure_boats.py).

const SCENE_H := 148
const CUT := 3.6                 # Schnitt Totale -> Nah
const WALK_FPS := 15.0           # Laufphasen je Sekunde (auf Zweien)
const WALK_PHASES := 8           # Phasen je Laufzyklus (zwei Schritte)
const WALK_STEPS := 44           # gezeigte Laufphasen bis zum Halt (2,93 s)
const WALK_START_PX := -14.0     # Fußpunkt beim Start (links außerhalb)
const WALK_M_PER_PHASE := 0.367 / 8.0   # 0,367 m je Sekunde Animationszeit, Phase = 1/8 s Animationszeit
const IDLE_FPS := 5.0
const WAVE_FPS := 10.0
const WAVE_START := 3.9          # Winken in der Naheinstellung
const BEAM_PERIOD := 4.4
const ANIM_TAGS := ["window", "lantern", "lamp"]

## Kunstangaben je Einstellung (Bildpunkte im Szenenband). sky/sea: Ringe [Farbe, Halbachse senkrecht, waagrecht]
## um den Glutpunkt am Horizont, von außen nach innen. lighter: Strahlfarbe je Himmelsfarbe.
const ART := {
	"A": {
		"glow_x": 112.0, "sky_base": 2,
		"sky": [[3, 64.0, 270.0], [4, 43.0, 200.0], [5, 27.0, 145.0], [6, 14.0, 98.0], [7, 5.0, 52.0]],
		"sea_base": 8, "sea": [[9, 12.0, 210.0], [5, 4.0, 110.0], [6, 1.6, 55.0]],
		"lighter": {2: 4, 3: 5, 4: 6, 5: 7, 6: 7, 7: 12},
		"clouds": [[70.0, 36.0, 110.0, 7.0, 2, 5], [268.0, 30.0, 120.0, 8.0, 2, 4], [160.0, 60.0, 70.0, 4.0, 3, 6]],
		"stars": 14, "star_max_y": 22.0, "glint": 6, "wave": 9, "wave_dy": 2.2, "wave_n": 7, "wave_len": 1.0,
		"gull_y": 46.0,
		"lantern_dim": 6, "flash": 12, "rock": 3.0, "heave": 1.0, "pool": [11.0, 2.0, 6], "shadow": [10.0, 2.0, 1],
	},
	"B": {
		"glow_x": 120.0, "sky_base": 2,
		"sky": [[3, 76.0, 300.0], [4, 40.0, 210.0], [5, 16.0, 135.0], [7, 5.0, 60.0]],
		"sea_base": 1, "sea": [[4, 3.0, 220.0], [5, 1.5, 120.0], [7, 0.6, 50.0]],
		"lighter": {2: 4, 3: 4, 4: 5, 5: 7, 7: 8},
		"clouds": [[40.0, 37.0, 120.0, 8.0, 2, 4], [290.0, 27.0, 110.0, 7.0, 2, 4], [150.0, 77.0, 80.0, 4.0, 3, 5]],
		"stars": 10, "star_max_y": 22.0, "glint": 5, "wave": 3, "wave_dy": 1.2, "wave_n": 12, "wave_len": 1.8,
		"gull_y": 31.0,
		"lantern_dim": 5, "flash": 8, "rock": 3.5, "heave": 1.0, "pool": [24.0, 3.0, 5], "shadow": [24.0, 4.0, 1],
	},
}

var data: Dictionary
var t := 0.0
var args := {}
var shots := {}
var ui: Node2D
var bad_polys := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	t = float(args.get("t0", "0"))
	var f := FileAccess.open("res://data/scenes.json", FileAccess.READ)
	data = JSON.parse_string(f.get_as_text())
	for key in ["A", "B"]:
		shots[key] = build_shot(key)
	if bad_polys > 0:
		push_error("%d Polygone ließen sich nicht in Dreiecke zerlegen (Godot zeichnet sie nicht)" % bad_polys)
	ui = preload("res://ui.gd").new()
	add_child(ui)
	if args.has("probe-badger"):
		ui.visible = false
	_apply(0.0)


func _process(delta: float) -> void:
	t += delta
	_apply(delta)
	if args.has("probe-stats"):
		var n := 0
		for c in shots[("A" if t < CUT else "B")].root.find_children("*", "", true, false):
			if (c is Polygon2D or c is MeshInstance2D) and c.is_visible_in_tree():
				n += 1
		print("stats t=%.2f draw_calls=%d objects=%d primitives=%d sichtbare_knoten=%d" % [t,
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_OBJECTS_IN_FRAME),
			RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_PRIMITIVES_IN_FRAME), n])


# ------------------------------------------------------------------------------------------------
# Aufbau
# ------------------------------------------------------------------------------------------------
func pal_color(s: Dictionary, i: int) -> Color:
	return s.pal[i]


func poly(parent: Node, pts: PackedVector2Array, col: Color) -> Polygon2D:
	var p := Polygon2D.new()
	p.polygon = pts
	p.color = col
	p.antialiased = false
	parent.add_child(p)
	return p


func data_poly(parent: Node, s: Dictionary, rec: Array, offset := Vector2.ZERO) -> Polygon2D:
	var flat: Array = rec[2]
	var pts := PackedVector2Array()
	for i in range(0, flat.size(), 2):
		pts.append(Vector2(flat[i], flat[i + 1]) - offset)
	if Geometry2D.triangulate_polygon(pts).is_empty():
		bad_polys += 1
	var p := poly(parent, pts, s.pal[int(rec[0])])
	var tag: String = data.tags[int(rec[1])]
	if tag != "":
		if not s.tags.has(tag):
			s.tags[tag] = []
		s.tags[tag].append(p)
	return p


## Unbewegte Polygone einer Ebene oder Phase in Zeichenreihenfolge zu einem Netz mit Eckfarben zusammenfassen
## (ein Zeichenaufruf statt eines je Polygon). Polygone mit Farbanimation (Fenster, Laterne, Lampe) bleiben
## eigene Polygon2D an ihrer Stelle in der Reihenfolge. Dreiecke wie Polygon2D über triangulate_polygon.
func data_polys(parent: Node, s: Dictionary, recs: Array, offset := Vector2.ZERO) -> void:
	var run := []
	for rec in recs:
		var tag: String = data.tags[int(rec[1])]
		if tag in ANIM_TAGS or args.has("probe-nobake"):
			flush_run(parent, s, run, offset)
			run = []
			data_poly(parent, s, rec, offset)
		else:
			run.append(rec)
	flush_run(parent, s, run, offset)


func flush_run(parent: Node, s: Dictionary, run: Array, offset: Vector2) -> void:
	if run.is_empty():
		return
	var verts := PackedVector2Array()
	var cols := PackedColorArray()
	var idx := PackedInt32Array()
	for rec in run:
		var flat: Array = rec[2]
		var pts := PackedVector2Array()
		for i in range(0, flat.size(), 2):
			pts.append(Vector2(flat[i], flat[i + 1]) - offset)
		var tri := Geometry2D.triangulate_polygon(pts)
		if tri.is_empty():
			bad_polys += 1
			continue
		var base := verts.size()
		verts.append_array(pts)
		var col: Color = s.pal[int(rec[0])]
		for i in pts.size():
			cols.append(col)
		for k in tri:
			idx.append(base + k)
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_COLOR] = cols
	arr[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	var mi := MeshInstance2D.new()
	mi.mesh = mesh
	parent.add_child(mi)


func rect_mesh(quads: Array) -> ArrayMesh:
	## Achsparallele Rechtecke (Sterne, Wellenstriche) als ein Netz mit Eckfarben.
	var verts := PackedVector2Array()
	var cols := PackedColorArray()
	var idx := PackedInt32Array()
	for q in quads:
		var r: Rect2 = q[0]
		var b := verts.size()
		verts.append_array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
		for i in 4:
			cols.append(q[1])
		idx.append_array([b, b + 1, b + 2, b, b + 2, b + 3])
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_COLOR] = cols
	arr[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	return mesh


func ellipse(c: Vector2, rx: float, ry: float, n: int) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in n:
		var a := TAU * float(i) / n
		pts.append(c + Vector2(roundf(rx * cos(a)), roundf(ry * sin(a))))
	return pts


func half_ellipse(cx: float, cy: float, ry: float, rx: float, up: bool, n := 14) -> PackedVector2Array:
	var pts := PackedVector2Array()
	for i in n + 1:
		var a := PI * float(i) / n
		var y := ry * sin(a)
		pts.append(Vector2(cx - rx * cos(a), cy - y if up else cy + y))
	return pts


func build_shot(key: String) -> Dictionary:
	var sd: Dictionary = data.shots[key]
	var art: Dictionary = ART[key]
	var s := {"key": key, "art": art, "tags": {}, "clips": {}, "pal": PackedColorArray()}
	for h in data.palettes[key]:
		s.pal.append(Color(h))
	var root := Node2D.new()
	root.name = "Shot" + key
	add_child(root)
	s.root = root
	var hz: float = sd.anchors.Horizon[1]
	s.horizon = hz
	var gx: float = art.glow_x
	var rng := RandomNumberGenerator.new()
	rng.seed = 1991 + key.unicode_at(0)
	# Himmel: Grundfarbe, darüber Ringe um den Glutpunkt (sparsamer Verlauf aus wenigen Stufen)
	var sky := Node2D.new()
	sky.name = "Sky"
	root.add_child(sky)
	poly(sky, PackedVector2Array([Vector2(-2, -2), Vector2(322, -2), Vector2(322, hz), Vector2(-2, hz)]),
		s.pal[art.sky_base])
	s.sky_rings = []
	for r in art.sky:
		var pts := half_ellipse(gx, hz, r[1], r[2], true)
		poly(sky, pts, s.pal[r[0]])
		s.sky_rings.append([pts, int(r[0])])
	# Sterne (1 Pixel) im obersten Band, alle in einem Netz
	s.stars = []
	for i in art.stars:
		var p := Vector2(rng.randi_range(2, 317), rng.randi_range(1, int(art.star_max_y)))
		s.stars.append([p, rng.randf() * TAU, rng.randf_range(1.5, 3.5)])
	s.star_mesh = MeshInstance2D.new()
	sky.add_child(s.star_mesh)
	# Strahl des Leuchtfeuers (Stücke je Himmelsring, je eine Stufe heller), hinter Wolken und Fels
	s.beam = Node2D.new()
	s.beam.name = "Beam"
	root.add_child(s.beam)
	s.beam_pool = []
	# Wolken: Streifen mit heller Unterkante
	var clouds := Node2D.new()
	clouds.name = "Clouds"
	root.add_child(clouds)
	s.clouds = []
	for c in art.clouds:
		var node := Node2D.new()
		clouds.add_child(node)
		node.position = Vector2(c[0], c[1])
		var body := cloud_shape(rng, c[2], c[3])
		var lit := PackedVector2Array()
		for v in body:
			lit.append(v + Vector2(1.0, 1.0))
		poly(node, lit, s.pal[c[5]])
		poly(node, body, s.pal[c[4]])
		s.clouds.append([node, Vector2(c[0], c[1]), rng.randf_range(0.6, 1.4), float(c[2])])
	# Meer: Grundfarbe und Spiegelung des Glutpunkts
	var sea := Node2D.new()
	sea.name = "Sea"
	root.add_child(sea)
	poly(sea, PackedVector2Array([Vector2(-2, hz), Vector2(322, hz), Vector2(322, SCENE_H), Vector2(-2, SCENE_H)]),
		s.pal[art.sea_base])
	for r in art.sea:
		poly(sea, half_ellipse(gx, hz, r[1], r[2], false), s.pal[r[0]])
	# Wellen: kurze waagrechte Striche, perspektivisch dichter zum Horizont, alle in einem Netz
	s.waves = []
	for row in 9:
		var y: float = hz + 1.5 + pow(row, 1.55) * art.wave_dy
		if y > SCENE_H - 1:
			break
		var cnt: int = art.wave_n + row
		for i in cnt:
			var x0 := rng.randf_range(-10, 330)
			var near_glow: bool = abs(x0 - gx) < 40.0 + row * 9.0
			var col: int = art.glint if near_glow else art.wave
			var l0: float = (2.0 + row * 1.3) * art.wave_len * rng.randf_range(0.7, 1.5)
			s.waves.append([col, x0, floor(y), l0, rng.randf() * TAU, rng.randf_range(1.5, 3.0)])
	s.wave_mesh = MeshInstance2D.new()
	s.wave_mesh.name = "Waves"
	root.add_child(s.wave_mesh)
	# Ebenen aus der Rotoskopie
	for layer in ["far", "boats", "near"]:
		var ln := Node2D.new()
		ln.name = layer.capitalize()
		root.add_child(ln)
		if layer == "boats":
			s.boats = {}
			for b in ["boatA", "boatB"]:
				var bn := Node2D.new()
				bn.name = b
				var anc: Array = sd.anchors["BoatA" if b == "boatA" else "BoatB"]
				bn.position = Vector2(round(anc[0]), round(anc[1]))
				ln.add_child(bn)
				s.boats[b] = bn
			s.boat_home = {"boatA": s.boats.boatA.position, "boatB": s.boats.boatB.position}
			var placed := 0
			for b in s.boats:
				var recs := []
				for rec in sd.layers[layer]:
					if data.tags[int(rec[1])] == b:
						recs.append(rec)
				if recs.is_empty():
					push_error("Einstellung %s: Boot %s hat 0 Polygone (Marke in scenes.json fehlt?)" % [key, b])
				placed += recs.size()
				data_polys(s.boats[b], s, recs, s.boats[b].position)
			if placed != sd.layers[layer].size():
				push_error("Einstellung %s: %d Bootspolygone ohne Marke boatA/boatB werden nicht gezeichnet" % [key,
					sd.layers[layer].size() - placed])
		else:
			data_polys(ln, s, sd.layers[layer])
		if layer == "near":
			s.near_node = ln
		if layer == "far":
			# Möwen fliegen vor dem Fels, hinter Booten und Kai
			s.gulls = []
			var gn := Node2D.new()
			gn.name = "Gulls"
			root.add_child(gn)
			for i in 2:
				var g := poly(gn, PackedVector2Array(), s.pal[0])
				s.gulls.append([g, rng.randf_range(0, 320), art.gull_y + i * 9.0, 14.0 + i * 5.0, rng.randf() * TAU])
	# Rauch aus dem Schornstein (nur wenn im Bild)
	s.smoke = []
	var ch: Array = sd.anchors.ChimneySmoke
	if ch[0] > 0 and ch[0] < 320 and ch[1] > 0:
		var sn := Node2D.new()
		sn.name = "Smoke"
		root.add_child(sn)
		for i in 6:
			s.smoke.append([poly(sn, PackedVector2Array(), s.pal[4]), float(i) / 6.0, rng.randf_range(0.0, TAU)])
		s.chimney = Vector2(ch[0], ch[1])
	# Lichtfleck unter der Laterne (flackert mit) und Bodenschatten des Dachses: flache Ellipsen
	var post: Array = sd.anchors.LanternPost
	var lan: Array = sd.anchors.LanternLight
	s.pool = poly(s.near_node, ellipse(Vector2(roundf(lan[0]), roundf(post[1])), art.pool[0], art.pool[1], 12),
		s.pal[art.pool[2]])
	s.shadow = poly(root, PackedVector2Array(), s.pal[art.shadow[2]])
	# Aufblitzen des Leuchtfeuers (vor dem Turm)
	s.flare = poly(root, PackedVector2Array(), s.pal[art.flash])
	# Dachs: je Phase ein Knoten mit seinen Polygonen
	var bd := Node2D.new()
	bd.name = "Badger"
	root.add_child(bd)
	s.badger = bd
	for cname in sd.clips:
		var arr := []
		for fr in sd.clips[cname].frames:
			var n := Node2D.new()
			n.visible = false
			bd.add_child(n)
			data_polys(n, s, fr)
			arr.append(n)
		s.clips[cname] = arr
	s.current = null
	if args.has("probe-badger"):
		for c in root.get_children():
			if c != bd:
				c.visible = false
		var bg := Polygon2D.new()
		bg.polygon = PackedVector2Array([Vector2(0, 0), Vector2(320, 0), Vector2(320, 200), Vector2(0, 200)])
		bg.color = Color(1, 0, 1)
		root.add_child(bg)
		root.move_child(bg, 0)
	if args.has("probe-nobadger"):
		bd.visible = false
	return s


func cloud_shape(rng: RandomNumberGenerator, length: float, thick: float) -> PackedVector2Array:
	## Wolkenbank als kantige Linse: spitze Enden, Oberkante in wenigen Buckeln, Unterkante flach gewölbt.
	var pts := PackedVector2Array()
	var n := 5
	pts.append(Vector2(-length * 0.5, 0))
	for i in range(1, n):
		var f := float(i) / n
		var x := -length * 0.5 + length * f + rng.randf_range(-3.0, 3.0)
		pts.append(Vector2(roundf(x), roundf(-thick * sin(PI * f) * rng.randf_range(0.55, 1.15))))
	pts.append(Vector2(length * 0.5, 0))
	for i in range(n - 1, 0, -1):
		var f := float(i) / n
		pts.append(Vector2(roundf(-length * 0.5 + length * f), roundf(thick * 0.3 * sin(PI * f))))
	return pts


# ------------------------------------------------------------------------------------------------
# Ablauf
# ------------------------------------------------------------------------------------------------
func _apply(_delta: float) -> void:
	var key := "A" if t < CUT else "B"
	if args.has("shot"):
		key = args["shot"]
	for k in shots:
		shots[k].root.visible = (k == key)
	var s: Dictionary = shots[key]
	var lt := t if key == "A" else t - CUT
	if key == "A":
		badger_a(s, t)
	else:
		badger_b(s, t)
	ambient(s, t)
	ui.set_time(t, key)


func show_frame(s: Dictionary, n: Node2D) -> void:
	if s.current == n:
		return
	if s.current != null:
		s.current.visible = false
	n.visible = true
	s.current = n


func clip_offset(s: Dictionary, cname: String, x_world: float) -> Vector2:
	var cl: Dictionary = data.shots[s.key].clips[cname]
	var k: Array = cl.px_per_m_x
	var dx: float = x_world - float(cl.at[0])
	return Vector2(round(dx * k[0]), round(dx * k[1]))


func place_shadow(s: Dictionary, cname: String) -> void:
	var cl: Dictionary = data.shots[s.key].clips[cname]
	var f: Vector2 = Vector2(roundf(cl.foot_px[0]), roundf(cl.foot_px[1])) + s.badger.position
	s.shadow.polygon = ellipse(f + Vector2(0, -1), s.art.shadow[0], s.art.shadow[1], 10)


func badger_a(s: Dictionary, tt: float) -> void:
	var cl: Dictionary = data.shots["A"].clips["walk"]
	var k: float = cl.px_per_m_x[0]
	var x_start: float = float(cl.at[0]) + (WALK_START_PX - float(cl.foot_px[0])) / k
	var step := int(floor(tt * WALK_FPS))
	if step < WALK_STEPS:
		var x := x_start + step * WALK_M_PER_PHASE
		show_frame(s, s.clips["walk"][step % WALK_PHASES])
		s.badger.position = clip_offset(s, "walk", x)
		place_shadow(s, "walk")
	else:
		var x_end := x_start + (WALK_STEPS - 1) * WALK_M_PER_PHASE
		var i: int = int(floor((tt - WALK_STEPS / WALK_FPS) * IDLE_FPS)) % s.clips["idle"].size()
		show_frame(s, s.clips["idle"][i])
		s.badger.position = clip_offset(s, "idle", x_end)
		place_shadow(s, "idle")


func badger_b(s: Dictionary, tt: float) -> void:
	s.badger.position = Vector2.ZERO
	place_shadow(s, "idle")
	var waves: Array = s.clips["wave"]
	var idles: Array = s.clips["idle"]
	if tt < WAVE_START:
		show_frame(s, idles[int(floor((tt - CUT) * IDLE_FPS)) % idles.size()])
	elif tt < WAVE_START + waves.size() / WAVE_FPS:
		show_frame(s, waves[int(floor((tt - WAVE_START) * WAVE_FPS))])
	else:
		var i := int(floor((tt - WAVE_START - waves.size() / WAVE_FPS) * IDLE_FPS))
		show_frame(s, idles[i % idles.size()])


func ambient(s: Dictionary, tt: float) -> void:
	var art: Dictionary = s.art
	var sd: Dictionary = data.shots[s.key]
	var q10: float = floorf(tt * 10.0) / 10.0          # Umgebung auf Dreien (10 Bilder/s)
	var q15: float = floorf(tt * 15.0) / 15.0
	# Leuchtfeuer: Strahl dreht sich, Lampe blitzt, wenn er zur Kamera zeigt
	var lamp: Array = sd.anchors.LighthouseLight
	var lp := Vector2(lamp[0], lamp[1])
	var th: float = TAU * q15 / BEAM_PERIOD + 0.6
	var c := cos(th)
	var toward := sin(th)                        # > 0: zur Kamera
	var length: float = 16.0 + 150.0 * absf(c)
	var w_end: float = 3.0 + 9.0 * (1.0 - absf(c))
	var dirx := 1.0 if c >= 0.0 else -1.0
	var beam := PackedVector2Array([lp + Vector2(0, -1.0), lp + Vector2(dirx * length, -w_end - 1.0),
		lp + Vector2(dirx * length, w_end - 1.0), lp + Vector2(0, 1.0)])
	var used := 0
	for ring in [[PackedVector2Array([Vector2(-2, -2), Vector2(322, -2), Vector2(322, s.horizon), Vector2(-2, s.horizon)]), art.sky_base]] + s.sky_rings:
		for piece in Geometry2D.intersect_polygons(beam, ring[0]):
			if used >= s.beam_pool.size():
				s.beam_pool.append(poly(s.beam, PackedVector2Array(), Color.BLACK))
			var p: Polygon2D = s.beam_pool[used]
			p.polygon = piece
			p.color = s.pal[art.lighter[ring[1]]]
			p.visible = true
			used += 1
	for i in range(used, s.beam_pool.size()):
		s.beam_pool[i].visible = false
	var flash := toward > 0.93
	for p in s.tags.get("lamp", []):
		p.color = s.pal[art.flash] if flash else s.pal[7]
	if flash:
		var r := 2.0 + 5.0 * (toward - 0.93) / 0.07
		s.flare.polygon = PackedVector2Array([lp + Vector2(-r * 2.2, 0), lp + Vector2(-1, -1), lp + Vector2(0, -r),
			lp + Vector2(1, -1), lp + Vector2(r * 2.2, 0), lp + Vector2(1, 1), lp + Vector2(0, r), lp + Vector2(-1, 1)])
		s.flare.visible = not args.has("probe-badger")
	else:
		s.flare.visible = false
	# Laterne flackert (feste Folge je 1/15 s)
	var lr := RandomNumberGenerator.new()
	lr.seed = 7000 + int(floor(tt * 15.0))
	var dim := lr.randf() < 0.32
	for p in s.tags.get("lantern", []):
		p.color = s.pal[art.lantern_dim] if dim else s.pal[7]
	s.pool.visible = not dim
	# Sterne funkeln
	var quads := []
	for st in s.stars:
		var on := sin(q10 * st[2] + st[1]) > -0.55
		quads.append([Rect2(st[0], Vector2(1, 1)), s.pal[(12 if s.key == "A" else 8) if on else 3]])
	s.star_mesh.mesh = rect_mesh(quads)
	# Wolken treiben langsam (ganze Pixel)
	for cd in s.clouds:
		var span: float = 320.0 + cd[3]
		var cx: float = fposmod(cd[1].x + q10 * cd[2] + cd[3] * 0.5, span) - cd[3] * 0.5
		cd[0].position = Vector2(roundf(cx), cd[1].y)
	# Wellen
	quads = []
	for wv in s.waves:
		var x: float = round(wv[1] + 2.5 * sin(q10 * wv[5] + wv[4]))
		var l: float = max(1.0, round(wv[3] * (0.65 + 0.35 * sin(q10 * wv[5] * 0.7 + wv[4] * 1.3))))
		quads.append([Rect2(x, wv[2], l, 1), s.pal[wv[0]]])
	s.wave_mesh.mesh = rect_mesh(quads)
	# Boote schaukeln um die Wasserlinie und heben sich um ganze Pixel
	if not args.has("probe-norock"):
		var rock: float = art.rock
		var heave: float = art.heave
		var pa: float = q10 * 2.2
		var pb: float = q10 * 1.8 + 1.7
		s.boats.boatA.rotation = deg_to_rad(rock * sin(pa))
		s.boats.boatB.rotation = deg_to_rad(rock * sin(pb))
		s.boats.boatA.position = s.boat_home.boatA + Vector2(0, roundf(heave * sin(pa - 1.3)))
		s.boats.boatB.position = s.boat_home.boatB + Vector2(0, roundf(heave * sin(pb - 1.3)))
	# Möwen: zwei Flügelstellungen (6 Bilder/s)
	for g in s.gulls:
		var gt: float = floorf(tt * 6.0) / 6.0
		var gx: float = fposmod(g[1] + gt * g[3], 360.0) - 20.0
		var gy: float = roundf(g[2] + 3.0 * sin(gt * 0.9 + g[4]))
		gx = round(gx)
		var up := int(floor(tt * 6.0 + g[4])) % 2 == 0
		var p := Vector2(gx, gy)
		if up:
			g[0].polygon = PackedVector2Array([p + Vector2(-4, -2), p + Vector2(0, 0), p + Vector2(4, -2),
				p + Vector2(4, -1), p + Vector2(0, 1), p + Vector2(-4, -1)])
		else:
			g[0].polygon = PackedVector2Array([p + Vector2(-4, 1), p + Vector2(-1, -1), p + Vector2(1, -1),
				p + Vector2(4, 1), p + Vector2(4, 2), p + Vector2(0, 0), p + Vector2(-4, 2)])
	# Rauch: Ballen steigen, wachsen, treiben nach rechts und verblassen in den Himmel
	if not s.smoke.is_empty():
		for sm in s.smoke:
			var life: float = fposmod(q10 / 2.4 + sm[1], 1.0)
			var r: float = 1.5 + 4.5 * life
			var cpos: Vector2 = s.chimney + Vector2(round(10.0 * life * life + 1.5 * sin(sm[2] + life * 5.0)), round(-26.0 * life))
			var pts := PackedVector2Array()
			for i in 7:
				var a: float = TAU * i / 7.0 + sm[2]
				pts.append(cpos + Vector2(round(cos(a) * r * 1.2), round(sin(a) * r * 0.9)))
			sm[0].polygon = pts
			sm[0].color = s.pal[4 if life < 0.45 else 3]

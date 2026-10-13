extends Node2D
## Vektorbildschirm: Jedes Bild wird als Anzeigeliste aus Linien neu aufgebaut (wie beim Vektorautomaten),
## von vorn nach hinten sortiert und gegen die Umrisse näherer Körper geschnitten (Verdeckung in Software).
## Die Linien landen als Strahlbänder additiv in einem HDR-Phosphorpuffer, der jedes Bild nur teilweise
## gelöscht wird (Nachleuchten); der Glow der WorldEnvironment liefert den weiten Lichthof.
##
## Benutzerargumente (nach "--"): --t0=SEK (Startzeit), --solo (nur Dachsbeine/Mütze, ohne Nachleuchten
## und Glow, zum Messen), --nopersist, --noglow, --noocclude (Vergleichsschalter), --stats (Zählwerte),
## --floor=X (Schwelle des Nachleuchtens; mit --nopersist und --floor=0 prüft man, dass das frische
## Strahlbild ohne Verzögerung im Phosphorpuffer ankommt), --preview, --sheet=font|badger.

const Wire := preload("res://wire.gd")
const Badger := preload("res://badger.gd")
const VecFont := preload("res://vecfont.gd")

const WHITE := Color(0.82, 0.9, 1.0)
const CYAN := Color(0.15, 0.9, 1.0)
const BLUE := Color(0.22, 0.42, 1.0)
const GREEN := Color(0.25, 1.0, 0.35)
const YELLOW := Color(1.0, 0.82, 0.22)
const RED := Color(1.0, 0.16, 0.12)
const MAGENTA := Color(1.0, 0.22, 0.85)

const BEAM_R := 3.4          # Bandradius in px (Kern ~1,5 px, enger Hof)
const CLIP_CAP := 0.25       # Kappe an Schnittkanten (Strahl wird dort dunkelgetastet)
const PERSIST := 0.55        # Anteil des Phosphorpuffers, der pro Bild (1/30 s) stehen bleibt (linear)
const TRAIL_FLOOR := 0.95    # Nachleuchten erst oberhalb dieser Helligkeit sichtbar
const SEED := 1979

const PANEL := Rect2(24, 588, 1232, 120)

@onready var beams: Node2D = $Phosphor/Beam/Beams
@onready var fade: ColorRect = $Phosphor/Fade
@onready var phosphor: SubViewport = $Phosphor

var w := Wire.new()
var badger := Badger.new()
var t := 0.0
var solo := false
var persist := true
var occlude := true
var stats := false
var preview := false
var sheet := ""
var cpu_us := 0
var trail_floor := TRAIL_FLOOR
var frame := 0

# vorbereitete Modelle
var m_cottage: Dictionary
var m_chimney: Dictionary
var m_barrel: Dictionary
var m_crate: Dictionary
var m_post: Dictionary
var m_plinth: Dictionary
var m_tower: Dictionary
var m_gallery: Dictionary
var m_roof: Dictionary
var m_hull_a: Dictionary
var m_hull_b: Dictionary
var m_wheelhouse: Dictionary
var stars := []
var water_z := []
var water_seed := []
var quay_poly := PackedVector2Array()
var deck_poly := PackedVector2Array()


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a == "--solo":
			solo = true
		elif a == "--nopersist":
			persist = false
		elif a == "--noglow":
			$WorldEnvironment.environment = null
		elif a == "--noocclude":
			occlude = false
		elif a == "--stats":
			stats = true
		elif a.begins_with("--floor="):
			trail_floor = float(a.substr(8))
		elif a == "--preview":
			preview = true
		elif a.begins_with("--sheet="):
			sheet = a.substr(8)
	if solo:
		persist = false
		$WorldEnvironment.environment = null
		(beams.material as ShaderMaterial).set_shader_parameter("whiten", 0.0)
	(fade.material as ShaderMaterial).set_shader_parameter("keep", PERSIST if persist else 0.0)
	var beam_tex := ($Phosphor/Beam as SubViewport).get_texture()
	($Phosphor/Fresh as Sprite2D).texture = beam_tex
	var screen := $Screen as Sprite2D
	screen.texture = phosphor.get_texture()
	(screen.material as ShaderMaterial).set_shader_parameter("beam_tex", beam_tex)
	(screen.material as ShaderMaterial).set_shader_parameter("trail_floor", trail_floor)
	w.setup()
	_build_models()


func cue(z: float) -> float:
	# Tiefenabschwächung: ferne Linien dunkler (wie die Intensitätsstufen der Farbvektor-Automaten)
	return lerpf(1.0, 0.42, clampf((z - 5.0) / 70.0, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Modelle (Meter, Godot-Achsen: x rechts, y oben, z zur Kamera)
# ---------------------------------------------------------------------------

func _build_models() -> void:
	# Hafenmeisterhäuschen: Satteldach, First entlang x
	var x0 := -7.6
	var x1 := -3.8
	var z0 := -6.2
	var z1 := -3.4
	var hw := 2.3
	var hr := 3.6
	var zc := (z0 + z1) * 0.5
	var v := PackedVector3Array([
		Vector3(x0, 0, z1), Vector3(x1, 0, z1), Vector3(x1, 0, z0), Vector3(x0, 0, z0),
		Vector3(x0, hw, z1), Vector3(x1, hw, z1), Vector3(x1, hw, z0), Vector3(x0, hw, z0),
		Vector3(x0, hr, zc), Vector3(x1, hr, zc)])
	var win := [PackedVector3Array([Vector3(-6.5, 0.95, z1), Vector3(-5.4, 0.95, z1), Vector3(-5.4, 1.85, z1), Vector3(-6.5, 1.85, z1)]), YELLOW, 1.3, true]
	var win_v := [PackedVector3Array([Vector3(-5.95, 0.95, z1), Vector3(-5.95, 1.85, z1)]), YELLOW, 0.9, false]
	var win_h := [PackedVector3Array([Vector3(-6.5, 1.4, z1), Vector3(-5.4, 1.4, z1)]), YELLOW, 0.9, false]
	var door := [PackedVector3Array([Vector3(-4.9, 0, z1), Vector3(-4.9, 1.95, z1), Vector3(-4.1, 1.95, z1), Vector3(-4.1, 0, z1)]), YELLOW, 0.55, false]
	var knob := [PackedVector3Array([Vector3(-4.25, 1.0, z1)]), YELLOW, 1.2, false]
	var side_win := [PackedVector3Array([Vector3(x1, 1.1, -4.4), Vector3(x1, 1.1, -5.2), Vector3(x1, 1.8, -5.2), Vector3(x1, 1.8, -4.4)]), YELLOW, 0.8, true]
	var gable_vent := [PackedVector3Array([Vector3(x1, 2.75, zc + 0.25), Vector3(x1, 2.75, zc - 0.25)]), WHITE, 0.4, false]
	m_cottage = Wire.solid(v, [
		Wire.face([0, 1, 5, 4], WHITE, 0.62, 0, [win, win_v, win_h, door, knob]),     # vorn
		Wire.face([3, 2, 6, 7], WHITE, 0.62),                                         # hinten
		Wire.face([0, 3, 7, 8, 4], WHITE, 0.62),                                      # Giebel links
		Wire.face([1, 2, 6, 9, 5], WHITE, 0.62, 0, [side_win, gable_vent]),           # Giebel rechts
		Wire.face([4, 5, 9, 8], BLUE, 0.9, 1),                                        # Dach vorn
		Wire.face([7, 6, 9, 8], BLUE, 0.9, 1)])                                       # Dach hinten
	m_chimney = Wire.box(Vector3(-7.05, 3.15, -5.05), Vector3(-6.45, 4.35, -4.45), WHITE, 0.6)

	m_barrel = Wire.lathe([[0.0, 0.26], [0.16, 0.31], [0.42, 0.33], [0.68, 0.31], [0.84, 0.26]], 10,
		[[YELLOW, 0.55, 0]], true, 0.25)
	m_crate = _crate(0.62)
	m_post = Wire.box(Vector3(-0.07, 0.0, -0.07), Vector3(0.07, 2.85, 0.07), YELLOW, 0.55)

	# Leuchtturm: Sockel, Turm mit rotem Band, Galerie, Laternenhaus (offen), Dach
	m_plinth = Wire.lathe([[0.0, 2.5], [0.6, 2.4]], 12, [[WHITE, 0.55, 0]], true, 0.5)
	m_tower = Wire.lathe([[0.6, 1.9], [4.5, 1.66], [6.1, 1.56], [9.7, 1.36]], 12,
		[[WHITE, 0.95, 0], [RED, 1.25, 1], [WHITE, 0.95, 0]], false, 0.5)
	m_gallery = Wire.lathe([[9.7, 2.0], [9.95, 2.0]], 12, [[WHITE, 0.8, 0]], true, 0.5)
	var rv := PackedVector3Array()
	var n := 8
	for j in n:
		var a := TAU * (float(j) + 0.5) / float(n)
		rv.append(Vector3(cos(a) * 1.25, 11.45, sin(a) * 1.25))
	rv.append(Vector3(0, 12.5, 0))
	var rf := []
	for j in n:
		rf.append(Wire.face([j, (j + 1) % n, n], RED, 1.0))
	m_roof = Wire.solid(rv, rf)

	m_hull_a = _hull(3.6, 1.35, 0.5)
	m_hull_b = _hull(4.4, 1.6, 0.6)
	m_wheelhouse = Wire.box(Vector3(-0.9, 0.0, -0.55), Vector3(0.3, 0.95, 0.55), WHITE, 0.75)

	# Sterne (fester Seed)
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in 70:
		var p := Vector2(rng.randf_range(10, 1270), rng.randf_range(12, 262))
		var b := rng.randf_range(0.25, 1.0)
		b = b * b * 1.6
		stars.append([p, b, rng.randf_range(0, TAU), rng.randf_range(1.5, 4.0)])
	# Wasserzeilen: Tiefen so gewählt, dass sie im Bild etwa gleichmäßig nach oben dichter werden
	for k in 15:
		water_z.append(-3.6 - 1.15 * pow(1.36, float(k)))
		water_seed.append(rng.randf_range(0, 10))
	# Kai- und Landoberfläche (verdeckt alles, was tiefer liegt: Wasser, Bootsrümpfe, Stegpfähle)
	quay_poly = w.project_poly(PackedVector3Array([Vector3(-40, 0, 6), Vector3(40, 0, 6), Vector3(40, 0, 0),
		Vector3(-3.0, 0, 0), Vector3(-3.0, 0, -10), Vector3(-40, 0, -10)]))
	deck_poly = w.project_poly(PackedVector3Array([Vector3(2.4, 0, 0), Vector3(3.6, 0, 0), Vector3(3.6, 0, -7.5), Vector3(2.4, 0, -7.5)]))


func _crate(s: float) -> Dictionary:
	var b := Wire.box(Vector3(0, 0, 0), Vector3(s, s, s), YELLOW, 0.6)
	# Diagonalstreben auf den Seiten als Abziehbild (nur wenn die Fläche zur Kamera zeigt)
	var i := 0.06
	for f in b.faces:
		var idx: PackedInt32Array = f.i
		var vv: PackedVector3Array = b.verts
		var c := Vector3()
		for k in idx:
			c += vv[k]
		c /= 4.0
		var p0 := vv[idx[0]].lerp(c, 0.18)
		var p2 := vv[idx[2]].lerp(c, 0.18)
		var q := PackedVector3Array()
		for k in idx:
			q.append(vv[k].lerp(c, i / s * 2.0))
		f.decals = [[PackedVector3Array([p0, p2]), YELLOW, 0.4, false], [q, YELLOW, 0.3, true]]
	return b


## Bootsrumpf als konvexer Körper (Bug +x): Schandeck oben (rot), Wasserlinie unten
func _hull(l: float, bw: float, fb: float) -> Dictionary:
	var top := [[-0.5, 0.42, 0.0], [-0.25, 0.5, -0.03], [0.05, 0.5, -0.03], [0.3, 0.42, 0.02], [0.5, 0.0, 0.14]]
	var v := PackedVector3Array()
	# Ring oben (Schandeck), Backbord dann Steuerbord rückwärts
	var ring_top := []
	var ring_bot := []
	for p in top:
		ring_top.append(Vector3(p[0] * l, fb + p[2], p[1] * bw))
	for k in range(top.size() - 2, -1, -1):
		var p: Array = top[k]
		ring_top.append(Vector3(p[0] * l, fb + p[2], -p[1] * bw))
	for p in ring_top:
		var q: Vector3 = p
		var bx := q.x * 0.9 if q.x > 0.0 else q.x * 0.97
		ring_bot.append(Vector3(bx, -0.02, q.z * 0.72))
	for p in ring_top:
		v.append(p)
	for p in ring_bot:
		v.append(p)
	var m := ring_top.size()
	var faces := []
	var ti := []
	var bi := []
	for j in m:
		ti.append(j)
		bi.append(m + j)
	faces.append(Wire.face(ti, RED, 1.0, 2))
	for j in m:
		var j2 := (j + 1) % m
		faces.append(Wire.face([j, j2, m + j2, m + j], WHITE, 0.6, 0))
	return Wire.solid(v, faces)


# ---------------------------------------------------------------------------
# Bild aufbauen
# ---------------------------------------------------------------------------

func _process(delta: float) -> void:
	var t_start := Time.get_ticks_usec()
	beams.clear()
	var draws := []
	if solo:
		_add_badger(draws)
	elif preview:
		_add_badger(draws, 3.2)
	elif sheet != "":
		_add_sheet(draws)
	else:
		_build_scene(draws)
	_render(draws)
	beams.queue_redraw()
	if stats:
		cpu_us += Time.get_ticks_usec() - t_start
		if frame % 30 == 29:
			print("t=%.2f segments=%d verts=%d script_ms=%.2f" % [t, beams.segment_count, beams.points.size(), cpu_us / 30000.0])
			cpu_us = 0
	t += delta
	frame += 1


## Vorlageblätter für den Katalog: --sheet=font (Strichschrift) oder --sheet=badger (Laufphasen)
func _add_sheet(draws: Array) -> void:
	var lines := []
	if sheet == "font":
		var rows := ["ABCDEFGHIJKLM", "NOPQRSTUVWXYZ", "ÄÖÜ 0123456789", ".,:;!?<>-+_/'()", "> nimm paket"]
		for i in rows.size():
			_text(lines, rows[i], Vector2(70, 120 + 120 * i), 6.0, (YELLOW if i == 4 else WHITE) * 0.8)
		_add(draws, 1.0, [_layer(lines, [], false, [], 3.0)])
		return
	var poses := [1.0, 1.1, 1.2, 1.3, 1.4, 5.0]
	for i in poses.size():
		t = poses[i]
		var b := badger.build(t)
		var base := Vector2(118.0 + 205.0 * i - (float(b.body_x) - badger.body_x(poses[i])) , 640.0)
		var k := 2.7
		var layers := []
		for l in b.layers:
			var ls := []
			for line in l.lines:
				ls.append([_to_screen(line[0], base, k), line[1], line[2], line[3]])
			var occ := []
			for o in l.occ:
				occ.append(_to_screen(o, base, k))
			layers.append(_layer(ls, occ))
		_add(draws, 5.0 + float(i) * 0.01, layers)
	t = 0.0


func _layer(lines: Array, occ: Array = [], clip := true, extra: Array = [], r := BEAM_R) -> Dictionary:
	return {"lines": lines, "occ": occ, "clip": clip, "extra": extra, "r": r}


func _add(draws: Array, depth: float, layers: Array) -> void:
	draws.append({"depth": depth, "layers": layers})


func _add_emit(draws: Array, e: Dictionary, extra: Array = [], with_occ := true) -> void:
	var occ := []
	if with_occ and e.occ.size() >= 3:
		occ.append(e.occ)
	_add(draws, e.depth, [_layer(e.lines, occ, true, extra)])


func _build_scene(draws: Array) -> void:
	var under := [quay_poly, deck_poly]    # für alles, was tiefer liegt als Kai und Steg
	_add_ui(draws)
	_add_badger(draws)
	_add_quay(draws)
	_add_props(draws)
	_add_cottage(draws)
	_add_jetty(draws)
	_add_boats(draws, under)
	_add_water(draws, under)
	_add_land(draws)
	_add_lighthouse(draws)
	_add_sky(draws)


func _render(draws: Array) -> void:
	draws.sort_custom(func(a, b): return a.depth < b.depth)
	var occluders := []
	for d in draws:
		for layer in d.layers:
			for line in layer.lines:
				_emit_line(line, layer, occluders)
			for o in layer.occ:
				if (o as PackedVector2Array).size() >= 3:
					occluders.append([o, _bounds(o)])


func _bounds(p: PackedVector2Array) -> Rect2:
	var r := Rect2(p[0], Vector2.ZERO)
	for q in p:
		r = r.expand(q)
	return r


func _emit_line(line: Array, layer: Dictionary, occluders: Array) -> void:
	var pts: PackedVector2Array = line[0]
	if pts.is_empty():
		return
	var col: Color = line[1]
	if col.r + col.g + col.b < 0.004:
		return
	var closed: bool = line[2]
	var cap: float = line[3]
	var fade_c: Vector2 = line[4] if line.size() > 4 else Vector2.INF
	var fade_l: float = line[5] if line.size() > 5 else 0.0
	if pts.size() == 1:
		# Leuchtpunkt: nur zeichnen, wenn er nicht verdeckt ist
		if layer.clip and occlude:
			for o in occluders:
				if (o[1] as Rect2).has_point(pts[0]) and Geometry2D.is_point_in_polygon(pts[0], o[0]):
					return
			for e in layer.extra:
				if Geometry2D.is_point_in_polygon(pts[0], e):
					return
		beams.point(pts[0], col * cap, layer.r)
		return
	var open := pts
	if closed:
		open = pts.duplicate()
		open.append(pts[0])
	var pieces := [open]
	if layer.clip and occlude:
		var r := _bounds(open).grow(layer.r)
		var polys := []
		for o in occluders:
			if (o[1] as Rect2).intersects(r):
				polys.append(o[0])
		for e in layer.extra:
			polys.append(e)
		for poly in polys:
			var next := []
			for pc in pieces:
				next.append_array(Geometry2D.clip_polyline_with_polygon(pc, poly))
			pieces = next
			if pieces.is_empty():
				return
	var a0 := open[0]
	var a1 := open[open.size() - 1]
	for pc in pieces:
		var p: PackedVector2Array = pc
		if p.size() < 2:
			continue
		var c0 := cap if (not closed and (p[0].distance_squared_to(a0) < 0.01 or p[0].distance_squared_to(a1) < 0.01)) else CLIP_CAP
		var c1 := cap if (not closed and (p[p.size() - 1].distance_squared_to(a0) < 0.01 or p[p.size() - 1].distance_squared_to(a1) < 0.01)) else CLIP_CAP
		if pieces.size() == 1 and closed and p.size() == open.size():
			beams.polyline(pts, col, layer.r, true, cap, 0.4)
		elif fade_l > 0.0:
			_emit_faded(p, col, fade_c, fade_l, c0, c1)
		else:
			_poly_caps(p, col, c0, c1, layer.r)


func _poly_caps(p: PackedVector2Array, col: Color, c0: float, c1: float, r: float) -> void:
	var n := p.size()
	for i in n - 1:
		beams.segment(p[i], p[i + 1], col, r, c0 if i == 0 else 0.4, c1 if i == n - 2 else 0.4)


## Linie mit Helligkeitsabfall vom Punkt c (Leuchtturmstrahl): in kurze Stücke zerlegen
func _emit_faded(p: PackedVector2Array, col: Color, c: Vector2, l: float, c0: float, c1: float) -> void:
	for i in p.size() - 1:
		var a := p[i]
		var b := p[i + 1]
		var n := maxi(1, int(a.distance_to(b) / 10.0))
		for k in n:
			var q0 := a.lerp(b, float(k) / n)
			var q1 := a.lerp(b, float(k + 1) / n)
			var m := (q0 + q1) * 0.5
			var f := exp(-m.distance_to(c) / l)
			var first := i == 0 and k == 0
			var last := i == p.size() - 2 and k == n - 1
			beams.segment(q0, q1, col * f, BEAM_R, c0 * f if first else 0.5, c1 * f if last else 0.5)


# ---------------------------------------------------------------------------
# Inhalte
# ---------------------------------------------------------------------------

const BADGER_Z := 3.4


func _add_badger(draws: Array, zoom := 1.0) -> void:
	var z := BADGER_Z
	var b := badger.build(t, solo)
	var bx: float = b.body_x
	if solo:
		var fe: Array = b.feet
		print("M %d %.5f %.5f %.3f %.5f %.3f %.5f" % [frame, t, fe[0].x, fe[0].y, fe[1].x, fe[1].y, bx])
	var base := w.project(Vector3(bx, 0.0, z))
	var k := w.px_per_m(w.depth(Vector3(bx, 0.0, z))) / 100.0
	if zoom != 1.0:
		k *= zoom
		base = Vector2(640.0 - (bx + 0.87) * 100.0 * k, 660.0)
	var layers := []
	for l in b.layers:
		var lines := []
		for line in l.lines:
			lines.append([_to_screen(line[0], base, k), line[1], line[2], line[3]])
		var occ := []
		for o in l.occ:
			occ.append(_to_screen(o, base, k))
		layers.append(_layer(lines, occ))
	_add(draws, w.depth(Vector3(bx, 0.0, z)), layers)


func _to_screen(p: PackedVector2Array, base: Vector2, k: float) -> PackedVector2Array:
	var o := PackedVector2Array()
	o.resize(p.size())
	for i in p.size():
		o[i] = base + Vector2(p[i].x, -p[i].y) * k
	return o


func _add_quay(draws: Array) -> void:
	# Kaikante (Wasserseite) und Landkante links, Pflasterreihen, Fugen; jede Reihe eigene Tiefe
	var edge := [[PackedVector3Array([Vector3(-3.0, 0, -10.0), Vector3(-3.0, 0, 0.0), Vector3(30.0, 0, 0.0)]), BLUE, 1.1, false],
		[PackedVector3Array([Vector3(-3.0, 0, 0.32), Vector3(30.0, 0, 0.32)]), BLUE, 0.55, false],
		[PackedVector3Array([Vector3(-3.0, -0.8, -10.0), Vector3(-3.0, -0.8, -0.0)]), BLUE, 0.45, false]]
	_add_emit(draws, w.emit_wire(edge, Transform3D.IDENTITY, cue, 8.0))
	# Fugen der Kaimauer (linke Wand, sichtbar von rechts)
	var wall := []
	for zz in [-1.2, -2.6, -4.1, -5.7, -7.4, -9.2]:
		wall.append([PackedVector3Array([Vector3(-3.0, 0, zz), Vector3(-3.0, -0.8, zz)]), BLUE, 0.35, false])
	wall.append([PackedVector3Array([Vector3(-3.0, -0.4, -10.0), Vector3(-3.0, -0.4, 0.0)]), BLUE, 0.25, false])
	_add_emit(draws, w.emit_wire(wall, Transform3D.IDENTITY, cue, 13.0))
	var rows := [1.0, 1.8, 2.75, 3.85, 5.1]
	var prev := 0.32
	var ri := 0
	for zr in rows:
		var lines := [[PackedVector3Array([Vector3(-9.0, 0, zr), Vector3(14.0, 0, zr)]), BLUE, 0.32, false]]
		var off := 0.55 if ri % 2 == 0 else 0.0
		var x := -9.0 + off
		while x < 14.0:
			lines.append([PackedVector3Array([Vector3(x, 0, prev), Vector3(x, 0, zr)]), BLUE, 0.26, false])
			x += 1.15
		_add_emit(draws, w.emit_wire(lines, Transform3D.IDENTITY, cue, w.depth(Vector3(0, 0, (zr + prev) * 0.5))))
		prev = zr
		ri += 1
	# Land links hinter der Kante (unter dem Häuschen)
	var lrows := [-1.1, -2.4, -3.9, -5.6, -7.6]
	prev = 0.0
	ri = 0
	for zr in lrows:
		var lines := [[PackedVector3Array([Vector3(-16.0, 0, zr), Vector3(-3.0, 0, zr)]), BLUE, 0.3, false]]
		var x := -15.4 + (0.6 if ri % 2 == 0 else 0.0)
		while x < -3.0:
			lines.append([PackedVector3Array([Vector3(x, 0, prev), Vector3(x, 0, zr)]), BLUE, 0.24, false])
			x += 1.2
		_add_emit(draws, w.emit_wire(lines, Transform3D.IDENTITY, cue, w.depth(Vector3(-4, 0, (zr + prev) * 0.5))))
		prev = zr
		ri += 1


func _add_props(draws: Array) -> void:
	# Fässer neben dem Häuschen
	for p in [Vector3(-3.55, 0, -1.6), Vector3(-4.3, 0, -1.05)]:
		_add_emit(draws, w.emit_solid(m_barrel, Transform3D(Basis(), p), cue))
	# Kistenstapel rechts
	for c in [[Vector3(3.85, 0, 1.0), 0.0], [Vector3(4.55, 0, 0.95), 0.1], [Vector3(4.15, 0.62, 0.97), -0.06]]:
		_add_emit(draws, w.emit_solid(m_crate, Transform3D(Basis(Vector3.UP, c[1]), c[0]), cue))
	# Tauwerk: flache Spirale am Boden
	var rope := PackedVector3Array()
	for i in 64:
		var a := float(i) / 64.0 * TAU * 2.6
		var r := 0.1 + 0.2 * float(i) / 64.0
		rope.append(Vector3(1.55 + cos(a) * r, 0.03, 0.55 + sin(a) * r))
	_add_emit(draws, w.emit_wire([[rope, YELLOW, 0.4, false]], Transform3D.IDENTITY, cue))
	# Laternenpfahl mit Ausleger und Laterne
	var px := -2.05
	var pz := 0.75
	var xf := Transform3D(Basis(), Vector3(px, 0, pz))
	_add_emit(draws, w.emit_solid(m_post, xf, cue))
	var arm := [[PackedVector3Array([Vector3(0.0, 2.72, 0), Vector3(0.62, 2.72, 0)]), YELLOW, 0.55, false],
		[PackedVector3Array([Vector3(0.0, 2.3, 0), Vector3(0.42, 2.72, 0)]), YELLOW, 0.45, false]]
	var lx := 0.52
	var top := 2.58
	var cage := []
	cage.append([PackedVector3Array([Vector3(lx, 2.72, 0), Vector3(lx, top + 0.05, 0)]), WHITE, 0.5, false])
	var sq := [Vector3(-0.11, 0, -0.11), Vector3(0.11, 0, -0.11), Vector3(0.11, 0, 0.11), Vector3(-0.11, 0, 0.11)]
	var ring_t := PackedVector3Array()
	var ring_b := PackedVector3Array()
	for q in sq:
		ring_t.append(Vector3(lx, top - 0.08, 0) + q)
		ring_b.append(Vector3(lx, top - 0.38, 0) + q * 0.85)
	cage.append([ring_t, WHITE, 0.55, true])
	cage.append([ring_b, WHITE, 0.55, true])
	for i in 4:
		cage.append([PackedVector3Array([ring_t[i], ring_b[i]]), WHITE, 0.45, false])
		cage.append([PackedVector3Array([ring_t[i], Vector3(lx, top + 0.05, 0)]), WHITE, 0.5, false])
	cage.append([PackedVector3Array([ring_b[0], Vector3(lx, top - 0.46, 0), ring_b[2]]), WHITE, 0.4, false])
	var e := w.emit_wire(arm + cage, xf, cue)
	_add_emit(draws, e)
	# Flamme: kleine Raute, flackert (Rauschen aus festen Sinusanteilen)
	var fl := 0.75 + 0.18 * sin(t * 23.0) + 0.12 * sin(t * 37.0 + 1.3) + 0.1 * sin(t * 7.3)
	var fc := xf * Vector3(lx, top - 0.24, 0)
	var s := w.project(fc)
	var h := 7.0 * (0.85 + 0.25 * fl)
	var flame := PackedVector2Array([s + Vector2(0, -h), s + Vector2(3.2, 0), s + Vector2(0, h * 0.55), s + Vector2(-3.2, 0)])
	_add(draws, w.depth(fc) - 0.05, [_layer([[flame, YELLOW * (1.6 * fl), true, 0.6], [PackedVector2Array([s]), YELLOW * (3.0 * fl), false, 1.0]])])


func _add_cottage(draws: Array) -> void:
	var e := w.emit_solid(m_cottage, Transform3D.IDENTITY, cue)
	# Fenster flackert leicht mit (Kerzenlicht hinter dem Glas)
	var fl := 0.92 + 0.08 * sin(t * 9.0 + 0.7)
	for line in e.lines:
		if (line[1] as Color).r > 0.5 and (line[1] as Color).b < 0.3:
			line[1] = (line[1] as Color) * fl
	_add_emit(draws, e)
	var c := w.emit_solid(m_chimney, Transform3D.IDENTITY, cue)
	c.depth -= 0.5
	_add_emit(draws, c)
	# Rauch: Ringe steigen auf, wachsen, verblassen, treiben nach rechts
	var top := Vector3(-6.75, 4.4, -4.75)
	var lines := []
	for i in 6:
		var age := fmod(t + float(i) * 0.63, 3.78)
		var u := age / 3.78
		var center := top + Vector3(0.32 * age + 0.07 * age * age, 0.34 * age - 0.015 * age * age, 0.0)
		var r := 0.1 + 0.5 * u
		var pts := PackedVector3Array()
		var nseg := 9
		for j in nseg:
			var a := TAU * float(j) / float(nseg) + float(i) * 0.7
			var wob := 1.0 + 0.12 * sin(a * 3.0 + t * 2.0 + float(i))
			pts.append(center + Vector3(cos(a) * r * wob, sin(a) * r * 0.8 * wob, 0))
		var k := 0.55 * (1.0 - u) * smoothstep(0.0, 0.1, u)
		lines.append([pts, WHITE, k, true])
	var sm := w.emit_wire(lines, Transform3D.IDENTITY, cue)
	sm.depth = w.depth(top) - 0.6
	_add_emit(draws, sm)


func _add_jetty(draws: Array) -> void:
	var lines := []
	var a := 2.4
	var b := 3.6
	var zf := -7.5
	lines.append([PackedVector3Array([Vector3(a, 0, 0), Vector3(a, 0, zf), Vector3(b, 0, zf), Vector3(b, 0, 0)]), YELLOW, 0.6, false])
	var z := -0.5
	while z > zf:
		lines.append([PackedVector3Array([Vector3(a, 0, z), Vector3(b, 0, z)]), YELLOW, 0.3, false])
		z -= 0.5
	for zp in [-1.5, -3.0, -4.5, -6.0, -7.5]:
		var hi := 0.55 if zp == -7.5 else 0.0
		for xp in [a, b]:
			lines.append([PackedVector3Array([Vector3(xp, hi, zp), Vector3(xp, -0.85, zp)]), YELLOW, 0.5, false])
	var e := w.emit_wire(lines, Transform3D.IDENTITY, cue)
	e.occ = deck_poly
	_add_emit(draws, e, [quay_poly])


func _add_boats(draws: Array, under: Array) -> void:
	# Boot A: offen, mit Mast; Boot B: mit Ruderhaus. Schaukeln um die Längsachse.
	var specs := [[m_hull_a, Vector3(0.1, -0.8, -5.4), 0.0, 0.0], [m_hull_b, Vector3(6.3, -0.8, -6.6), PI, 1.7]]
	for sp in specs:
		var ph: float = sp[3]
		var roll := deg_to_rad(3.2) * sin(t * 1.35 + ph)
		var pitch := deg_to_rad(1.1) * sin(t * 0.9 + ph + 0.8)
		var heave := 0.045 * sin(t * 1.1 + ph + 0.4)
		var basis := Basis(Vector3.UP, sp[2]) * Basis(Vector3.RIGHT, roll) * Basis(Vector3.BACK, pitch)
		var xf := Transform3D(basis, (sp[1] as Vector3) + Vector3(0, heave, 0))
		var e := w.emit_solid(sp[0], xf, cue)
		_add_emit(draws, e, under)
		if sp[0] == m_hull_a:
			var mast := [[PackedVector3Array([Vector3(0.35, 0.4, 0), Vector3(0.35, 2.9, 0)]), YELLOW, 0.65, false],
				[PackedVector3Array([Vector3(0.35, 2.75, 0), Vector3(1.75, 0.55, 0)]), WHITE, 0.3, false],
				[PackedVector3Array([Vector3(0.35, 2.75, 0), Vector3(-1.6, 0.48, 0)]), WHITE, 0.3, false],
				[PackedVector3Array([Vector3(0.35, 1.0, 0), Vector3(-1.3, 1.05, 0)]), YELLOW, 0.5, false]]
			var me := w.emit_wire(mast, xf, cue)
			me.depth = e.depth - 0.05
			_add_emit(draws, me, under, false)
		else:
			var wh := w.emit_solid(m_wheelhouse, xf, cue)
			wh.depth = e.depth - 0.3
			_add_emit(draws, wh, under)
			var extra := [[PackedVector3Array([Vector3(-0.2, 0.95, 0), Vector3(-0.2, 2.4, 0)]), YELLOW, 0.6, false],
				[PackedVector3Array([Vector3(-0.2, 2.25, 0), Vector3(-1.9, 0.62, 0)]), WHITE, 0.3, false],
				[PackedVector3Array([Vector3(-0.75, 0.45, 0.56), Vector3(-0.35, 0.45, 0.56), Vector3(-0.35, 0.8, 0.56), Vector3(-0.75, 0.8, 0.56)]), CYAN, 0.6, true],
				[PackedVector3Array([Vector3(-0.75, 0.45, -0.56), Vector3(-0.35, 0.45, -0.56), Vector3(-0.35, 0.8, -0.56), Vector3(-0.75, 0.8, -0.56)]), CYAN, 0.6, true]]
			var xe := w.emit_wire(extra, xf, cue)
			xe.depth = wh.depth - 0.05
			_add_emit(draws, xe, under, false)


func _add_water(draws: Array, under: Array) -> void:
	# Wellen als gestrichelte Linienzüge, je Zeile eigene Tiefe (Boote verdecken nur, was dahinter liegt)
	var lamp := _lamp_world()
	var lamp_s := w.project(lamp)
	for k in water_z.size():
		var z: float = water_z[k]
		var sd: float = water_seed[k]
		var dz := w.depth(Vector3(0, -0.8, z))
		var x0 := -3.0 if z > -10.0 else -70.0
		var x1 := 70.0
		var step := 0.22 * dz / 6.0
		var period := 2.4 * (1.0 + dz / 25.0)
		var drift := t * (0.35 + 0.1 * float(k % 3)) + sd
		var lines := []
		var cur := PackedVector3Array()
		var x := x0
		while x <= x1:
			var ph := fposmod((x + drift) / period, 1.0)
			if ph < 0.68:
				var y := -0.8 + 0.06 * sin(1.4 * x + t * 2.1 + sd) + 0.03 * sin(3.1 * x - t * 1.3)
				cur.append(Vector3(x, y, z))
			elif cur.size() > 0:
				if cur.size() > 1:
					lines.append([cur, CYAN, 0.62, false])
				cur = PackedVector3Array()
			x += step
		if cur.size() > 1:
			lines.append([cur, CYAN, 0.62, false])
		# Spiegelung des Leuchtfeuers: kurze gelbe Striche senkrecht unter der Lampe
		var mx := (lamp_s.x - 640.0) * dz / w.f_px
		var fl := 0.55 + 0.45 * _flash()
		var half := 0.15 + 0.03 * dz
		var jig := 0.25 * sin(t * 3.0 + float(k) * 1.7) * dz / 10.0
		lines.append([PackedVector3Array([Vector3(mx - half + jig, -0.8, z), Vector3(mx + half + jig, -0.8, z)]), YELLOW, 0.9 * fl, false])
		var e := w.emit_wire(lines, Transform3D.IDENTITY, cue, dz)
		_add_emit(draws, e, under)


func _add_land(draws: Array) -> void:
	# Landzunge rechts (trägt den Leuchtturm) und Hügel links: Grat, Felskanten, Wasserlinie
	var ridge := PackedVector3Array([Vector3(13.0, -0.8, -36.0), Vector3(14.6, 0.4, -37.0), Vector3(16.5, 1.3, -38.5),
		Vector3(18.5, 2.3, -39.5), Vector3(21.0, 3.0, -41.0), Vector3(23.6, 3.5, -42.0), Vector3(28.4, 3.5, -42.0),
		Vector3(31.0, 3.2, -41.0), Vector3(33.5, 3.9, -40.0), Vector3(36.5, 3.1, -39.5), Vector3(40.0, 2.6, -39.0),
		Vector3(44.0, 3.0, -40.0), Vector3(50.0, 2.1, -40.0), Vector3(60.0, 1.6, -40.0)])
	var base := PackedVector3Array([Vector3(60.0, -0.8, -33.0), Vector3(40.0, -0.8, -33.0), Vector3(30.0, -0.8, -34.0),
		Vector3(22.0, -0.8, -34.5), Vector3(16.0, -0.8, -35.0), Vector3(13.0, -0.8, -36.0)])
	var crags := [[16.5, 1.3, -38.5, 15.6, -0.8, -35.0], [21.0, 3.0, -41.0, 20.0, -0.8, -34.6], [23.6, 3.5, -42.0, 24.5, 1.2, -36.5],
		[24.5, 1.2, -36.5, 23.5, -0.8, -34.4], [31.0, 3.2, -41.0, 30.5, 0.8, -36.0], [30.5, 0.8, -36.0, 29.0, -0.8, -34.0],
		[36.5, 3.1, -39.5, 37.5, -0.8, -33.0], [44.0, 3.0, -40.0, 45.0, 0.6, -35.0], [18.5, 2.3, -39.5, 21.0, 1.0, -37.0],
		[21.0, 1.0, -37.0, 24.5, 1.2, -36.5], [30.5, 0.8, -36.0, 33.5, 1.4, -36.5], [33.5, 1.4, -36.5, 36.5, 3.1, -39.5]]
	var lines := [[ridge, GREEN, 0.95, false], [base, CYAN, 0.55, false]]
	for c in crags:
		lines.append([PackedVector3Array([Vector3(c[0], c[1], c[2]), Vector3(c[3], c[4], c[5])]), GREEN, 0.5, false])
	# Felsen im Wasser vor der Landzunge
	lines.append([PackedVector3Array([Vector3(10.0, -0.8, -31.0), Vector3(10.5, -0.2, -31.5), Vector3(11.4, 0.1, -31.6),
		Vector3(12.3, -0.4, -31.2), Vector3(12.8, -0.8, -31.0)]), GREEN, 0.55, false])
	var e := w.emit_wire(lines, Transform3D.IDENTITY, cue)
	var occ := PackedVector3Array(ridge)
	occ.append_array(base)
	e.occ = w.project_poly(occ)
	_add_emit(draws, e)
	var rock_occ := w.project_poly(PackedVector3Array([Vector3(10.0, -0.8, -31.0), Vector3(10.5, -0.2, -31.5),
		Vector3(11.4, 0.1, -31.6), Vector3(12.3, -0.4, -31.2), Vector3(12.8, -0.8, -31.0)]))
	_add(draws, w.depth(Vector3(11, 0, -31)) + 0.01, [_layer([], [rock_occ])])

	var hill := PackedVector3Array([Vector3(-3.0, -0.8, -10.5), Vector3(-3.6, 0.3, -12.5), Vector3(-5.0, 1.2, -15.0),
		Vector3(-7.5, 2.0, -18.5), Vector3(-10.5, 2.5, -21.0), Vector3(-14.0, 3.2, -24.0), Vector3(-18.0, 3.4, -27.0),
		Vector3(-24.0, 3.9, -30.0), Vector3(-32.0, 3.6, -33.0), Vector3(-45.0, 3.9, -36.0)])
	var hl := [[hill, GREEN, 0.8, false],
		[PackedVector3Array([Vector3(-7.5, 2.0, -18.5), Vector3(-6.5, 0.0, -13.0)]), GREEN, 0.38, false],
		[PackedVector3Array([Vector3(-14.0, 3.2, -24.0), Vector3(-12.0, 1.2, -18.0), Vector3(-9.5, 0.0, -14.0)]), GREEN, 0.38, false],
		[PackedVector3Array([Vector3(-24.0, 3.9, -30.0), Vector3(-20.0, 1.8, -22.0)]), GREEN, 0.32, false]]
	var he := w.emit_wire(hl, Transform3D.IDENTITY, cue)
	var hocc := PackedVector3Array(hill)
	hocc.append_array(PackedVector3Array([Vector3(-45.0, -0.8, -36.0), Vector3(-45.0, -0.8, -10.0)]))
	he.occ = w.project_poly(hocc)
	_add_emit(draws, he)
	# ferne Inseln am Horizont
	var isl := [[PackedVector3Array([Vector3(-75.0, -0.8, -320.0), Vector3(-66.0, 3.0, -320.0), Vector3(-55.0, 4.2, -320.0),
		Vector3(-44.0, 2.4, -320.0), Vector3(-36.0, -0.8, -320.0)]), GREEN, 0.75, false],
		[PackedVector3Array([Vector3(4.0, -0.8, -300.0), Vector3(10.0, 1.8, -300.0), Vector3(19.0, 2.4, -300.0),
		Vector3(27.0, -0.8, -300.0)]), GREEN, 0.7, false]]
	for il in isl:
		var ie := w.emit_wire([il], Transform3D.IDENTITY, cue)
		ie.occ = w.project_poly(il[0])
		_add_emit(draws, ie)


func _lighthouse_xf() -> Transform3D:
	return Transform3D(Basis(), Vector3(26.0, 3.5, -42.0))


func _lamp_world() -> Vector3:
	return _lighthouse_xf() * Vector3(0, 10.7, 0)


const BEAM_PERIOD := 4.2
const BEAM_PHASE := 1.05


func _beam_angle() -> float:
	return TAU * (t - BEAM_PHASE) / BEAM_PERIOD


## 1 = Strahl zeigt genau zur Kamera
func _flash() -> float:
	var lamp := _lamp_world()
	var to_cam := Vector2(w.cam_pos.x - lamp.x, w.cam_pos.z - lamp.z).angle()
	var d := angle_difference(_beam_angle(), to_cam)
	return exp(-pow(d / 0.22, 2.0))


func _add_lighthouse(draws: Array) -> void:
	var xf := _lighthouse_xf()
	var parts := [m_plinth, m_tower, m_gallery, m_roof]
	var base_d := w.depth(xf.origin)
	for i in parts.size():
		var e := w.emit_solid(parts[i], xf, cue)
		e.depth = base_d - 0.01 * float(i)
		_add_emit(draws, e)
	# Tür und Fenster als Abziehbilder auf der Vorderseite (Turm zeigt zur Kamera, +z)
	var deco := [[PackedVector3Array([Vector3(-0.42, 0.6, 1.9), Vector3(-0.42, 2.0, 1.85), Vector3(0.42, 2.0, 1.85), Vector3(0.42, 0.6, 1.9)]), YELLOW, 0.55, false],
		[PackedVector3Array([Vector3(-0.2, 3.3, 1.72), Vector3(0.2, 3.3, 1.72), Vector3(0.2, 3.85, 1.71), Vector3(-0.2, 3.85, 1.71)]), YELLOW, 0.65, true],
		[PackedVector3Array([Vector3(-0.18, 7.4, 1.47), Vector3(0.18, 7.4, 1.47), Vector3(0.18, 7.9, 1.45), Vector3(-0.18, 7.9, 1.45)]), YELLOW, 0.65, true]]
	# Galeriegeländer und Laternenhaus (offen, durchsichtig)
	var n := 12
	var rail := PackedVector3Array()
	var gl_b := PackedVector3Array()
	var gl_t := PackedVector3Array()
	for j in n:
		var a := TAU * (float(j) + 0.5) / float(n)
		rail.append(Vector3(cos(a) * 1.95, 10.55, sin(a) * 1.95))
	for j in 8:
		var a := TAU * (float(j) + 0.5) / 8.0
		gl_b.append(Vector3(cos(a) * 1.15, 9.95, sin(a) * 1.15))
		gl_t.append(Vector3(cos(a) * 1.15, 11.45, sin(a) * 1.15))
	var cage := [[rail, WHITE, 0.6, true], [gl_b, WHITE, 0.45, true], [gl_t, WHITE, 0.55, true]]
	for j in n:
		var a := TAU * (float(j) + 0.5) / float(n)
		if sin(a) > -0.3:
			cage.append([PackedVector3Array([Vector3(cos(a) * 1.95, 9.95, sin(a) * 1.95), rail[j]]), WHITE, 0.4, false])
	var ang := _beam_angle()
	for j in 8:
		cage.append([PackedVector3Array([gl_b[j], gl_t[j]]), WHITE, 0.35, false])
	var de := w.emit_wire(deco + cage, xf, cue)
	de.depth = base_d - 0.2
	_add_emit(draws, de)
	# Lampe und Strahl
	var lamp := _lamp_world()
	var ls := w.project(lamp)
	var fl := _flash()
	var lamp_lines := [[PackedVector2Array([ls]), YELLOW * (2.2 + 9.0 * fl), false, 1.0]]
	var rr := 5.0 + 9.0 * fl
	for k in 4:
		var a := PI * 0.25 + PI * 0.5 * float(k)
		var dvec := Vector2(cos(a), sin(a))
		lamp_lines.append([PackedVector2Array([ls + dvec * 3.0, ls + dvec * rr]), YELLOW * (0.6 + 2.5 * fl), false, 0.5])
	lamp_lines.append([PackedVector2Array([ls + Vector2(-rr * 1.6, 0), ls + Vector2(rr * 1.6, 0)]), YELLOW * (0.2 + 2.0 * fl), false, 0.3])
	_add(draws, w.depth(lamp) - 0.3, [_layer(lamp_lines)])
	var beam := []
	for side in [-1.0, 1.0]:
		var a: float = ang + side * 0.07
		var far := lamp + Vector3(cos(a), 0.0, sin(a)) * 34.0
		var near := lamp + Vector3(cos(a), 0.0, sin(a)) * 1.3
		var col := YELLOW * 2.6
		beam.append([PackedVector2Array([w.project(near), w.project(far)]), col, false, 0.0, ls, 210.0])
	_add(draws, w.depth(lamp) + 0.5, [_layer(beam)])


func _add_sky(draws: Array) -> void:
	var hy := w.project(Vector3(0, -0.8, -20000)).y
	var lines := []
	lines.append([PackedVector2Array([Vector2(0, hy), Vector2(1280, hy)]), YELLOW * 1.0, false, 0.6])
	# Abendlicht über dem Horizont: Linien statt Verlauf, nach oben dunkler und röter
	var band := [[4.0, YELLOW, 0.5, 0.0], [9.0, RED, 0.75, 0.2], [15.0, RED, 0.45, 0.5], [23.0, MAGENTA, 0.32, 0.3], [34.0, MAGENTA, 0.18, 0.7]]
	for b in band:
		var y: float = hy - b[0]
		var x: float = -40.0 + 60.0 * b[3]
		while x < 1280.0:
			var l := 180.0 + 90.0 * sin(x * 0.013 + b[0])
			lines.append([PackedVector2Array([Vector2(x, y), Vector2(x + l, y)]), b[1] * b[2], false, 0.4])
			x += l + 26.0 + 14.0 * sin(x * 0.05)
	# Wolkenbänder (treiben langsam): oben Bögen unterschiedlicher Größe, unten flach und offen
	var crng := RandomNumberGenerator.new()
	crng.seed = SEED + 7
	for cl in [[Vector2(300, 100), 380.0, 0.36, 6.0], [Vector2(690, 192), 290.0, 0.26, 4.0]]:
		var wd: float = cl[1]
		var p0: Vector2 = cl[0]
		p0.x = fposmod(p0.x + t * (cl[3] as float) + wd, 1280.0 + wd) - wd   # läuft endlos durch
		var pts := PackedVector2Array()
		pts.append(p0)
		var x := 0.0
		while x < wd:
			var r := crng.randf_range(9.0, 24.0) * (1.0 - 0.5 * absf(x / wd - 0.5))
			var hh := crng.randf_range(0.5, 0.85)
			for j in 7:
				var a := PI + PI * float(j) / 6.0
				pts.append(p0 + Vector2(x + r + cos(a) * r, sin(a) * r * hh))
			x += 2.0 * r * 0.92
		pts.append(p0 + Vector2(x, 0))
		lines.append([pts, MAGENTA * (cl[2] as float), false, 0.4])
		lines.append([PackedVector2Array([p0 + Vector2(wd * 0.12, 3.0), p0 + Vector2(wd * 0.8, 3.0)]), MAGENTA * ((cl[2] as float) * 0.45), false, 0.3])
	_add(draws, 9000.0, [_layer(lines)])
	# Sterne: Leuchtpunkte, einige funkeln
	var sl := []
	for s in stars:
		var tw := 0.75 + 0.25 * sin(t * (s[3] as float) + (s[2] as float))
		sl.append([PackedVector2Array([s[0]]), WHITE * ((s[1] as float) * tw), false, 1.0])
	_add(draws, 9500.0, [_layer(sl)])
	# Möwen: zwei Flügelbögen, flattern
	var gulls := [[Vector3(-6.0, 7.5, -24.0), 1.1, 0.0], [Vector3(4.0, 9.0, -30.0), 0.8, 2.1]]
	for g in gulls:
		var pos: Vector3 = g[0] + Vector3(t * (g[1] as float), 0.25 * sin(t * 0.9 + (g[2] as float)), 0)
		pos.x = fposmod(pos.x + 30.0, 60.0) - 30.0   # außerhalb des Bildes zurück an den Anfang
		var c := w.project(pos)
		var span := w.px_per_m(w.depth(pos)) * 0.55
		var ph := t * 7.0 + (g[2] as float)
		var al := 0.5 * sin(ph)
		var be := 0.7 * sin(ph - 0.9)
		var pts := PackedVector2Array()
		for side in [-1.0, 1.0]:
			var el := Vector2(side * cos(al), -sin(al)) * span * 0.5
			var tp := el + Vector2(side * cos(al + be), -sin(al + be)) * span * 0.5
			if side < 0:
				pts.append(c + tp)
				pts.append(c + el)
				pts.append(c)
			else:
				pts.append(c + el)
				pts.append(c + tp)
		_add(draws, w.depth(pos), [_layer([[pts, WHITE * 0.95, false, 0.6]])])


# ---------------------------------------------------------------------------
# Oberfläche: Strichschrift, Rahmen; verdeckt die Szene (Austastung)
# ---------------------------------------------------------------------------

func _text(lines: Array, text: String, origin: Vector2, s: float, col: Color, shown := 1000, t_char := -1.0) -> void:
	for st in VecFont.layout(text, origin, s):
		var idx: int = st[1]
		if idx >= shown:
			continue
		var c := col
		if t_char >= 0.0 and idx == shown - 1:
			c = col * (1.0 + 1.6 * t_char)  # frisch gesetztes Zeichen blitzt kurz auf
		# Einzelpunkte (i-Punkte, Umlaute, Satzzeichen) leuchten hell: der Strahl verweilt dort
		lines.append([st[0], c, false, 1.5 if (st[0] as PackedVector2Array).size() == 1 else 0.55])


func _chamfer_rect(r: Rect2, c: float) -> PackedVector2Array:
	var a := r.position
	var b := r.end
	return PackedVector2Array([Vector2(a.x + c, a.y), Vector2(b.x - c, a.y), Vector2(b.x, a.y + c), Vector2(b.x, b.y - c),
		Vector2(b.x - c, b.y), Vector2(a.x + c, b.y), Vector2(a.x, b.y - c), Vector2(a.x, a.y + c)])


func _typed(t0: float, cps: float, n: int) -> Array:
	var x := (t - t0) * cps
	if x <= 0.0:
		return [0, -1.0]
	var shown := mini(n, int(floor(x)) + 1)
	var fresh: float = 1.0 - (x - floor(x)) if shown < n else maxf(0.0, 1.0 - (x - float(n)) * 3.0)
	return [shown, fresh]


func _add_ui(draws: Array) -> void:
	var lines := []
	# Rahmen mit abgeschrägten Ecken; der Ortsname sitzt als Reiter in der oberen Kante
	var loc := "Hafen von Lornholm"
	var ts := 2.4
	var tx := 64.0
	var tw := VecFont.width(loc, ts)
	var r := PANEL
	var c := 10.0
	var a := r.position
	var b := r.end
	var frame_pts := PackedVector2Array([Vector2(tx + tw + 12.0, a.y), Vector2(b.x - c, a.y), Vector2(b.x, a.y + c),
		Vector2(b.x, b.y - c), Vector2(b.x - c, b.y), Vector2(a.x + c, b.y), Vector2(a.x, b.y - c), Vector2(a.x, a.y + c),
		Vector2(a.x + c, a.y), Vector2(tx - 12.0, a.y)])
	lines.append([frame_pts, CYAN * 0.7, false, 0.7])
	_text(lines, loc, Vector2(tx, a.y + ts * 3.0), ts, YELLOW * 0.75)
	lines.append([PackedVector2Array([Vector2(782, 606), Vector2(782, 694)]), CYAN * 0.35, false, 0.4])
	# Erzählzeile mit Tippeffekt
	var l1 := "Die Laterne flackert im Wind."
	var l2 := "Am Kai wartet ein Paket auf dich."
	var ty1 := _typed(0.15, 34.0, l1.length())
	var ty2 := _typed(0.15 + float(l1.length()) / 34.0 + 0.12, 34.0, l2.length())
	_text(lines, l1, Vector2(48, 627), 3.0, WHITE * 0.7, ty1[0], ty1[1])
	_text(lines, l2, Vector2(48, 656), 3.0, WHITE * 0.7, ty2[0], ty2[1])
	# Parser
	var cmd := "> nimm paket"
	var ty3 := _typed(2.45, 11.0, cmd.length())
	_text(lines, cmd, Vector2(48, 692), 2.6, YELLOW * 0.75, ty3[0], ty3[1])
	var cx := 48.0 + float(ty3[0]) * VecFont.ADVANCE * 2.6 + 4.0
	if fmod(t, 0.6) < 0.36:
		lines.append([PackedVector2Array([Vector2(cx, 692), Vector2(cx + 10.4, 692)]), YELLOW * 1.0, false, 0.8])
	# Auswahl rechts, 2 ist gewählt
	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	for i in 3:
		var y := 626.0 + 30.0 * float(i)
		var sel := i == 1
		var col := (WHITE * (0.82 + 0.1 * sin(t * 5.0))) if sel else CYAN * 0.5
		_text(lines, str(i + 1), Vector2(816, y), 2.4, YELLOW * (0.85 if sel else 0.5))
		_text(lines, choices[i], Vector2(850, y), 2.4, col)
		if sel:
			var m := PackedVector2Array([Vector2(798, y - 12.0), Vector2(806, y - 7.2), Vector2(798, y - 2.4)])
			lines.append([m, YELLOW * 0.9, false, 0.6])
	var occ := [_chamfer_rect(Rect2(r.position - Vector2(0, 10), r.size + Vector2(0, 10)), c)]
	_add(draws, 0.0, [_layer(lines, occ, false, [], 2.7)])

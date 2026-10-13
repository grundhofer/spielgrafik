extends Node2D
## Hafen von Lornholm als Rubber-Hose-Zeichentrick der frühen 1930er.
## Gemalte Hintergrundplatte (KI), davor Requisiten als Cels (KI), die alle im selben Takt tanzen: biegen sich
## hin und her und federn auf jedem Schlag (Shader takt.gdshader). Der Dachs ist eine Puppe aus KI-Cels mit
## Gummischlauch-Armen und -Beinen aus Code (puppet.gd). Alles Gezeichnete läuft auf Zweien (15 Posen/s,
## Takt = 6 Ticks = 0,4 s, 150 Schläge/min). Darüber liegt ein alter Zweistreifen-Filmabzug (film.gdshader):
## Korn je Filmbild, Flimmern, Kratzer, Staub, Vignette, Bildstand, Irisblende.
## Zeit nur über aufsummierte delta-Werte, Zufall nur über RandomNumberGenerator mit festem Seed.

const TICKS_PER_S := 15.0
const BEAT := 6
const SEED := 19301013
const FPS := 30.0

const TITLE := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const INK := Color(0.07, 0.05, 0.04)
const CARD := Color(0.11, 0.08, 0.065)
const CREAM := Color(0.96, 0.91, 0.79)
const CREAM_DIM := Color(0.80, 0.74, 0.62)
const SMOKE := Color(0.86, 0.81, 0.74)
const WAVE_INK := Color(0.16, 0.30, 0.30)
const WAVE_HI := Color(0.93, 0.95, 0.88)

# Wasserkringel (Bildschirmlage, auf freiem Wasser zwischen Kimm y 279 und Kaikante y 466, nicht hinter
# Häuschen, Steg, Booten oder Laterne)
const WAVES := [
	Vector2(120, 298), Vector2(212, 302), Vector2(330, 300), Vector2(452, 334), Vector2(478, 296),
	Vector2(612, 292), Vector2(800, 302), Vector2(705, 345), Vector2(575, 372), Vector2(540, 345),
	Vector2(565, 461), Vector2(760, 330)]
# Sterne im klaren oberen Himmel, außerhalb der Titelkarte (x 30–516, beim Aufspringen bis 557) samt Zacken
const STARS := [Vector2(928, 24), Vector2(566, 14), Vector2(652, 38), Vector2(762, 18), Vector2(846, 46),
	Vector2(600, 64)]

var t := 0.0
var frame := 0
var tick := -1
var scene: Dictionary
var props := {}          # Name -> {sprite, mat, meta, phase}
var puppet: Node2D
var film: ShaderMaterial
var drawer: Script

var lamp_glow: Sprite2D
var lantern_glow: Sprite2D
var lantern_core: Sprite2D
var window_glow: Sprite2D
var fx_back: Node2D      # Sterne, Wasserkringel
var fx_mid: Node2D       # Leuchtfeuerstrahlen, Rauch
var fx_hull: Node2D      # Wellenstriche an der Wasserlinie der Boote
var flicker_tab := PackedFloat32Array()

var title_box: Control
var box: Control
var line_lbl: Label
var choice_nodes: Array = []   # [badge Control, label]
var parser_lbl: Label
var cursor: ColorRect
var hilite: Panel
var deco: Node2D
var probe_badger := false
var no_dance := false
var no_film := false


func _ready() -> void:
	drawer = load("res://drawer.gd")
	scene = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	var args := OS.get_cmdline_user_args()
	probe_badger = "--probe-badger" in args
	no_film = "--no-film" in args or probe_badger
	no_dance = "--no-dance" in args
	for a in args:
		if a.begins_with("--t0="):  # Langzeitprüfung: Start bei t0 Sekunden
			t = float(a.substr(5))
			frame = int(round(t * FPS))
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in range(64):
		flicker_tab.append(rng.randf())

	var bg := Sprite2D.new()
	bg.texture = load("res://art/bg.png")
	bg.centered = false
	add_child(bg)
	fx_back = _drawer(_draw_fx_back)
	add_child(fx_back)
	var takt: Shader = load("res://shaders/takt.gdshader")
	# Reihenfolge = Tiefe: Leuchtturm, Boote, Steg, Häuschen, Fässer, Kisten, Laterne, Tau
	_add_prop("lighthouse", takt, 0.0)
	_add_prop("boat_b", takt, 1.3)
	_add_prop("boat_a", takt, 0.4)
	fx_hull = _drawer(_draw_fx_hull)
	add_child(fx_hull)
	_add_prop("jetty", takt, PI)   # aus der Platte freigestellt, kleiner Ausschlag
	var shadows := _drawer(_draw_prop_shadows)
	add_child(shadows)
	_add_prop("cottage", takt, PI)
	fx_mid = _drawer(_draw_fx_mid)
	add_child(fx_mid)
	_add_prop("barrels", takt, PI)
	_add_prop("crates", takt, 0.0)
	_add_prop("lantern", takt, 0.0)   # Fuß vor den Fässern: Lampe hängt vor ihnen
	_add_prop("rope", takt, 0.0)
	var glow_tex: Texture2D = load("res://art/fx/glow.png")
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	lamp_glow = _glow(glow_tex, add, Color(1.0, 0.85, 0.55))
	window_glow = _glow(glow_tex, add, Color(1.0, 0.7, 0.4))
	lantern_glow = _glow(glow_tex, add, Color(1.0, 0.72, 0.42))
	lantern_core = _glow(glow_tex, add, Color(1.0, 0.9, 0.7))
	var shadow_parent := Node2D.new()
	add_child(shadow_parent)
	puppet = load("res://puppet.gd").new()
	add_child(puppet)
	puppet.setup(scene["badger"], drawer, shadow_parent)
	_build_ui()
	_build_film()
	if probe_badger:
		# Prüfmodus: nur die Figur vor Magenta (scripts/measure_badger.py)
		for c in get_children():
			if c != puppet and c is CanvasItem:
				(c as CanvasItem).visible = false
			elif c is CanvasLayer:
				(c as CanvasLayer).visible = false
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
	_update()


func _drawer(fn: Callable) -> Node2D:
	var d: Node2D = drawer.new()
	d.fn = fn
	return d


func _glow(tex: Texture2D, mat: Material, col: Color) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.material = mat
	s.modulate = col
	add_child(s)
	return s


func _add_prop(pname: String, shader: Shader, phase: float) -> void:
	var m: Dictionary = scene["props"][pname]
	var s := Sprite2D.new()
	s.texture = load("res://art/" + m["file"])
	s.centered = false
	s.offset = -Vector2(m["anchor"][0], m["anchor"][1])
	s.position = Vector2(m["at"][0], m["at"][1])
	var mat := ShaderMaterial.new()
	mat.shader = shader
	mat.set_shader_parameter("anchor", Vector2(m["anchor"][0], m["anchor"][1]))
	mat.set_shader_parameter("height", float(m["content_h"]))
	if pname.begins_with("boat"):
		mat.set_shader_parameter("waterline", float(m["at"][1]) + 0.5)
	s.material = mat
	add_child(s)
	props[pname] = {"sprite": s, "mat": mat, "meta": m, "phase": phase, "bend": 0.0, "sx": 1.0, "sy": 1.0}


# ---------------------------------------------------------------- Takt

static func beat_pulse(j: int) -> float:
	return [1.0, -0.55, 0.2, 0.0, 0.0, 0.0][j]


static func lean(k: int, phase: float) -> float:
	# Hin und her in 2 Takten, Ausschlag genau auf dem Schlag (zusammen mit dem Stauchen), zackig:
	# schnell in die Neigung, dort kurz halten
	var s := cos(PI * float(k) / BEAT + phase)
	return signf(s) * pow(absf(s), 0.45)


func prop_point(pname: String, key: String) -> Vector2:
	# Vorwärtsabbildung des Shaders für einen Merkpunkt (Texturpixel) -> Bildschirm
	var p: Dictionary = props[pname]
	var m: Dictionary = p["meta"]
	var a := Vector2(m["anchor"][0], m["anchor"][1])
	var q := Vector2(m["points"][key][0], m["points"][key][1]) - a
	var h := clampf(-q.y / float(m["content_h"]), 0.0, 1.6)
	var d := Vector2(q.x * float(p["sx"]) + float(p["bend"]) * h * h, q.y * float(p["sy"]))
	return (p["sprite"] as Sprite2D).position + d


func _update_props() -> void:
	var j := tick % BEAT
	if no_dance:
		j = 3
	for pname in props:
		var p: Dictionary = props[pname]
		var m: Dictionary = p["meta"]
		var s: Sprite2D = p["sprite"]
		var mat: ShaderMaterial = p["mat"]
		if pname.begins_with("boat"):
			# Boote: wippen auf dem Schlag (ganze Pixel) und schaukeln über zwei Takte
			var base := Vector2(m["at"][0], m["at"][1])
			s.position = base + Vector2(0.0, round(2.0 * beat_pulse(j)))
			s.rotation = 0.0 if no_dance else 0.035 * lean(tick, float(p["phase"]))
			mat.set_shader_parameter("bend", 0.0)
			continue
		var sq := float(m["squash"]) * beat_pulse(j)
		p["bend"] = 0.0 if no_dance else float(m["bend"]) * lean(tick, float(p["phase"]))
		p["sy"] = 1.0 - sq
		p["sx"] = 1.0 + 0.6 * sq
		mat.set_shader_parameter("bend", p["bend"])
		mat.set_shader_parameter("sx", p["sx"])
		mat.set_shader_parameter("sy", p["sy"])


func _update_lights() -> void:
	var j := tick % BEAT
	var beat_i := floori(float(tick) / BEAT)
	# Leuchtfeuer blinkt jeden zweiten Schlag
	var flash := beat_i % 2 == 0 and j < 3
	lamp_glow.position = prop_point("lighthouse", "lamp").round()
	var lf := 0.3
	if beat_i % 2 == 0:
		lf = [1.0, 0.8, 0.55, 0.35, 0.3, 0.3][j]
	lamp_glow.scale = Vector2.ONE * (0.55 + 0.9 * lf)
	lamp_glow.modulate.a = 0.35 + 0.55 * lf
	lamp_glow.set_meta("flash", flash)
	# Laterne flackert (Zufallstabelle je Tick, leicht geglättet) und pulst auf dem Schlag
	var fl := 0.6 * flicker_tab[tick % 64] + 0.4 * flicker_tab[(tick + 63) % 64]
	var lp := prop_point("lantern", "lamp").round()
	lantern_glow.position = lp
	lantern_glow.scale = Vector2.ONE * (1.45 + 0.25 * fl + 0.12 * maxf(beat_pulse(j), 0.0))
	lantern_glow.modulate.a = 0.30 + 0.22 * fl
	lantern_core.position = lp
	lantern_core.scale = Vector2.ONE * (0.42 + 0.08 * fl)
	lantern_core.modulate.a = 0.55 + 0.3 * fl
	window_glow.position = prop_point("cottage", "window").round()
	window_glow.scale = Vector2.ONE * (0.75 + 0.06 * flicker_tab[(tick * 7) % 64])
	window_glow.modulate.a = 0.38


# ---------------------------------------------------------------- Effekte (gezeichnet)

func _draw_fx_back(ci: CanvasItem) -> void:
	var j := tick % BEAT
	var beat_i := floori(float(tick) / BEAT)
	# Sterne: vierzackig, funkeln abwechselnd auf dem Schlag
	for i in range(STARS.size()):
		var on := (beat_i + i) % 2 == 0
		var r := 8.0 if on and j < 2 else 5.0
		if on and j == 0:
			r = 10.5
		_star(ci, STARS[i], r)
	# Wasserkringel: zwei Bögen wie im gemalten Meer, wechseln je Schlag die Form und rücken 3 px
	for i in range(WAVES.size()):
		var w: Vector2 = WAVES[i]
		var ph := (beat_i + i) % 2
		var x := w.x + (3.0 if ph == 1 else 0.0)
		var amp := 3.0 if ph == 0 else 1.8
		_wave(ci, Vector2(x, w.y), 9.0 + (i % 3), amp)


func _star(ci: CanvasItem, c: Vector2, r: float) -> void:
	var pts := PackedVector2Array()
	for k in range(8):
		var a := PI * 0.25 * k - PI * 0.5
		var rr := r if k % 2 == 0 else r * 0.3
		pts.append(c + Vector2(cos(a), sin(a)) * rr)
	ci.draw_colored_polygon(pts, Color(1.0, 0.95, 0.80, 1.0))


func _wave(ci: CanvasItem, c: Vector2, r: float, amp: float) -> void:
	var pts := PackedVector2Array()
	for k in range(13):
		var u := float(k) / 12.0
		pts.append(c + Vector2((u - 0.5) * 2.0 * r * 1.6, -amp * absf(sin(u * TAU))))
	ci.draw_polyline(pts, WAVE_INK, 2.2, true)
	var hi := PackedVector2Array()
	for k in range(5):
		var u := float(k) / 4.0 * 0.4 + 0.05
		hi.append(c + Vector2((u - 0.5) * 2.0 * r * 1.6, -amp * absf(sin(u * TAU)) - 2.0))
	ci.draw_polyline(hi, WAVE_HI, 1.6, true)


func _draw_fx_hull(ci: CanvasItem) -> void:
	# Wellenstriche über der Schnittkante der Rümpfe: setzen die Boote ins Wasser, wechseln je Schlag
	var beat_i := floori(float(tick) / BEAT)
	for bname in ["boat_a", "boat_b"]:
		var m: Dictionary = props[bname]["meta"]
		var w := float(m["size"][0]) * (0.30 if bname == "boat_a" else 0.27)
		var base := Vector2(m["at"][0], float(m["at"][1]) + 1.0)
		for k in range(-1, 2):
			var ph := (beat_i + k + 2) % 2
			_wave(ci, base + Vector2(k * w + (3.0 if ph == 1 else -2.0), 0.0), 10.0, 2.6 if ph == 0 else 1.6)


func _draw_fx_mid(ci: CanvasItem) -> void:
	var j := tick % BEAT
	# Strahlen des Leuchtfeuers beim Blinken (gezeichnete Lichtstriche wie im Trickfilm)
	if lamp_glow.get_meta("flash", false):
		var c := lamp_glow.position
		var rot := 0.2 * floori(float(tick) / (2 * BEAT))
		var lens: Array = [1.0, 0.8, 0.55]
		for k in range(10):
			var a := rot + TAU * k / 10.0
			var r0 := 14.0
			var r1 := r0 + (34.0 if k % 2 == 0 else 22.0) * float(lens[j])
			var dir := Vector2(cos(a), sin(a))
			var nrm := Vector2(-dir.y, dir.x)
			var pts := PackedVector2Array([c + dir * r0 + nrm * 2.6, c + dir * r1, c + dir * r0 - nrm * 2.6])
			ci.draw_colored_polygon(pts, Color(1.0, 0.94, 0.78, 0.9))
	# Rauch aus dem Schornstein: jeder Schlag ein Wölkchen, steigt und wächst, ploppt auf dem Schlag und
	# schrumpft am Ende weg (wie gezeichnete Rauchballen, keine Überblendung)
	var chim := prop_point("cottage", "chimney")
	var beat_i := floori(float(tick) / BEAT)
	for k in range(5, -1, -1):
		var born := (beat_i - k) * BEAT
		var age := tick - born
		if age < 0 or age >= 30:
			continue
		var pos := chim + Vector2(age * 0.9 + 3.0 * sin(age * 0.6 + born * 0.37), -5.0 - age * 3.1)
		var r := 6.0 + age * 0.55
		if age >= 20:
			r *= 1.0 - float(age - 20) / 10.0
		if j == 0 and age > 0:
			r *= 1.12
		if r > 0.8:
			_puff(ci, pos, r, 1.0)


func _puff(ci: CanvasItem, c: Vector2, r: float, a: float) -> void:
	var blobs := [Vector2(0, 0), Vector2(-0.62, 0.25), Vector2(0.6, 0.2), Vector2(0.05, -0.45)]
	var rs := [1.0, 0.62, 0.66, 0.6]
	for i in range(blobs.size()):
		ci.draw_circle(c + blobs[i] * r, r * rs[i] + 2.2, Color(INK, a), true, -1.0, true)
	for i in range(blobs.size()):
		ci.draw_circle(c + blobs[i] * r, r * rs[i], Color(SMOKE, a), true, -1.0, true)
	ci.draw_circle(c + Vector2(-0.3, -0.35) * r, r * 0.22, Color(1, 1, 1, 0.5 * a), true, -1.0, true)


func _draw_prop_shadows(ci: CanvasItem) -> void:
	# flache Kontaktschatten unter den Requisiten auf dem Kai; werden breiter, wenn die Requisite federt
	for pname in ["cottage", "lantern", "barrels", "crates", "rope"]:
		var p: Dictionary = props[pname]
		var s: Sprite2D = p["sprite"]
		var w := {"cottage": 178.0, "lantern": 26.0, "barrels": 84.0, "crates": 73.0, "rope": 52.0}[pname] as float
		w *= float(p["sx"])
		var pts := PackedVector2Array()
		for k in range(24):
			var a := TAU * k / 24.0
			pts.append(s.position + Vector2(cos(a) * w, sin(a) * 6.0 + 1.0))
		ci.draw_colored_polygon(pts, Color(0.08, 0.04, 0.03, 0.28))


# ---------------------------------------------------------------- Oberfläche (Zwischentitel der 1930er)

func _panel_style(bg: Color, border: Color, bw: int, radius: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(bw)
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	return sb


func _build_ui() -> void:
	var ui := CanvasLayer.new()
	ui.layer = 5
	add_child(ui)
	# Corben setzt "ck" als Zierligatur; für die Lesbarkeit Ligaturen und Kontextvarianten abschalten
	var ts := TextServerManager.get_primary_interface()
	var feats := {}
	for tag in ["liga", "clig", "dlig", "calt"]:
		feats[ts.name_to_tag(tag)] = 0
	var f_bold := FontVariation.new()
	f_bold.base_font = load("res://fonts/Corben-Bold.ttf")
	f_bold.opentype_features = feats
	var f_reg := FontVariation.new()
	f_reg.base_font = load("res://fonts/Corben-Regular.ttf")
	f_reg.opentype_features = feats
	# Titelkarte oben links
	title_box = Control.new()
	title_box.position = Vector2(30, 24)
	title_box.size = Vector2(486, 66)
	title_box.pivot_offset = Vector2(243, 33)
	ui.add_child(title_box)
	var tp := Panel.new()
	tp.size = title_box.size
	tp.add_theme_stylebox_override("panel", _panel_style(CARD, CREAM, 3, 14))
	title_box.add_child(tp)
	var ti := Panel.new()
	ti.position = Vector2(7, 7)
	ti.size = title_box.size - Vector2(14, 14)
	ti.add_theme_stylebox_override("panel", _panel_style(Color(0, 0, 0, 0), CREAM_DIM, 1, 9))
	title_box.add_child(ti)
	var tl := Label.new()
	tl.text = TITLE
	tl.add_theme_font_override("font", f_bold)
	tl.add_theme_font_size_override("font_size", 32)
	tl.add_theme_color_override("font_color", CREAM)
	tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	tl.size = title_box.size
	tl.position = Vector2(0, -1)
	title_box.add_child(tl)
	# Textkarte unten
	box = Control.new()
	box.position = Vector2(30, 600)
	box.size = Vector2(1220, 106)
	box.pivot_offset = Vector2(610, 106)
	ui.add_child(box)
	var bp := Panel.new()
	bp.size = box.size
	bp.add_theme_stylebox_override("panel", _panel_style(CARD, CREAM, 3, 14))
	box.add_child(bp)
	var bi := Panel.new()
	bi.position = Vector2(7, 7)
	bi.size = box.size - Vector2(14, 14)
	bi.add_theme_stylebox_override("panel", _panel_style(Color(0, 0, 0, 0), CREAM_DIM, 1, 9))
	box.add_child(bi)
	deco = _drawer(_draw_deco)
	box.add_child(deco)
	line_lbl = Label.new()
	line_lbl.add_theme_font_override("font", f_reg)
	line_lbl.add_theme_font_size_override("font_size", 23)
	line_lbl.add_theme_color_override("font_color", CREAM)
	line_lbl.position = Vector2(44, 13)
	box.add_child(line_lbl)
	hilite = Panel.new()
	hilite.add_theme_stylebox_override("panel", _panel_style(CREAM, CREAM, 0, 15))
	hilite.visible = false
	box.add_child(hilite)
	var xs := [44.0, 382.0, 694.0]
	for i in range(3):
		var badge := Panel.new()
		badge.size = Vector2(30, 30)
		badge.pivot_offset = Vector2(15, 15)
		badge.position = Vector2(xs[i], 59)
		badge.add_theme_stylebox_override("panel", _panel_style(CREAM, INK, 2, 15))
		box.add_child(badge)
		var num := Label.new()
		num.text = str(i + 1)
		num.add_theme_font_override("font", f_bold)
		num.add_theme_font_size_override("font_size", 19)
		num.add_theme_color_override("font_color", CARD)
		num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		num.size = badge.size
		num.position = Vector2(0, -1)
		badge.add_child(num)
		var lbl := Label.new()
		lbl.text = CHOICES[i]
		lbl.add_theme_font_override("font", f_reg)
		lbl.add_theme_font_size_override("font_size", 22)
		lbl.add_theme_color_override("font_color", CREAM)
		lbl.position = Vector2(xs[i] + 48.0, 58)
		box.add_child(lbl)
		choice_nodes.append([badge, lbl])
	parser_lbl = Label.new()
	parser_lbl.add_theme_font_override("font", f_reg)
	parser_lbl.add_theme_font_size_override("font_size", 22)
	parser_lbl.add_theme_color_override("font_color", CREAM)
	parser_lbl.position = Vector2(1044, 58)
	box.add_child(parser_lbl)
	cursor = ColorRect.new()
	cursor.color = CREAM
	cursor.size = Vector2(11, 22)
	box.add_child(cursor)


func _draw_deco(ci: CanvasItem) -> void:
	# Ecken der Textkarte: kleine Rauten wie auf Zwischentiteln
	for c in [Vector2(16, 16), Vector2(1204, 16), Vector2(16, 90), Vector2(1204, 90)]:
		var pts := PackedVector2Array([c + Vector2(0, -5), c + Vector2(5, 0), c + Vector2(0, 5), c + Vector2(-5, 0)])
		ci.draw_colored_polygon(pts, CREAM)


func _update_ui() -> void:
	var j := tick % BEAT
	# Titelkarte springt in Tick 3 auf (gestaucht, überschießend), danach federt sie leicht im Takt
	var tk := tick - 3
	if tk < 0:
		title_box.visible = false
	else:
		title_box.visible = true
		var sc: float = [0.3, 1.15, 0.94, 1.0][min(tk, 3)]
		title_box.scale = Vector2(sc, sc) * (1.0 + 0.015 * maxf(beat_pulse(j), 0.0))
		title_box.rotation = 0.012 * lean(tick, 0.0) if tk >= 3 else 0.0
	# Textkarte steigt in Tick 8 auf; Zeile tippt mit 30 Zeichen/s; Antworten erscheinen je Schlag
	var bk := tick - 8
	box.visible = bk >= 0
	if bk >= 0:
		var sy: float = [0.2, 1.1, 0.97, 1.0][min(bk, 3)]
		box.scale = Vector2(1.0, sy)
	var chars := clampi(int((t - 0.8) * 30.0), 0, LINE.length())
	line_lbl.text = LINE.substr(0, chars)
	for i in range(3):
		var appear := 36 + i * BEAT
		var badge: Panel = choice_nodes[i][0]
		var lbl: Label = choice_nodes[i][1]
		badge.visible = tick >= appear
		lbl.visible = tick >= appear
		var bt := tick - appear
		var s := 1.0
		if bt >= 0 and bt < 3:
			s = [0.4, 1.25, 0.95][bt]
		elif bt >= 3:
			s = 1.0 + 0.12 * maxf(beat_pulse(j), 0.0)
		badge.scale = Vector2(s, s)
	# Auswahl 2 ab Tick 72 hervorgehoben (cremefarbene Fläche, dunkle Schrift)
	var sel := tick >= 72
	hilite.visible = sel
	var l2: Label = choice_nodes[1][1]
	if sel:
		var hs: float = [1.12, 0.97, 1.0][min(tick - 72, 2)]
		hilite.size = Vector2(l2.get_minimum_size().x + 10.0, 30.0)
		hilite.position = l2.position + Vector2(-5.0, 3.0)
		hilite.pivot_offset = hilite.size * 0.5
		hilite.scale = Vector2(hs, hs)
		l2.add_theme_color_override("font_color", CARD)
	else:
		l2.add_theme_color_override("font_color", CREAM)
	# Parserzeile tippt ab Tick 50 mit 10 Zeichen/s, Blockcursor blinkt im Takt
	var pc := clampi(int((tick - 50) / 1.5), 0, PARSER.length())
	parser_lbl.visible = tick >= 50
	parser_lbl.text = PARSER.substr(0, pc)
	cursor.visible = tick >= 50 and (pc < PARSER.length() or floori(float(tick) / BEAT) % 2 == 0)
	cursor.position = parser_lbl.position + Vector2(parser_lbl.get_minimum_size().x + 4.0, 5.0)


# ---------------------------------------------------------------- Filmabzug

func _build_film() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	var rect := ColorRect.new()
	rect.size = Vector2(1280, 720)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	film = ShaderMaterial.new()
	film.shader = load("res://shaders/film.gdshader")
	rect.material = film
	layer.add_child(rect)
	layer.visible = not no_film


func _update_film() -> void:
	# Alles je Filmbild (30/s) aus einem Zufallsgenerator mit Seed aus der Bildnummer: reproduzierbar, auch ab --t0
	var r := RandomNumberGenerator.new()
	r.seed = SEED + frame * 7919
	film.set_shader_parameter("frame", float(frame % 997))
	film.set_shader_parameter("flicker", 1.0 + (r.randf() - 0.5) * 0.07)
	var wy := 1.0 if r.randf() < 0.3 else 0.0
	var wx := 1.0 if r.randf() < 0.12 else 0.0
	film.set_shader_parameter("weave", Vector2(wx, wy))
	film.set_shader_parameter("dust_seed", float(frame % 911) * 1.37)
	film.set_shader_parameter("dust_amount", 0.035 + 0.03 * r.randf())
	# kurzer Kratzer in einzelnen Bildern
	if r.randf() < 0.18:
		film.set_shader_parameter("scratch1", Vector4(r.randf_range(60, 1220), r.randf_range(0.35, 0.8), r.randf_range(0.8, 1.6), 1.0 if r.randf() < 0.6 else 0.0))
	else:
		film.set_shader_parameter("scratch1", Vector4(-100, 0, 1, 0))
	# langer Kratzer: bleibt 40 Bilder lang (wandert leicht), in 70 % der Abschnitte
	var seg := floori(frame / 40.0)
	var rs := RandomNumberGenerator.new()
	rs.seed = SEED + seg * 104729
	if rs.randf() < 0.7:
		var x0 := rs.randf_range(120, 1160)
		film.set_shader_parameter("scratch0", Vector4(x0 + (frame % 40) * rs.randf_range(-0.4, 0.4), rs.randf_range(0.25, 0.5), 1.2, 1.0))
	else:
		film.set_shader_parameter("scratch0", Vector4(-100, 0, 1, 0))
	# Fussel: in manchen Abschnitten von 25 Bildern für 3 Bilder
	var hseg := floori(frame / 25.0)
	var rh := RandomNumberGenerator.new()
	rh.seed = SEED + hseg * 15485863
	if rh.randf() < 0.35 and frame % 25 < 3:
		film.set_shader_parameter("hair", Vector4(rh.randf_range(150, 1130), rh.randf_range(100, 560), rh.randf_range(14, 30), 0.8))
	else:
		film.set_shader_parameter("hair", Vector4(-100, -100, 0, 0))
	# Irisblende öffnet sich in den ersten 0,7 s
	var ir := lerpf(26.0, 1500.0, smooth01(clampf(t / 0.7, 0.0, 1.0)))
	film.set_shader_parameter("iris", Vector3(640.0, 360.0, ir))


static func smooth01(u: float) -> float:
	return u * u * (3.0 - 2.0 * u)


# ---------------------------------------------------------------- Ablauf

func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update()


func _update() -> void:
	var k := floori(t * TICKS_PER_S + 0.0001)
	if k != tick:
		tick = k
		_update_props()
		_update_lights()
		puppet.update_pose(tick)
		fx_back.queue_redraw()
		fx_hull.queue_redraw()
		fx_mid.queue_redraw()
		_update_ui()
	_update_film()

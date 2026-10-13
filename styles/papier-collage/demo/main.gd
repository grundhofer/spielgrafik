extends Node2D
## Hafen von Lornholm als Papiercollage: Jede Ebene ist ein ausgeschnittenes oder gerissenes Papierstück mit
## eigenem Schatten auf der Lage dahinter. Hinten der KI-Hintergrund (Himmel aus Seidenpapierstreifen, Landzunge
## mit Leuchtturm), davor vier gerissene Meeresstreifen aus Code, die gegeneinander hin- und hergleiten wie in
## einem Papiertheater, dazwischen Boote und Steg (KI-Requisitenbogen), vorn Kai und Häuschen (KI-Bild).
## Lichter: Laterne, Fenster und Leuchtfeuer als warmer Schein, der Lichtkeil als Seidenpapier, das sich um den
## Turm dreht. Der Dachs ist eine Gliederpuppe aus Papierteilen (puppet.gd). Die Oberfläche ist ein liniertes
## Notizblatt mit Kreppband, Antworten auf Papierzetteln und dem Ortsnamen aus aufgeklebten Schnipseln.
## Alles hängt nur von der aufsummierten Zeit ab; Flackern über FastNoiseLite mit festem Seed.
##
## Benutzerargumente (nach "--"):
##   --t0=<s>         Startzeit (Langzeitprüfung)
##   --badger-only    nur die Puppe vor hellem Grund (Messung von Füßen und Kopf)
##   --smooth         Puppe mit 30 statt 15 Posen/s (Vergleich)
##   --only=a,b       nur diese Puppenteile (z. B. foot_n,shin_n)
##   --no-shadows     ohne Schlagschatten zwischen den Lagen (Vergleich)
##   --no-ui          ohne Oberfläche

const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const TITLE := "Hafen von Lornholm"
const SHADOW_OFF := Vector2(4.0, 6.0)
const BEAM_T := 6.4
const BEAM_PHASE := 0.62           # Strahl voll nach links bei 2,4 s, Aufblitzen bei 4,0 s

var t := 0.0
var t0 := 0.0
var L: Dictionary
var U: Dictionary
var noise := FastNoiseLite.new()
var badger_only := false
var no_shadows := false
var no_ui := false
var mat_far: ShaderMaterial
var mat_near: ShaderMaterial
var mat_puppet: ShaderMaterial
var puppet: Node2D
var strips := []                   # [node, shadow, top, amp, period, phase]
var boats := []                    # [node, shadow, base, amp_rot, period, phase]
var clouds := []                   # [node, shadow, base, speed]
var gulls := []                    # [root, wing, wing_shadow, from, to, flap, phase, flip]
var smokes := []                   # [node, shadow]
var beam: Sprite2D
var lamp_glow: Sprite2D
var lamp_flash: Sprite2D
var win_glow: Sprite2D
var lan_glow: Sprite2D
var lan_pool: Sprite2D
var ui_line: Label
var ui_parser: Label
var ui_cursor: ColorRect
var slips := []                    # [node, shadow, base_pos, base_rot]
var snips := []                    # [node, shadow, base_pos, rot, delay]


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--badger-only":
			badger_only = true
		elif a == "--no-shadows":
			no_shadows = true
		elif a == "--no-ui":
			no_ui = true
	t = t0
	noise.seed = 7
	noise.frequency = 1.0
	L = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene/layout.json"))
	U = JSON.parse_string(FileAccess.get_file_as_string("res://art/ui/ui.json"))
	var rig: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/puppet/rig.json"))
	var lit := load("res://shaders/lit.gdshader") as Shader
	var lp := _rect_center(L["lantern_glass"])
	var wp := _rect_center(L["window"])
	mat_far = _mat(lit, Vector3(0.80, 0.80, 0.92), lp, 0.25, wp)
	mat_near = _mat(lit, Vector3(0.80, 0.78, 0.90), lp, 0.55, wp)
	mat_puppet = _mat(lit, Vector3(0.88, 0.86, 0.94), lp, 0.55, wp)

	if badger_only:
		var bg := ColorRect.new()
		bg.color = Color(0.93, 0.93, 0.9)
		bg.size = Vector2(1280, 720)
		add_child(bg)
	else:
		_build_scene()
	puppet = preload("res://puppet.gd").new()
	add_child(puppet)
	puppet.setup(rig, mat_puppet, 588.0, 436.0)     # Sohlenzeile 14 px über dem Notizblatt-Rand (ab 597)
	if not badger_only:
		_build_lights_front()
		if not no_ui:
			_build_ui()
	_update(0.0)


func _rect_center(r) -> Vector2:
	return Vector2((float(r[0]) + float(r[2])) * 0.5, (float(r[1]) + float(r[3])) * 0.5)


func _mat(sh: Shader, tint: Vector3, lp: Vector2, k: float, wp: Vector2) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = sh
	m.set_shader_parameter("tint", tint)
	m.set_shader_parameter("lamp_pos", lp)
	m.set_shader_parameter("lamp_k", k)
	m.set_shader_parameter("win_pos", wp)
	m.set_shader_parameter("win_r", 150.0)
	m.set_shader_parameter("win_k", 0.35)
	return m


func _tex(p: String) -> Texture2D:
	return load("res://art/" + p) as Texture2D


## Papierteil mit Schatten. Gibt [Teil, Schatten] zurück; beide als Node2D mit Sprite, Drehpunkt pivot.
func _piece(parent: Node, dir: String, meta: Dictionary, pivot: Vector2, mat: Material,
		shadow_a := 0.4, shadow_off := SHADOW_OFF) -> Array:
	var pad := float(meta.get("shadow_pad", meta.get("pad", 0)))
	var sh := Node2D.new()
	var shs := Sprite2D.new()
	shs.texture = _tex(dir + "/" + meta["shadow"])
	shs.centered = false
	shs.offset = -pivot - Vector2(pad, pad)
	shs.modulate = Color(1, 1, 1, 0.0 if no_shadows else shadow_a)
	sh.add_child(shs)
	sh.set_meta("off", shadow_off)
	parent.add_child(sh)
	var n := Node2D.new()
	var sp := Sprite2D.new()
	sp.texture = _tex(dir + "/" + meta["file"])
	sp.centered = false
	sp.offset = -pivot
	if mat:
		sp.material = mat
	n.add_child(sp)
	parent.add_child(n)
	return [n, sh]


func _put(pair: Array, pos: Vector2, rot := 0.0, scl := Vector2.ONE) -> void:
	pair[0].position = pos
	pair[0].rotation = rot
	pair[0].scale = scl
	pair[1].position = pos + pair[1].get_meta("off")
	pair[1].rotation = rot
	pair[1].scale = scl


func _glow(parent: Node, pos: Vector2, size: Vector2, col: Color, inner := 0.0) -> Sprite2D:
	var g := Gradient.new()
	g.set_color(0, Color(col.r, col.g, col.b, 1.0))
	g.set_color(1, Color(col.r, col.g, col.b, 0.0))
	if inner > 0.0:
		g.add_point(inner, Color(col.r, col.g, col.b, 0.55))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	gt.width = 128
	gt.height = 128
	var s := Sprite2D.new()
	s.texture = gt
	s.position = pos
	s.scale = size / 128.0
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	s.material = m
	parent.add_child(s)
	return s


func _build_scene() -> void:
	var back := Sprite2D.new()
	back.texture = _tex("scene/back.png")
	back.centered = false
	add_child(back)
	var lamp := Vector2(L["lamp"][0], L["lamp"][1])
	lamp_glow = _glow(self, lamp, Vector2(70, 70), Color(1.0, 0.85, 0.5), 0.25)
	# Wolken aus dem Requisitenbogen ziehen langsam
	for c in [["cloud_a", Vector2(250, 12), 5.0]]:
		var pr := _piece(self, "scene", L[c[0]], Vector2.ZERO, mat_far, 0.32, Vector2(6, 8))
		clouds.append([pr, c[1], c[2]])
	# Lichtkeil aus Seidenpapier
	beam = Sprite2D.new()
	beam.texture = _tex("ui/beam.png")
	beam.centered = false
	beam.offset = -Vector2(U["beam"]["pivot"][0], U["beam"]["pivot"][1])
	beam.position = lamp
	beam.modulate = Color(1.0, 0.93, 0.7, 0.72)
	add_child(beam)
	lamp_flash = _glow(self, lamp, Vector2(150, 150), Color(1.0, 0.86, 0.55), 0.2)
	# Möwen: Körper und Flügel als zwei Papierteile, Flügel an einer Klammer
	# [von, nach, Flügelschläge/s, Phase, nach links, Größe, Umlaufzeit s, Zeitversatz s]: Wege führen über die
	# Bildränder hinaus und wiederholen sich, damit die Szene beliebig lange läuft
	for gdef in [[Vector2(1310, 226), Vector2(-90, 150), 2.3, 0.0, true, 1.0, 22.0, 4.0],
			[Vector2(-80, 300), Vector2(1360, 236), 2.8, 1.7, false, 0.78, 24.0, 10.7]]:
		var root := Node2D.new()
		add_child(root)
		var wing_sh := _piece(root, "scene", L["gull_wing"], _v(L["gull_wing"]["pivot"]), mat_far, 0.3,
				Vector2(3, 5))
		var body := _piece(root, "scene", L["gull_body"], _v(L["gull_body"]["pivot"]), mat_far, 0.3, Vector2(3, 5))
		_put(body, Vector2.ZERO)
		gulls.append([root, wing_sh, gdef[0], gdef[1], gdef[2], gdef[3], gdef[4], gdef[5], gdef[6], gdef[7]])
	# Meeresstreifen und dazwischen Boote und Steg
	var st: Array = L["strips"]
	for i in st.size():
		var meta: Dictionary = st[i]
		var pr := _piece(self, "scene", meta, Vector2(0, 14), mat_far if i < 2 else mat_near, 0.28, Vector2(0, -1))
		strips.append([pr, float(meta["top"]), [12.0, 16.0, 11.0, 18.0][i], [4.3, 3.7, 4.9, 3.3][i],
				[0.0, 2.1, 4.0, 1.1][i]])
		if i == 0:
			var b := _piece(self, "scene", L["boat_l"], _v(L["boat_l"]["pivot"]), mat_far, 0.36, Vector2(4, 5))
			boats.append([b, Vector2(552, 442), 1.6, 3.4, 0.4])
		elif i == 1:
			var j := _piece(self, "scene", L["jetty"], Vector2.ZERO, mat_far, 0.42, Vector2(5, 7))
			_put(j, Vector2(470, 424))
		elif i == 2:
			var b := _piece(self, "scene", L["boat_r"], _v(L["boat_r"]["pivot"]), mat_near, 0.4, Vector2(5, 6))
			boats.append([b, Vector2(745, 504), 1.9, 3.9, 2.0])
	# Rauch hinter dem Schornstein
	for i in 5:
		var pr := _piece(self, "scene", L["smoke"], Vector2(23, 24), mat_far, 0.25, Vector2(4, 6))
		smokes.append(pr)
	# Kai und Häuschen
	var q := _piece(self, "scene", L["quay"], Vector2.ZERO, mat_near, 0.5, Vector2(7, 9))
	_put(q, Vector2.ZERO)
	var cot := _piece(self, "scene", L["cottage"], Vector2.ZERO, mat_near, 0.5, Vector2(8, 10))
	_put(cot, Vector2(L["cottage"]["pos"][0], L["cottage"]["pos"][1]))
	win_glow = _glow(self, _rect_center(L["window"]), Vector2(190, 170), Color(1.0, 0.72, 0.32), 0.3)
	lan_pool = _glow(self, Vector2(850, 572), Vector2(420, 70), Color(1.0, 0.66, 0.3), 0.0)


func _build_lights_front() -> void:
	lan_glow = _glow(self, _rect_center(L["lantern_glass"]), Vector2(170, 170), Color(1.0, 0.74, 0.36), 0.22)
	# Bühnenlicht: Ränder leicht abgedunkelt (multiplikativ), wie bei einer fotografierten Papierbühne
	var g := Gradient.new()
	g.set_color(0, Color(1, 1, 1, 1))
	g.set_color(1, Color(0.62, 0.6, 0.7, 1))
	g.set_offset(0, 0.55)
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.45)
	gt.fill_to = Vector2(1.08, 0.45)
	gt.width = 256
	gt.height = 144
	var v := Sprite2D.new()
	v.texture = gt
	v.centered = false
	v.scale = Vector2(1280.0 / 256.0, 720.0 / 144.0)
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_MUL
	v.material = m
	add_child(v)


func _v(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


# ---------------------------------------------------------------- Oberfläche
func _font(p: String) -> FontFile:
	return load("res://fonts/" + p) as FontFile


func _build_ui() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 10
	add_child(layer)
	var ink := Color(0.15, 0.14, 0.2)
	var f_txt := _font("CourierPrime-Regular.ttf")
	var f_bold := _font("CourierPrime-Bold.ttf")
	# Notizblatt
	var note := _piece(layer, "ui", U["note"], Vector2.ZERO, null, 0.45, Vector2(4, 6))
	_put(note, Vector2(22, 598), deg_to_rad(-0.25))
	for i in 2:
		var tp := _piece(layer, "ui", U["tape_%d" % i], Vector2(46, 15), null, 0.18, Vector2(1, 2))
		_put(tp, [Vector2(70, 606), Vector2(1214, 604)][i], deg_to_rad([-9.0, 7.0][i]))
	ui_line = Label.new()
	ui_line.text = LINE
	ui_line.position = Vector2(92, 616)
	ui_line.add_theme_font_override("font", f_txt)
	ui_line.add_theme_font_size_override("font_size", 23)
	ui_line.add_theme_color_override("font_color", ink)
	ui_line.rotation = deg_to_rad(-0.25)
	layer.add_child(ui_line)
	# Antwortzettel
	var x := 88.0
	for i in 3:
		var meta: Dictionary = U["slip_%d" % i]
		var w := float(meta["size"][0])
		var base := Vector2(x + w * 0.5, 676)
		var rot := deg_to_rad([-1.4, 0.9, -0.6][i])
		var pr := _piece(layer, "ui", meta, Vector2(w * 0.5, 18), null, 0.42, Vector2(2, 3))
		var lb := Label.new()
		lb.text = "%d  %s" % [i + 1, CHOICES[i]]
		lb.add_theme_font_override("font", f_bold)
		lb.add_theme_font_size_override("font_size", 18)
		lb.add_theme_color_override("font_color", ink if i != 1 else Color(0.62, 0.16, 0.14))
		lb.position = Vector2(-w * 0.5 + 14, -12)
		pr[0].add_child(lb)
		slips.append([pr, base, rot])
		x += w + 18.0
	ui_parser = Label.new()
	ui_parser.position = Vector2(1006, 662)
	ui_parser.add_theme_font_override("font", f_bold)
	ui_parser.add_theme_font_size_override("font_size", 20)
	ui_parser.add_theme_color_override("font_color", ink)
	ui_parser.text = PARSER
	layer.add_child(ui_parser)
	ui_cursor = ColorRect.new()
	ui_cursor.color = ink
	ui_cursor.size = Vector2(11, 20)
	layer.add_child(ui_cursor)
	# Ortsname aus Schnipseln
	var fonts := [_font("LilitaOne-Regular.ttf"), _font("AbrilFatface-Regular.ttf"), f_bold]
	var rng := RandomNumberGenerator.new()
	rng.seed = 41
	var sx := 648.0
	var si := 0
	for ch in TITLE:
		if ch == " ":
			sx += 14.0
			continue
		var meta: Dictionary = U["snips"][si % U["snips"].size()]
		var w := float(meta["size"][0])
		var h := float(meta["size"][1])
		var pr := _piece(layer, "ui", meta, Vector2(w * 0.5, h * 0.5), null, 0.45, Vector2(2.5, 3.5))
		var paper: Array = meta["paper"]
		var lum: float = 0.3 * paper[0] + 0.59 * paper[1] + 0.11 * paper[2]
		var lb := Label.new()
		lb.text = ch
		var f: FontFile = fonts[(si * 7 + 3) % 3]
		var fs: int = 33 if f != f_bold else 35
		lb.add_theme_font_override("font", f)
		lb.add_theme_font_size_override("font_size", fs)
		lb.add_theme_color_override("font_color", Color(0.96, 0.94, 0.88) if lum < 110 else
				(Color(0.62, 0.13, 0.12) if si % 4 == 1 else ink))
		var sz := f.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, fs)
		lb.position = -sz * 0.5 + Vector2(0, -1)
		pr[0].add_child(lb)
		var ssc := 0.86
		var base := Vector2(sx + w * ssc * 0.5, 44 + rng.randf_range(-3.0, 3.0))
		snips.append([pr, base, deg_to_rad(rng.randf_range(-7.0, 7.0)), 0.15 + 0.05 * si, ssc])
		sx += w * ssc - 1.0
		si += 1


# ---------------------------------------------------------------- Zeitablauf
func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _ease(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func _update(dt: float) -> void:
	puppet.advance(t, maxf(dt, 1.0 / 30.0))
	if badger_only:
		return
	# Laterne und Fenster flackern
	var fl := 0.82 + 0.12 * noise.get_noise_1d(t * 3.1) + 0.06 * noise.get_noise_1d(t * 11.0 + 40.0)
	var gust := _ease((t - 2.2) / 0.15) * (1.0 - _ease((t - 2.6) / 0.3))
	fl -= 0.18 * gust * (0.5 + 0.5 * sin(t * 37.0))
	for m in [mat_far, mat_near, mat_puppet]:
		m.set_shader_parameter("lamp_k", (0.25 if m == mat_far else 0.6) * fl)
	var wf := 0.9 + 0.08 * noise.get_noise_1d(t * 1.7 + 100.0)
	for m in [mat_far, mat_near, mat_puppet]:
		m.set_shader_parameter("win_k", 0.35 * wf)
	lan_glow.modulate = Color(1, 1, 1, 0.42 * fl)
	lan_pool.modulate = Color(1, 1, 1, 0.22 * fl)
	win_glow.modulate = Color(1, 1, 1, 0.3 * wf)
	# Leuchtfeuer: Seidenpapierkeil dreht sich um die senkrechte Achse
	var ang := TAU * (t / BEAM_T + BEAM_PHASE)
	var c := cos(ang)
	beam.scale = Vector2(c * 1.05, 1.0)
	beam.modulate = Color(1.0, 0.93, 0.7, 0.72 * clampf(absf(c) * 3.0, 0.0, 1.0))
	var flash := pow(maxf(sin(ang), 0.0), 10.0)
	lamp_flash.modulate = Color(1, 1, 1, 0.9 * flash)
	lamp_glow.modulate = Color(1, 1, 1, 0.55 + 0.35 * flash)
	# Wolken
	for cl in clouds:
		var cx: float = fmod(cl[1].x + cl[2] * t + 300.0, 1600.0) - 300.0
		_put(cl[0], Vector2(round(cx), cl[1].y))
	# Möwen
	for g in gulls:
		var u: float = fmod(t + g[9], g[8]) / g[8]
		var pos: Vector2 = (g[2] as Vector2).lerp(g[3], u) + Vector2(0, 4.0 * sin(t * 1.3 + g[5]))
		g[0].position = pos.round()
		g[0].scale = Vector2(-g[7] if g[6] else g[7], g[7])
		var flap := sin(TAU * g[4] * t + g[5])
		_put(g[1], _v(L["gull_body"]["wing_at"]) - _v(L["gull_body"]["pivot"]), -0.55 * flap - 0.15)
	# Meer
	for s in strips:
		var off: float = s[2] * sin(TAU * t / s[3] + s[4])
		var bob: float = round(1.2 * sin(TAU * t / (s[3] * 0.7) + s[4] * 1.3))
		_put(s[0], Vector2(round(-80.0 + off), s[1] + bob))
	for b in boats:
		var r := deg_to_rad(b[2]) * sin(TAU * t / b[3] + b[4])
		var y := 1.4 * sin(TAU * t / (b[3] * 1.1) + b[4] + 0.8)
		_put(b[0], b[1] + Vector2(0, y), r)
	# Rauch: alle 0,7 s ein Wölkchen, steigt, treibt nach links, wird größer und zum Schluss klein
	var ch := Vector2(L["chimney_top"][0], L["chimney_top"][1] + 6)
	for i in smokes.size():
		var age := fmod(t + 10.0 + i * 0.7, 3.5)
		var p := ch + Vector2(-16.0 * age - 2.0 * age * age, -24.0 * age - 2.5 * age * age)
		var sc := lerpf(0.45, 1.25, _ease(age / 2.8)) * (1.0 - _ease((age - 2.8) / 0.7))
		_put(smokes[i], p.round(), 0.35 * age + i, Vector2(sc, sc))
	if no_ui:
		return
	# Oberfläche: Ortsname klebt Buchstabe für Buchstabe, Zeile tippt, Parser tippt, Zettel 2 wird angehoben
	for sn in snips:
		var k := _ease((t - sn[3]) / 0.18)
		var lift := (1.0 - k) * 0.35
		var pr: Array = sn[0]
		pr[0].visible = t >= sn[3]
		pr[1].visible = pr[0].visible
		_put(pr, sn[1] + Vector2(0, -6.0 * (1.0 - k)), sn[2] * (1.0 + lift), Vector2.ONE * sn[4] * (1.0 + lift))
		pr[1].position = pr[0].position + Vector2(2.5, 3.5) * (1.0 + 4.0 * lift)
	ui_line.visible_characters = int(clampf((t - 0.5) * 30.0, 0.0, LINE.length()))
	var np := int(clampf((t - 3.2) * 9.0, 0.0, PARSER.length()))
	ui_parser.visible_characters = np
	var font := ui_parser.get_theme_font("font")
	var w := font.get_string_size(PARSER.substr(0, np), HORIZONTAL_ALIGNMENT_LEFT, -1, 20).x
	ui_cursor.position = ui_parser.position + Vector2(w + 2, 3)
	ui_cursor.visible = fmod(t, 0.8) < 0.5
	for i in slips.size():
		var sl: Array = slips[i]
		var up: float = _ease((t - 4.4) / 0.3) if i == 1 else 0.0
		_put(sl[0], sl[1] + Vector2(0, -4.0 * up), sl[2] * (1.0 - up) + deg_to_rad(-2.0) * up,
				Vector2.ONE * (1.0 + 0.04 * up))
		sl[0][1].position = sl[0][0].position + Vector2(2, 3) + Vector2(3, 5) * up

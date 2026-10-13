extends Node2D
# Art déco & Reiseplakat – Hafen von Lornholm.
# Ein KI-Plakat (gpt-image) als Welt in Bildpixeln (1536x1024); ein Shader legt Sonnenstrahlen, Leuchtfeuer in
# Stufen, Lichthöfe, Spiegelstriche und schaukelnde Boote darauf (shaders/scene.gdshader). In der Welt zeichnet
# Code Rauch, Möwen und vierzackige Sterne als Plakatformen. Der Dachs kommt aus einem KI-Laufbogen, der in
# 15 Plakatfarben getrennt ist (scripts/build_badger.py), und läuft nach art/timeline.json.
# Zwei feste Einstellungen: Totale (ganzes Plakat) bis Takt 90, dann Nahaufnahme 1,62-fach.
# Oberfläche: Titelband unten wie die Schriftzeile eines Reiseplakats (Federo, Josefin Sans).
# Zeit: Takte in _process gezählt (Movie Maker: feste 30 Bilder/s), alles ist eine Funktion des Takts.
#
# Prüfschalter nach -- :  --probe-badger  nur der Dachs vor flachem Blau (für scripts/probe_feet.py)
#                         --t0=<s>        Umgebung um <s> Sekunden vorstellen (Langzeitprüfung)
#                         --shot=<0|1>    eine Einstellung festhalten (Prüfbilder)

var tick := 0
var t0 := 0.0
var probe := false
var force_shot := -1

var scene_info := {}
var timeline := {}
var binfo := {}
var ui_text := {}

var world: Node2D
var bg: Sprite2D
var mat: ShaderMaterial
var fx: FxLayer
var badger: Sprite2D
var shadow: ShadowLayer
var tex_far: Texture2D
var tex_close: Texture2D
var ui: UiLayer
var flicker: PackedFloat32Array = PackedFloat32Array()
var cur_shot := -1


class FxLayer extends Node2D:
	# Rauch, Möwen und Sterne in Weltkoordinaten (Pixel des Plakats)
	var t := 0.0
	var chimney := Vector2(92, 236)
	const SMOKE_LIGHT := Color8(222, 178, 166)
	const SMOKE_SHADE := Color8(138, 108, 140)
	const GULL := Color8(240, 230, 210)
	const GULL_TIP := Color8(28, 32, 60)
	const STAR := Color8(250, 222, 150)
	const STARS := [Vector3(232, 82, 7.0), Vector3(640, 44, 9.0), Vector3(905, 112, 6.0), Vector3(1040, 34, 8.0),
			Vector3(1500, 170, 6.0), Vector3(392, 150, 5.0), Vector3(782, 172, 5.0)]

	func _draw() -> void:
		_draw_stars()
		_draw_smoke()
		# Möwen ziehen von rechts nach links und kommen nach dem linken Rand rechts wieder herein
		_draw_gull(Vector2(1600.0 - fposmod(420.0 + 34.0 * t, 1700.0), 238.0 + 6.0 * sin(t * 1.3)), 30.0, t * 9.0, 0.0)
		_draw_gull(Vector2(1600.0 - fposmod(590.0 + 52.0 * t, 1700.0), 432.0 + 5.0 * sin(t * 1.1 + 1.0)), 40.0, t * 8.0 + 1.5, 0.35)

	func _draw_stars() -> void:
		var i := 0
		for s in STARS:
			var k := 0.75 + 0.35 * sin(t * (1.7 + 0.37 * i) + 1.9 * i)
			var r: float = s.z * k
			var c := Vector2(s.x, s.y)
			var pts := PackedVector2Array()
			for j in 8:
				var a := PI * 0.25 * j
				var rr := r if j % 2 == 0 else r * 0.22
				pts.append(c + Vector2(sin(a), -cos(a)) * rr)
			draw_colored_polygon(pts, STAR)
			i += 1

	func _draw_smoke() -> void:
		# alle 0,5 s ein Ballen; steigt, treibt nach rechts und zieht sich dabei zu einer liegenden
		# Stromlinien-Ellipse auseinander (wie die Wolkenbänder des Plakats); schrumpft am Ende, keine Transparenz
		var period := 0.5
		var life := 3.6
		var n := int(ceil(life / period)) + 1
		var newest := floorf(t / period)
		for k in range(n - 1, -1, -1):
			var born := (newest - k) * period
			var age := t - born
			if age < 0.0 or age > life:
				continue
			var u := age / life
			var pos := chimney + Vector2(10.0 * age + 9.0 * age * age, -3.0 - 34.0 * age + 3.6 * age * age)
			var r := (6.0 + 12.0 * u) * (1.0 - smoothstep(0.75, 1.0, u))
			if r < 0.6:
				continue
			var stretch := 1.0 + 1.6 * u
			var squash := 1.0 - 0.38 * u
			_ellipse(pos, Vector2(r * stretch, r * squash), SMOKE_SHADE)
			_ellipse(pos + Vector2(r * stretch * 0.16, -r * squash * 0.22), Vector2(r * stretch * 0.82, r * squash * 0.74), SMOKE_LIGHT)

	func _ellipse(c: Vector2, rad: Vector2, col: Color) -> void:
		var pts := PackedVector2Array()
		for i in 36:
			var a := TAU * i / 36.0
			pts.append(c + Vector2(cos(a) * rad.x, sin(a) * rad.y))
		draw_colored_polygon(pts, col)
		draw_polyline(pts + PackedVector2Array([pts[0]]), col, 1.0, true)

	func _draw_gull(c: Vector2, span: float, ph: float, glide: float) -> void:
		# Möwe als Plakatform: zwei geschwungene Flügel, dunkle Spitzen; Flügelschlag mit Gleitphasen
		var flap := sin(ph)
		if fmod(ph, TAU * 3.0) > TAU * 2.0:
			flap = 0.25 + glide * 0.2   # gleiten
		var tip_y := -span * 0.22 * flap
		var s := span * 0.5
		for side in [-1.0, 1.0]:
			var pts := PackedVector2Array([
				c + Vector2(0.0, 0.0),
				c + Vector2(side * s * 0.30, -s * 0.16 + tip_y * 0.35),
				c + Vector2(side * s * 1.00, tip_y),
				c + Vector2(side * s * 0.55, tip_y * 0.55 + s * 0.02),
				c + Vector2(side * s * 0.22, s * 0.10)])
			draw_colored_polygon(pts, GULL)
			var tip := PackedVector2Array([
				c + Vector2(side * s * 1.00, tip_y),
				c + Vector2(side * s * 0.78, tip_y * 0.85 - s * 0.03),
				c + Vector2(side * s * 0.80, tip_y * 0.80 + s * 0.06)])
			draw_colored_polygon(tip, GULL_TIP)
		draw_circle(c + Vector2(0.0, s * 0.05), s * 0.13, GULL, true, -1.0, true)


class ShadowLayer extends Node2D:
	# flacher Schlagschatten unter dem Dachs (Bildschirmkoordinaten)
	var centre := Vector2.ZERO
	var radius := Vector2(30, 5)

	func _draw() -> void:
		var pts := PackedVector2Array()
		for i in 40:
			var a := TAU * i / 40.0
			pts.append(centre + Vector2(cos(a) * radius.x, sin(a) * radius.y))
		draw_colored_polygon(pts, Color(0.07, 0.08, 0.17, 0.42))


class UiLayer extends Node2D:
	# Titelband unten: Ortsname, Erzählzeile, Auswahl und Eingabe im Stil einer Plakat-Schriftzeile
	var t := 0.0
	var text := {}
	var f_title: FontVariation
	var f_text: FontVariation
	var f_bold: FontVariation
	var f_num: FontVariation
	const NAVY := Color8(20, 24, 48)
	const NAVY_2 := Color8(34, 40, 76)
	const GOLD := Color8(222, 176, 92)
	const GOLD_DARK := Color8(150, 112, 56)
	const GOLD_LIGHT := Color8(248, 218, 150)
	const CREAM := Color8(244, 230, 204)
	const CORAL := Color8(240, 146, 96)
	const Y := 628.0

	func _draw() -> void:
		var w := 1280.0
		# Band mit Stufenaufsatz in der Mitte (Zikkurat), zwei Goldlinien folgen der Kante
		var step := PackedVector2Array([
			Vector2(0, Y), Vector2(552, Y), Vector2(552, Y - 7), Vector2(574, Y - 7), Vector2(574, Y - 14),
			Vector2(706, Y - 14), Vector2(706, Y - 7), Vector2(728, Y - 7), Vector2(728, Y), Vector2(w, Y),
			Vector2(w, 720), Vector2(0, 720)])
		draw_colored_polygon(step, Color(NAVY, 0.95))
		var edge := PackedVector2Array()
		for i in 10:
			edge.append(step[i])
		draw_polyline(edge, GOLD, 2.0)
		var inner := PackedVector2Array()
		for p in edge:
			inner.append(p + Vector2(0, 5))
		draw_polyline(inner, GOLD_DARK, 1.0)
		# Sonnenfächer im Aufsatz
		var fc := Vector2(640, Y + 2)
		for i in 11:
			var a := PI + PI * (i + 0.5) / 11.0
			var a0 := a - 0.055
			var a1 := a + 0.055
			var ln := 13.0 if i % 2 == 0 else 9.0
			var fan := PackedVector2Array([fc, fc + Vector2(cos(a0), sin(a0)) * ln, fc + Vector2(cos(a1), sin(a1)) * ln])
			draw_colored_polygon(fan, GOLD)
		draw_circle(fc, 3.5, GOLD_LIGHT, true, -1.0, true)
		# Abschlusslinie unten
		draw_rect(Rect2(0, 716, w, 1), GOLD_DARK)

		# linke Spalte: Ortsname und Eingabezeile
		var loc := String(text.get("location", "")).to_upper()
		draw_string(f_title, Vector2(28, Y + 36), loc, HORIZONTAL_ALIGNMENT_LEFT, -1, 25, GOLD_LIGHT)
		var prompt := String(text.get("parser_prompt", ""))
		draw_string(f_text, Vector2(30, Y + 74), prompt, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color(CREAM, 0.88))
		var pw := f_text.get_string_size(prompt, HORIZONTAL_ALIGNMENT_LEFT, -1, 20).x
		if fmod(t, 1.0) < 0.55:
			draw_rect(Rect2(34 + pw, Y + 58, 10, 19), GOLD)

		# Trenner: Goldlinie mit Raute
		var dx := 432.0
		draw_rect(Rect2(dx, Y + 16, 2, 64), GOLD_DARK)
		_diamond(Vector2(dx + 1, Y + 48), 6.0, GOLD)

		# rechte Spalte: Erzählzeile und Auswahl
		draw_string(f_bold, Vector2(dx + 26, Y + 36), String(text.get("line", "")), HORIZONTAL_ALIGNMENT_LEFT, -1, 21, CREAM)
		var x := dx + 26.0
		var choices: Array = text.get("choices", [])
		for i in choices.size():
			var sel := i == 1
			var c := CORAL if sel else Color(CREAM, 0.9)
			_diamond(Vector2(x + 9, Y + 67), 10.0, GOLD if not sel else CORAL)
			draw_string(f_num, Vector2(x + 4.5, Y + 72.5), str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, NAVY)
			var s := String(choices[i])
			draw_string(f_text, Vector2(x + 26, Y + 74), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, c)
			var sw := f_text.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 20).x
			if sel:
				draw_rect(Rect2(x + 26, Y + 79, sw, 2), CORAL)
			x += 26.0 + sw + 34.0

	func _diamond(c: Vector2, r: float, col: Color) -> void:
		draw_colored_polygon(PackedVector2Array([c + Vector2(0, -r), c + Vector2(r, 0), c + Vector2(0, r), c + Vector2(-r, 0)]), col)


func _load_json(path: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--probe-badger":
			probe = true
		elif a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--shot="):
			force_shot = int(a.substr(7))
	scene_info = _load_json("res://art/scene.json")
	timeline = _load_json("res://art/timeline.json")
	binfo = _load_json("res://art/badger.json")
	ui_text = _load_json("res://art/ui_text.json")
	var rng := RandomNumberGenerator.new()
	rng.seed = 19301012
	for i in 400:
		flicker.append(rng.randf())

	world = Node2D.new()
	add_child(world)
	bg = Sprite2D.new()
	bg.centered = false
	bg.texture = load("res://art/bg.png")
	mat = ShaderMaterial.new()
	mat.shader = load("res://shaders/scene.gdshader")
	mat.set_shader_parameter("mask", load("res://art/mask.png"))
	mat.set_shader_parameter("plate", load("res://art/plate.png"))
	var sun: Dictionary = scene_info["sun"]
	mat.set_shader_parameter("sun_c", Vector2(sun["centre"][0], sun["centre"][1]))
	mat.set_shader_parameter("horizon_y", float(scene_info["horizon_y"]))
	mat.set_shader_parameter("quay_y", float(scene_info["quay_back_y"]))
	mat.set_shader_parameter("lamp", Vector2(scene_info["lamp"][0], scene_info["lamp"][1]))
	mat.set_shader_parameter("lantern", Vector2(scene_info["lantern"][0], scene_info["lantern"][1]))
	bg.material = mat
	world.add_child(bg)
	fx = FxLayer.new()
	fx.chimney = Vector2(scene_info["chimney_top"][0], scene_info["chimney_top"][1])
	world.add_child(fx)

	shadow = ShadowLayer.new()
	add_child(shadow)
	badger = Sprite2D.new()
	badger.centered = false
	tex_far = load("res://art/badger_far.png")
	tex_close = load("res://art/badger_close.png")
	badger.hframes = int(binfo["frames"])
	add_child(badger)

	var layer := CanvasLayer.new()
	layer.layer = 5
	add_child(layer)
	ui = UiLayer.new()
	ui.text = ui_text
	var ts := TextServerManager.get_primary_interface()
	var federo: FontFile = load("res://fonts/Federo-Regular.ttf")
	var josefin: FontFile = load("res://fonts/JosefinSans-wght.ttf")
	ui.f_title = FontVariation.new()
	ui.f_title.base_font = federo
	ui.f_title.spacing_glyph = 3
	ui.f_num = FontVariation.new()
	ui.f_num.base_font = federo
	ui.f_text = FontVariation.new()
	ui.f_text.base_font = josefin
	ui.f_text.variation_opentype = {ts.name_to_tag("wght"): 500}
	ui.f_bold = FontVariation.new()
	ui.f_bold.base_font = josefin
	ui.f_bold.variation_opentype = {ts.name_to_tag("wght"): 600}
	layer.add_child(ui)

	if probe:
		world.visible = false
		shadow.visible = false
		ui.visible = false
		RenderingServer.set_default_clear_color(Color(0.1, 0.3, 0.9))
	_apply(0)


func _process(_delta: float) -> void:
	tick += 1
	_apply(tick)


func _apply(tk: int) -> void:
	var ticks: Array = timeline["ticks"]
	var e: Dictionary = ticks[min(tk, ticks.size() - 1)]
	var shot := int(e["s"]) if force_shot < 0 else force_shot
	var sh: Dictionary = timeline["shots"][shot]
	var z := float(sh["zoom"])
	var o := Vector2(sh["origin"][0], sh["origin"][1])
	if shot != cur_shot:
		cur_shot = shot
		world.scale = Vector2(z, z)
		world.position = -o * z
		badger.texture = tex_far if shot == 0 else tex_close
	var key := "_far" if shot == 0 else "_close"
	var bx := float(e["x"])
	var by := float(e["y"])
	if force_shot >= 0 and force_shot != int(e["s"]):
		bx = roundf((float(e["wx"]) - o.x) * z)
		by = roundf((float(timeline["foot_y"]) - o.y) * z - float(binfo["sole_y" + key]))
	badger.frame = int(e["f"])
	badger.position = Vector2(bx, by)
	var ppa := float(binfo["px_per_ai" + key])
	var m: Dictionary = binfo["measure"][int(e["f"])]
	shadow.centre = Vector2(bx + float(m["cx_ai"]) * ppa, by + float(binfo["sole_y" + key]) + 1.0)
	shadow.radius = Vector2(46.0 * ppa / 0.42, 7.0 * ppa / 0.42)
	shadow.queue_redraw()

	var t := tk / 30.0 + t0
	# Sonnenstrahlen drehen langsam, Helligkeit atmet
	mat.set_shader_parameter("t", t)
	mat.set_shader_parameter("ray_rot", t * 0.035)
	mat.set_shader_parameter("ray_gain", 0.9 + 0.12 * sin(t * 0.9))
	# Leuchtfeuer: eine Umdrehung in 6 s; sichtbare Länge = Projektion, Aufblitzen zur Kamera (t = 1 s),
	# lang nach links bei t = 2,5 s
	var ph := PI / 6.0 + TAU * t / 6.0
	var cs := cos(ph)
	mat.set_shader_parameter("beam_dir", -1.0 if cs < 0.0 else 1.0)
	mat.set_shader_parameter("beam_len", 760.0 * abs(cs))
	var toward: float = max(0.0, sin(ph))
	mat.set_shader_parameter("lamp_gain", 1.15 + 0.7 * pow(toward, 6.0) - 0.15 * pow(max(0.0, -sin(ph)), 2.0))
	mat.set_shader_parameter("lamp_flash", pow(toward, 10.0))
	# Laterne flackert (Rauschen mit festem Seed, 15 Werte je Sekunde, weich überblendet)
	var fi := t * 15.0
	var i0 := int(floorf(fi)) % flicker.size()
	var i1 := (i0 + 1) % flicker.size()
	var fl := lerpf(flicker[i0], flicker[i1], fi - floorf(fi))
	mat.set_shader_parameter("lantern_gain", 1.08 + 0.22 * fl)
	mat.set_shader_parameter("window_gain", 1.04 + 0.05 * sin(t * 2.3) + 0.03 * flicker[(i0 + 7) % flicker.size()])
	# Boote schaukeln um ganze Pixel
	mat.set_shader_parameter("bob_a", roundf(1.6 * sin(t * 1.7)))
	mat.set_shader_parameter("bob_b", roundf(1.6 * sin(t * 1.35 + 1.3)))
	mat.set_shader_parameter("glint_step", floorf(t * 6.0))
	fx.t = t
	fx.queue_redraw()
	ui.t = tk / 30.0
	ui.queue_redraw()

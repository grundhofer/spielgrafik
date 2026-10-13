extends Node2D
# Jugendstil – Hafen von Lornholm.
# Ein KI-Plakat (gpt-image) als Welt in Bildpixeln (bg.png, 1536x1064) hinter einem KI-Ornamentrahmen mit
# Rundbogenfenster (frame.png, 1280x720, Fenster durchsichtig). Der Szenen-Shader (shaders/scene.gdshader) lässt
# die Wellenornamente fließen, das Gold auf dem Wasser schimmern, einen Nimbus um das Leuchtfeuer pulsieren,
# die Laterne flackern und die Sterne (eigene Sternmaske) funkeln; der Rauch ist ein Ornamentband (Line2D + shaders/smoke.gdshader),
# das Gold des Rahmens schimmert (shaders/frame.gdshader). Der Dachs kommt aus einem KI-Laufbogen, der in
# flache Druckfarben getrennt und mit gleich starker Kontur nachgezogen ist (scripts/build_badger.py), und läuft
# nach art/timeline.json. Zwei feste Einstellungen im selben Rahmen: Totale bis Takt 90, dann Nahaufnahme 1:1.
# Oberfläche: Text im cremefarbenen Textfeld des Rahmens (Della Respira, Amarante).
# Zeit: Takte in _process gezählt (Movie Maker: feste 30 Bilder/s), alles ist eine Funktion des Takts.
#
# Prüfschalter nach -- :  --probe-badger  nur der Dachs vor flachem Blau (für scripts/probe_feet.py)
#                         --t0=<s>        Umgebung um <s> Sekunden vorstellen (Langzeitprüfung)
#                         --shot=<0|1>    eine Einstellung festhalten (Prüfbilder)
#                         --no-waves      Wellen stehen (Vergleich für den Anteil geänderter Pixel)

var tick := 0
var t0 := 0.0
var probe := false
var force_shot := -1
var no_waves := false

var scene_info := {}
var layout := {}
var timeline := {}
var binfo := {}
var ui_text := {}
var frame_info := {}

var world: Node2D
var bg: Sprite2D
var tex_bg_far: Texture2D
var tex_bg_close: Texture2D
var mat: ShaderMaterial
var smoke: Line2D
var smoke_mat: ShaderMaterial
var badger: Sprite2D
var shadow: ShadowLayer
var tex_far: Texture2D
var tex_close: Texture2D
var frame: Sprite2D
var frame_mat: ShaderMaterial
var ui: UiLayer
var flicker: PackedFloat32Array = PackedFloat32Array()
var cur_shot := -1
var chimney := Vector2.ZERO
const SMOKE_R0 := 40.0       # Außenradius der Rauchspirale (Weltpixel)
const SMOKE_R1 := 8.0        # Innenradius am Ende (größer als die halbe Bandbreite dort)
const SMOKE_TURNS := 1.4     # Windungen


class ShadowLayer extends Node2D:
	# flacher Schlagschatten unter dem Dachs (Bildschirmkoordinaten), Konturfarbe halbdurchsichtig
	var centre := Vector2.ZERO
	var radius := Vector2(30, 5)

	func _draw() -> void:
		var pts := PackedVector2Array()
		for i in 40:
			var a := TAU * i / 40.0
			pts.append(centre + Vector2(cos(a) * radius.x, sin(a) * radius.y))
		draw_colored_polygon(pts, Color(0.13, 0.12, 0.05, 0.38))


class UiLayer extends Node2D:
	# Text im Textfeld des Rahmens: Ortsname (Della Respira, Terrakotta), Erzählzeile (Amarante), Auswahl mit
	# Goldpunkten wie im Rahmen, Eingabezeile mit blinkendem Goldbalken
	var t := 0.0
	var text := {}
	var panel := {}
	var f_title: FontVariation
	var f_text: Font
	const KEY := Color8(33, 31, 14)
	const PETROL := Color8(23, 60, 61)
	const TERRA := Color8(154, 66, 42)
	const GOLD := Color8(214, 160, 66)
	const GOLD_PALE := Color8(246, 214, 140)
	const SAGE := Color8(96, 112, 78)

	func _draw() -> void:
		var x0 := float(panel["x0"]) + 20.0
		var x1 := float(panel["x1"]) - 20.0
		var y0 := float(panel["y0"])
		# Zeile 1: Ortsname, Blattornament, Erzählzeile
		var loc := String(text.get("location", ""))
		var b1 := y0 + 28.0
		draw_string(f_title, Vector2(x0, b1), loc, HORIZONTAL_ALIGNMENT_LEFT, -1, 24, TERRA)
		var lw := f_title.get_string_size(loc, HORIZONTAL_ALIGNMENT_LEFT, -1, 24).x
		var lx := x0 + lw + 22.0
		_leaf(Vector2(lx, b1 - 8.0), 9.0)
		draw_string(f_text, Vector2(lx + 22.0, b1), String(text.get("line", "")), HORIZONTAL_ALIGNMENT_LEFT, -1, 20, KEY)
		# Trennlinie: dünne Goldlinie mit Kontur
		var ly := y0 + 39.0
		draw_line(Vector2(x0, ly), Vector2(x1, ly), Color(GOLD, 0.85), 1.0)
		# Zeile 2: Auswahl mit nummerierten Goldpunkten
		var b2 := y0 + 63.0
		var x := x0
		var choices: Array = text.get("choices", [])
		for i in choices.size():
			var sel := i == 1
			var c := Vector2(x + 9.0, b2 - 6.5)
			draw_circle(c, 9.5, KEY, true, -1.0, true)
			draw_circle(c, 8.0, TERRA if sel else GOLD, true, -1.0, true)
			var num := str(i + 1)
			var nw := f_text.get_string_size(num, HORIZONTAL_ALIGNMENT_LEFT, -1, 14).x
			draw_string(f_text, Vector2(c.x - nw * 0.5, b2 - 1.5), num, HORIZONTAL_ALIGNMENT_LEFT, -1, 14,
					GOLD_PALE if sel else KEY)
			var s := String(choices[i])
			var col := TERRA if sel else PETROL
			draw_string(f_text, Vector2(x + 25.0, b2), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 19, col)
			var sw := f_text.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x
			if sel:
				_whiplash(Vector2(x + 25.0, b2 + 4.0), sw, TERRA)
			x += 25.0 + sw + 30.0
		# Eingabezeile rechts
		var prompt := String(text.get("parser_prompt", ""))
		var pw := f_text.get_string_size(prompt, HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x
		var px := x1 - pw - 14.0
		draw_string(f_text, Vector2(px, b2), prompt, HORIZONTAL_ALIGNMENT_LEFT, -1, 19, KEY)
		if fmod(t, 1.0) < 0.55:
			draw_rect(Rect2(px + pw + 4.0, b2 - 15.0, 8.0, 18.0), KEY)
			draw_rect(Rect2(px + pw + 5.0, b2 - 14.0, 6.0, 16.0), GOLD)

	func _leaf(c: Vector2, r: float) -> void:
		# herzförmiges Blatt wie im Rahmen, Gold mit Kontur
		var pts := PackedVector2Array()
		for i in 33:
			var a := PI * 2.0 * i / 32.0
			var x := 16.0 * pow(sin(a), 3.0)
			var y := -(13.0 * cos(a) - 5.0 * cos(2.0 * a) - 2.0 * cos(3.0 * a) - cos(4.0 * a))
			pts.append(c + Vector2(x, y) * (r / 16.0))
		draw_colored_polygon(pts, GOLD)
		draw_polyline(pts, KEY, 1.6, true)

	func _whiplash(p: Vector2, w: float, col: Color) -> void:
		# Unterstreichung als flacher Peitschenhieb: Sinusschwung, der 7 px vor dem Wortende in einen kleinen
		# Kringel nach unten ausläuft (ein Kringel nach oben direkt hinter dem Wort las sich als Komma)
		var pts := PackedVector2Array()
		var we := w - 7.0
		for i in 41:
			var u := i / 40.0
			pts.append(p + Vector2(u * we, 1.6 * sin(u * PI * 2.0)))
		for i in 1 + 14:
			var a := -PI * 0.5 + i / 14.0 * PI * 1.5
			pts.append(p + Vector2(we, 3.4) + Vector2(cos(a), sin(a)) * (3.4 - i * 0.1))
		draw_polyline(pts, col, 1.6, true)


func _load_json(path: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--probe-badger":
			probe = true
		elif a == "--no-waves":
			no_waves = true
		elif a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--shot="):
			force_shot = int(a.substr(7))
	scene_info = _load_json("res://art/scene.json")
	layout = _load_json("res://art/layout.json")
	timeline = _load_json("res://art/timeline.json")
	binfo = _load_json("res://art/badger.json")
	ui_text = _load_json("res://art/ui_text.json")
	frame_info = _load_json("res://art/frame.json")
	var rng := RandomNumberGenerator.new()
	rng.seed = 19001012
	for i in 400:
		flicker.append(rng.randf())

	world = Node2D.new()
	add_child(world)
	bg = Sprite2D.new()
	bg.centered = false
	tex_bg_far = load("res://art/bg_far.png")
	tex_bg_close = load("res://art/bg.png")
	mat = ShaderMaterial.new()
	mat.shader = load("res://shaders/scene.gdshader")
	mat.set_shader_parameter("mask", load("res://art/mask.png"))
	mat.set_shader_parameter("stars", load("res://art/stars.png"))
	var size: Array = scene_info["size"]
	mat.set_shader_parameter("world_size", Vector2(size[0], size[1]))
	mat.set_shader_parameter("horizon_y", float(scene_info["horizon_y"]))
	mat.set_shader_parameter("quay_y", float(scene_info["quay_back_y"]))
	var lights: Dictionary = scene_info["lights"]
	mat.set_shader_parameter("lamp", Vector2(lights["lamp"]["centre"][0], lights["lamp"]["centre"][1]))
	mat.set_shader_parameter("lantern", Vector2(lights["lantern"]["centre"][0], lights["lantern"]["centre"][1]))
	mat.set_shader_parameter("wave_gain", 0.0 if no_waves else 1.0)
	bg.material = mat
	world.add_child(bg)

	chimney = Vector2(scene_info["chimney_top"][0], scene_info["chimney_top"][1])
	smoke = Line2D.new()
	smoke.width = 36.0
	var wc := Curve.new()
	# Breite über die Länge (Peitschenhieb ~ erste Hälfte, Spirale zweite Hälfte): kräftig am Schornstein,
	# dünner zur Spirale, spitz am Ende
	wc.add_point(Vector2(0.0, 0.5))
	wc.add_point(Vector2(0.2, 0.9))
	wc.add_point(Vector2(0.5, 0.68))
	wc.add_point(Vector2(0.75, 0.42))
	wc.add_point(Vector2(0.92, 0.2))
	wc.add_point(Vector2(1.0, 0.04))
	smoke.width_curve = wc
	var white := Image.create(2, 2, false, Image.FORMAT_RGBA8)
	white.fill(Color.WHITE)
	smoke.texture = ImageTexture.create_from_image(white)
	smoke.texture_mode = Line2D.LINE_TEXTURE_STRETCH
	smoke.joint_mode = Line2D.LINE_JOINT_ROUND
	smoke.antialiased = false            # Kantenglättung im Shader (Alpha über den Abstand zum Bandrand)
	smoke_mat = ShaderMaterial.new()
	smoke_mat.shader = load("res://shaders/smoke.gdshader")
	smoke.material = smoke_mat
	world.add_child(smoke)

	shadow = ShadowLayer.new()
	add_child(shadow)
	badger = Sprite2D.new()
	badger.centered = false
	tex_far = load("res://art/badger_far.png")
	tex_close = load("res://art/badger_close.png")
	badger.hframes = int(binfo["frames"])
	add_child(badger)

	frame = Sprite2D.new()
	frame.centered = false
	frame.texture = load("res://art/frame.png")
	frame_mat = ShaderMaterial.new()
	frame_mat.shader = load("res://shaders/frame.gdshader")
	frame_mat.set_shader_parameter("gold_mask", load("res://art/frame_gold.png"))
	frame.material = frame_mat
	add_child(frame)

	ui = UiLayer.new()
	ui.text = ui_text
	ui.panel = frame_info["panel"]
	ui.f_title = FontVariation.new()
	ui.f_title.base_font = load("res://fonts/DellaRespira-Regular.ttf")
	ui.f_title.variation_embolden = 0.45
	ui.f_title.spacing_glyph = 1
	ui.f_text = load("res://fonts/Amarante-Regular.ttf")
	add_child(ui)

	if probe:
		world.visible = false
		shadow.visible = false
		frame.visible = false
		ui.visible = false
		RenderingServer.set_default_clear_color(Color(0.1, 0.3, 0.9))
	_apply(0)


func _process(_delta: float) -> void:
	tick += 1
	_apply(tick)


func _bez(p0: Vector2, p1: Vector2, p2: Vector2, p3: Vector2, u: float) -> Vector2:
	var v := 1.0 - u
	return p0 * v * v * v + p1 * 3.0 * v * v * u + p2 * 3.0 * v * u * u + p3 * u * u * u


func _smoke_points(t: float) -> PackedVector2Array:
	# Ornamentband wie die Wolkenranken des Plakats: Peitschenhieb vom Schornstein nach rechts, am Ende eine
	# Spirale mit anderthalb Windungen, die über oben nach innen einrollt und spitz ausläuft. Die Breite fällt über
	# die Länge (smoke.width_curve); der Radius bleibt überall größer als die halbe Bandbreite, und eine Windung
	# rückt um mehr als die Bandbreite nach innen (sonst berühren sich die Windungen). Auf dem Peitschenhieb läuft
	# eine Welle vom festen Fuß zur Spirale; die Spirale atmet leicht.
	# Der Bogen des Rahmens liegt über dem Schornstein nur ~13 Weltpixel höher und steigt nach rechts steil an
	# (Welt-x 200: Zeile 82, x 300: Zeile 48, x 340: Zeile 37): das Band zieht deshalb flach nach rechts, unter
	# dem großen Stern bei (204, 119) durch, und rollt erst dort ein, wo der Bogen genug Platz lässt.
	var c := chimney + Vector2(0.0, 2.0)
	var p0 := c
	var p1 := c + Vector2(8.0, -26.0)
	var p2 := c + Vector2(125.0, 30.0)
	var p3 := c + Vector2(235.0, -4.0)
	var pts := PackedVector2Array()
	var n := 40
	for i in n:
		pts.append(_bez(p0, p1, p2, p3, float(i) / n))
	var dir := (p3 - p2).normalized()
	var th0 := atan2(dir.x, -dir.y)              # Eintritt tangential, Drehsinn über oben nach innen
	var r0 := SMOKE_R0 + 1.5 * sin(t * 1.1)
	var cs := p3 - Vector2(cos(th0), sin(th0)) * r0
	var m := 72
	for i in m + 1:
		var f := float(i) / m
		var a := th0 - f * SMOKE_TURNS * TAU
		pts.append(cs + Vector2(cos(a), sin(a)) * lerpf(r0, SMOKE_R1, f))
	var out := PackedVector2Array()
	var total := pts.size()
	for i in total:
		var u := float(i) / (total - 1)
		var d := (pts[min(i + 1, total - 1)] - pts[max(i - 1, 0)]).normalized()
		var nn := Vector2(-d.y, d.x)
		var env := smoothstep(0.0, 0.12, u) * (1.0 - smoothstep(0.3, 0.42, u))
		out.append(pts[i] + nn * 4.0 * env * sin(TAU * (2.2 * u - 0.45 * t)))
	return out


func _apply(tk: int) -> void:
	var ticks: Array = timeline["ticks"]
	var e: Dictionary = ticks[min(tk, ticks.size() - 1)]
	var shot := int(e["s"]) if force_shot < 0 else force_shot
	var sh: Dictionary = layout["shots"][shot]
	var z := float(sh["zoom"])
	var pos := Vector2(sh["pos"][0], sh["pos"][1])
	if shot != cur_shot:
		cur_shot = shot
		world.scale = Vector2(z, z)
		world.position = pos
		var tex := tex_bg_far if shot == 0 else tex_bg_close
		bg.texture = tex
		bg.scale = Vector2.ONE * (float(scene_info["size"][0]) / tex.get_width())
		badger.texture = tex_far if shot == 0 else tex_close
		smoke_mat.set_shader_parameter("line_px", 2.0 if shot == 0 else 3.2)
	var key := "far" if shot == 0 else "close"
	var bx := float(e["x"])
	var by := float(e["y"])
	if force_shot >= 0 and force_shot != int(e["s"]):
		bx = roundf(pos.x + float(e["wx"]) * z)
		by = roundf(pos.y + float(timeline["foot_y"]) * z - float(binfo["sole_y_" + key]))
	badger.frame = int(e["f"])
	badger.position = Vector2(bx, by)
	var ppa := float(binfo["px_per_ai_" + key])
	var m: Dictionary = binfo["measure"][int(e["f"])]
	shadow.centre = Vector2(bx + float(m["cx_ai"]) * ppa, by + float(binfo["sole_y_" + key]) + 1.0)
	shadow.radius = Vector2(70.0 * ppa, 10.0 * ppa)
	shadow.queue_redraw()

	var t := tk / 30.0 + t0
	mat.set_shader_parameter("t", t)
	# Leuchtfeuer: alle 2,6 s ein Aufleuchten (bei t = 1,8 s und 4,4 s), danach läuft eine Lichtwelle durch die
	# Ringe nach außen (in der Totale um t = 2,5 s mitten im Kranz)
	var ph := fmod(t + 0.8, 2.6)
	mat.set_shader_parameter("pulse_front", -12.0 + ph * 115.0)
	mat.set_shader_parameter("lamp_gain", 1.0 + 0.55 * exp(-pow(ph / 0.35, 2.0)))
	# Laterne flackert (Rauschen mit festem Seed, 15 Werte je Sekunde, weich überblendet)
	var fi := t * 15.0
	var i0 := int(floorf(fi)) % flicker.size()
	var i1 := (i0 + 1) % flicker.size()
	var fl := lerpf(flicker[i0], flicker[i1], fi - floorf(fi))
	mat.set_shader_parameter("lantern_gain", 1.05 + 0.28 * fl)
	mat.set_shader_parameter("window_gain", 1.03 + 0.05 * sin(t * 2.3) + 0.04 * flicker[(i0 + 7) % flicker.size()])
	smoke.points = _smoke_points(t)
	smoke_mat.set_shader_parameter("t", t)
	frame_mat.set_shader_parameter("t", t)
	ui.t = tk / 30.0
	ui.queue_redraw()

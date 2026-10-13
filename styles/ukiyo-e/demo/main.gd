extends Node2D
# Ukiyo-e – Hafen von Lornholm. Ein Farbholzschnitt (KI-Bild) mit Brandung aus KI-Wellen, die wie Wellenbretter
# einer Bühne kreisen, Gischttropfen, wiegenden Wellenlinien im Hafen, blitzendem Leuchtfeuer, flackernder Laterne
# und Rauch. Text als Gedichtzettel im Himmel (Ortsname als Kopfzeile), daneben eine Kartusche ohne Schrift.
# Washi-Papier liegt multiplikativ über allem. Zeit: Takte in _process gezählt (Movie Maker: feste 30 Bilder/s),
# alles ist eine Funktion der Zeit.
#
# Zwei feste Einstellungen (art/scene.json "closeup"): Totale bis Takt 90, dann Nahaufnahme (Druckausschnitt ab
# view, 1,6-fach). Die Nahaufnahme zeichnet nichts hochskaliert: Druckbild, Wellen, Gischt und Dachs haben eigene
# Bilder in Zielgröße (bg_close, wave_*_close, spray_close, badger_close); Lagen werden aus Totale-Koordinaten
# umgerechnet und auf ganze Pixel gerundet.
#
# Prüfschalter nach -- :  --probe-badger  nur der Dachs vor flachem Blau (für scripts/probe_feet.py)
#                         --t0=<s>        Umgebung um <s> Sekunden vorstellen (Langzeitprüfung)

const PRINT_ORIGIN := Vector2(8, 8)
const PRINT_SIZE := Vector2(1264, 704)
const PAPER := Color(0.945, 0.918, 0.851)
const SLIP_PAPER := Color(0.957, 0.929, 0.859)
const SUMI := Color(0.137, 0.118, 0.137)
const VERMILION := Color(0.741, 0.231, 0.180)
const PRUSSIAN := Color(0.110, 0.231, 0.463)
const INDIGO := Color(0.149, 0.173, 0.361)

var tick := 0
var t0 := 0.0
var probe := false
var shot := 0
var zoom := 1.6
var view := Vector2.ZERO
var cut_tick := 90

var scene_info := {}
var timeline := {}
var lights := {}
var bg: Sprite2D
var bg_close: Sprite2D
var badger: Sprite2D
var badger_tex: Array = []
var lamp_fx: Sprite2D
var lamp_tex: Array = []
var lantern_fx: Sprite2D
var lantern_tex: Array = []
var smoke: Sprite2D
var waves_back: Array = []
var waves_front: Array = []
var wave_tex: Array = []          # [klein, nah] je Wellenform
var spray: Node2D
var spray_tex: Array = []         # als Feld halten: ein nur in _draw geladenes Bild wird vor dem Zeichnen freigegeben
var cursor: ColorRect
var flicker: PackedFloat32Array = PackedFloat32Array()
var spray_rnd: PackedFloat32Array = PackedFloat32Array()


func _load_json(path: String) -> Variant:
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--probe-badger":
			probe = true
		elif a.begins_with("--t0="):
			t0 = float(a.substr(5))
	scene_info = _load_json("res://art/scene.json")
	timeline = _load_json("res://art/timeline.json")
	lights = _load_json("res://art/lights.json")
	var cu: Dictionary = scene_info["closeup"]
	zoom = float(cu["zoom"])
	view = Vector2(cu["view"][0], cu["view"][1])
	cut_tick = int(cu["from_tick"])

	var rng := RandomNumberGenerator.new()
	rng.seed = 18571012
	for i in 600:
		flicker.append(rng.randf())
	for i in 4000:
		spray_rnd.append(rng.randf())

	_build_print()
	_build_lights()
	_build_smoke()
	_build_badger()
	_build_waves()
	_build_frame()
	_build_ui()
	_build_paper()
	if probe:
		RenderingServer.set_default_clear_color(Color(0.16, 0.33, 0.6))
		for c in get_children():
			c.visible = (c == badger)
	_update()


# ---------------------------------------------------------------- Einstellungen

func _xf(p: Vector2) -> Vector2:
	# Totale-Bildschirmkoordinate -> Bildschirmkoordinate der aktuellen Einstellung
	if shot == 0:
		return p
	return PRINT_ORIGIN + zoom * (p - PRINT_ORIGIN - view)


# ---------------------------------------------------------------- Bildaufbau

func _water_material(mask: String, horizon: float, quay: float, scale: float, v: Vector2) -> ShaderMaterial:
	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/water.gdshader")
	mat.set_shader_parameter("water_mask", load(mask))
	mat.set_shader_parameter("horizon_y", horizon)
	mat.set_shader_parameter("quay_y", quay)
	mat.set_shader_parameter("px_scale", scale)
	mat.set_shader_parameter("view", v)
	return mat


func _build_print() -> void:
	var cu: Dictionary = scene_info["closeup"]
	bg = Sprite2D.new()
	bg.texture = load("res://art/bg.png")
	bg.centered = false
	bg.position = PRINT_ORIGIN
	bg.material = _water_material("res://art/water.png", float(scene_info["horizon_y"]), 436.0, 1.0, Vector2.ZERO)
	add_child(bg)
	bg_close = Sprite2D.new()
	bg_close.texture = load("res://art/bg_close.png")
	bg_close.centered = false
	bg_close.position = PRINT_ORIGIN
	bg_close.material = _water_material("res://art/water_close.png", float(cu["horizon_y"]), float(cu["quay_y"]),
		zoom, view)
	bg_close.visible = false
	add_child(bg_close)


func _build_lights() -> void:
	# Licht wird gedruckt, nicht addiert: fertige, deckende Bilder (Scheibe mit Bokashi und Indigo-Kontur hinter dem
	# Gehäuse, flache Strahlen), die nur ein- und ausgeschaltet werden (10 Bilder/s), nie überblendet oder skaliert.
	lamp_tex = [load("res://art/lamp_a.png"), load("res://art/lamp_b.png")]
	lamp_fx = Sprite2D.new()
	lamp_fx.centered = false
	lamp_fx.position = PRINT_ORIGIN + Vector2(lights["lamp_a"]["pos"][0], lights["lamp_a"]["pos"][1])
	lamp_fx.texture = lamp_tex[0]
	lamp_fx.visible = false
	add_child(lamp_fx)
	lantern_tex = [load("res://art/lantern_1.png"), load("res://art/lantern_2.png")]
	lantern_fx = Sprite2D.new()
	lantern_fx.centered = false
	lantern_fx.position = PRINT_ORIGIN + Vector2(lights["lantern_1"]["pos"][0], lights["lantern_1"]["pos"][1])
	lantern_fx.texture = lantern_tex[0]
	add_child(lantern_fx)


func _build_smoke() -> void:
	# Rauch als fertige Bildfolge (20 Bilder, Schleife 2,0 s, 10 Bilder/s): deckende flache Fahne mit Sumi-Kontur
	# und Bokashi nach oben. Schornsteinmund bei (112, 134) im Einzelbild.
	var ch: Array = scene_info["chimney"]
	smoke = Sprite2D.new()
	smoke.texture = load("res://art/smoke.png")
	smoke.hframes = 20
	smoke.centered = false
	smoke.position = PRINT_ORIGIN + Vector2(ch[0], ch[1] - 3) - Vector2(112, 134)
	add_child(smoke)


func _build_badger() -> void:
	badger_tex = [load("res://art/badger.png"), load("res://art/badger_close.png")]
	badger = Sprite2D.new()
	badger.texture = badger_tex[0]
	badger.hframes = int(timeline["frames"])
	badger.centered = false
	add_child(badger)


# Wellenbretter: [Sprite, x, Unterkante, Amplitude y, Amplitude x, Periode, Phase] (Totale-Bildschirmkoordinaten).
# Hintere Reihe alle 145 px: Nachbarn überlappen 41-52 px (bei gegenläufigem Kreisen mindestens 33 px), so liegt die
# ausgeblendete rechte Kante jeder Welle (16 px) ganz unter dem deckenden Körper der rechts folgenden Welle.
const BACK_ROW := [
	[3, -38, 720, 4.0, 4.0, 2.0, 0.0], [5, 107, 720, 4.0, 4.0, 2.0, 1.1], [4, 252, 720, 4.0, 4.0, 2.0, 2.3],
	[3, 397, 720, 4.0, 4.0, 2.0, 3.4], [5, 542, 720, 4.0, 4.0, 2.0, 4.4], [4, 687, 720, 4.0, 4.0, 2.0, 5.5],
	[3, 832, 720, 4.0, 4.0, 2.0, 0.6], [5, 977, 720, 4.0, 4.0, 2.0, 1.7], [4, 1122, 720, 4.0, 4.0, 2.0, 2.9]]
const FRONT_ROW := [
	[2, -30, 742, 8.0, 6.0, 3.0, 0.4], [0, 210, 742, 9.0, 6.0, 3.0, 2.2], [1, 520, 742, 9.0, 6.0, 3.0, 4.1],
	[2, 790, 742, 8.0, 6.0, 3.0, 1.3], [0, 1030, 742, 9.0, 6.0, 3.0, 3.3]]


func _build_waves() -> void:
	for i in 6:
		wave_tex.append([load("res://art/wave_%d.png" % i), load("res://art/wave_%d_close.png" % i)])
	for row in [BACK_ROW, FRONT_ROW]:
		for w in row:
			var s := Sprite2D.new()
			s.texture = wave_tex[w[0]][0]
			s.centered = false
			add_child(s)
			(waves_back if row == BACK_ROW else waves_front).append([s, w])
	spray_tex = [load("res://art/spray.png"), load("res://art/spray_close.png")]
	spray = Node2D.new()
	spray.draw.connect(_draw_spray)
	add_child(spray)


func _build_frame() -> void:
	# Papierrand um den Druck und Randlinie des Druckstocks (deckt Wellenunterkanten und Bildränder ab)
	var f := Node2D.new()
	f.draw.connect(func() -> void:
		var W := 1280.0
		var H := 720.0
		f.draw_rect(Rect2(0, 0, W, PRINT_ORIGIN.y), PAPER)
		f.draw_rect(Rect2(0, H - PRINT_ORIGIN.y, W, PRINT_ORIGIN.y), PAPER)
		f.draw_rect(Rect2(0, 0, PRINT_ORIGIN.x, H), PAPER)
		f.draw_rect(Rect2(W - PRINT_ORIGIN.x, 0, PRINT_ORIGIN.x, H), PAPER)
		f.draw_rect(Rect2(PRINT_ORIGIN, PRINT_SIZE), SUMI, false, 2.0))
	add_child(f)


func _label(text: String, font: Font, size: int, color: Color, pos: Vector2, parent: Node) -> Label:
	var l := Label.new()
	l.text = text
	var ls := LabelSettings.new()
	ls.font = font
	ls.font_size = size
	ls.font_color = color
	l.label_settings = ls
	l.position = pos
	parent.add_child(l)
	return l


func _vgrad(c0: Color, c1: Color) -> GradientTexture2D:
	var g := Gradient.new()
	g.colors = PackedColorArray([c0, c1])
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill_from = Vector2(0, 0)
	tex.fill_to = Vector2(0, 1)
	tex.width = 4
	tex.height = 64
	return tex


func _build_ui() -> void:
	var body: Font = load("res://fonts/KaiseiTokumin-Regular.ttf")
	var bold: Font = load("res://fonts/KaiseiTokumin-Bold.ttf")
	var title: Font = load("res://fonts/ZenAntique-Regular.ttf")
	var ui := Node2D.new()
	add_child(ui)

	# --- Gedichtzettel (Ortsname als Kopfzeile, Text, Auswahl, Eingabe) im Himmel
	var slip := Rect2(214, 16, 690, 152)
	var head_h := 30.0
	var head_band := _vgrad(Color(PRUSSIAN, 1.0), Color(PRUSSIAN.lerp(SLIP_PAPER, 0.35), 1.0))
	var bot_band := _vgrad(Color(0.85, 0.47, 0.44, 0.0), Color(0.85, 0.47, 0.44, 0.42))
	var top_y := slip.position.y + head_h
	var divider_x := slip.position.x + 16 + 362 + 16
	var deco := Node2D.new()
	deco.draw.connect(func() -> void:
		deco.draw_rect(slip, SLIP_PAPER)
		# Ichimonji-Band in Preußischblau mit Bokashi nach unten, darin der Ortsname
		deco.draw_texture_rect(head_band, Rect2(slip.position, Vector2(slip.size.x, head_h)), false)
		deco.draw_line(Vector2(slip.position.x, top_y), Vector2(slip.end.x, top_y), SUMI, 1.0)
		deco.draw_texture_rect(bot_band, Rect2(slip.position + Vector2(2, slip.size.y - 14), Vector2(slip.size.x - 4, 12)), false)
		deco.draw_rect(slip, SUMI, false, 2.0)
		deco.draw_rect(Rect2(slip.position + Vector2(5, head_h + 4), slip.size - Vector2(10, head_h + 9)), SUMI, false, 1.0)
		deco.draw_line(Vector2(divider_x, top_y + 14), Vector2(divider_x, slip.end.y - 18), SUMI, 1.0))
	ui.add_child(deco)
	var head := _label("Hafen von Lornholm", title, 19, SLIP_PAPER, Vector2(slip.position.x + 18, slip.position.y + 3), ui)
	head.size = Vector2(400, 26)
	var lx := slip.position.x + 18
	_label("Die Laterne flackert im Wind.", body, 22, SUMI, Vector2(lx, top_y + 10), ui)
	_label("Am Kai wartet ein Paket auf dich.", body, 22, SUMI, Vector2(lx, top_y + 40), ui)
	var parser := _label("> nimm paket", body, 20, Color(0.33, 0.29, 0.29), Vector2(lx, top_y + 80), ui)
	cursor = ColorRect.new()
	cursor.color = VERMILION
	cursor.size = Vector2(9, 19)
	cursor.position = Vector2(lx + 140, top_y + 85)
	ui.add_child(cursor)

	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	var cx := divider_x + 16
	for i in 3:
		var y := top_y + 12 + i * 33
		var selected := i == 1
		var seal := Node2D.new()
		var sp := Vector2(cx, y + 4)
		seal.draw.connect(func() -> void:
			seal.draw_rect(Rect2(sp, Vector2(19, 19)), VERMILION)
			seal.draw_rect(Rect2(sp + Vector2(2, 2), Vector2(15, 15)), Color(SLIP_PAPER, 0.9), false, 1.0))
		ui.add_child(seal)
		var num := _label(str(i + 1), title, 15, SLIP_PAPER, Vector2(cx + 5, y + 2), ui)
		num.size = Vector2(10, 20)
		_label(choices[i], bold if selected else body, 20, VERMILION if selected else SUMI, Vector2(cx + 28, y), ui)

	# --- Titelkartusche rechts oben ohne Schrift (wie der Auftrag verlangt): Zinnoberrahmen, gelbes Feld mit
	# Bokashi, darin ein Seigaiha-Wellenmuster in Indigo (Ornament, keine Zeichen)
	var cart := Rect2(1106, 18, 148, 92)
	var field_tex := _vgrad(Color(0.89, 0.76, 0.42), Color(0.96, 0.89, 0.62))
	var cdeco := Node2D.new()
	var frame_col := Color(0.78, 0.26, 0.2)
	var wave_fill := Color(0.96, 0.89, 0.62)
	cdeco.draw.connect(func() -> void:
		cdeco.draw_rect(cart, frame_col)
		var inner := cart.grow(-8)
		cdeco.draw_texture_rect(field_tex, inner, false)
		# Seigaiha: Reihen konzentrischer Halbkreise, von oben nach unten gedruckt (untere Reihe deckt die obere)
		var r := 12.0
		for row in [2, 1, 0]:
			var yb: float = inner.end.y + 2 - row * r * 0.9
			var x: float = inner.position.x - r + (row % 2) * r
			while x < inner.end.x + r:
				var c := Vector2(x + r, yb)
				var pts := PackedVector2Array()
				for k in 19:
					pts.append(c + Vector2(cos(PI + PI * k / 18.0), sin(PI + PI * k / 18.0)) * r)
				cdeco.draw_colored_polygon(pts, wave_fill)
				for k in 3:
					cdeco.draw_arc(c, r - k * 4.0, PI, TAU, 18, INDIGO, 1.3, true)
				x += 2.0 * r
		# Rahmen über den Überstand der Muster drucken
		cdeco.draw_rect(Rect2(cart.position, Vector2(cart.size.x, 8)), frame_col)
		cdeco.draw_rect(Rect2(cart.position + Vector2(0, cart.size.y - 8), Vector2(cart.size.x, 8)), frame_col)
		cdeco.draw_rect(Rect2(cart.position, Vector2(8, cart.size.y)), frame_col)
		cdeco.draw_rect(Rect2(cart.position + Vector2(cart.size.x - 8, 0), Vector2(8, cart.size.y)), frame_col)
		cdeco.draw_rect(cart, SUMI, false, 2.0)
		cdeco.draw_rect(inner, SUMI, false, 1.5))
	ui.add_child(cdeco)


func _build_paper() -> void:
	# Washi multiplikativ über alles (Druck, Figur, Wellen, Text): ein Bogen Papier
	var p := TextureRect.new()
	p.texture = load("res://art/washi.png")
	p.stretch_mode = TextureRect.STRETCH_TILE
	p.size = Vector2(1280, 720)
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_MUL
	p.material = m
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(p)


# ---------------------------------------------------------------- Ablauf

func _process(_delta: float) -> void:
	tick += 1
	_update()


func _update() -> void:
	var t := tick / 30.0 + t0
	# Dachs: Einstellung, Bild und Lage je Takt aus der Zeitleiste (ohne t0: er läuft immer von vorn)
	var ticks: Array = timeline["ticks"]
	var e: Dictionary = ticks[min(tick, ticks.size() - 1)]
	shot = int(e["s"])
	badger.texture = badger_tex[shot]
	badger.frame = int(e["f"])
	badger.position = Vector2(float(e["x"]), float(e["y"]))
	if probe:
		return

	bg.visible = shot == 0
	bg_close.visible = shot == 1
	lamp_fx.visible = false
	lantern_fx.visible = false
	smoke.visible = shot == 0       # Schornstein, Laterne und Leuchtturm liegen außerhalb der Nahaufnahme

	var step := int(floorf(t * 10.0 + 1e-4))   # Umgebung auf Dreien (10 Bilder/s)
	var t10 := step / 10.0
	var t15 := floorf(t * 15.0 + 1e-4) / 15.0  # Wellen auf Zweien (15 Bilder/s)
	(bg.material as ShaderMaterial).set_shader_parameter("time_q", t10)
	(bg_close.material as ShaderMaterial).set_shader_parameter("time_q", t10)

	if shot == 0:
		# Leuchtfeuer: alle 3 s ein Blitz in drei gedruckten Stufen (0,1 s Scheibe, 0,2 s Scheibe + Strahlen, 0,1 s
		# Scheibe), sonst nur das gemalte Glas
		var ph := posmod(step - 16, 30)
		if ph <= 3:
			lamp_fx.visible = true
			lamp_fx.texture = lamp_tex[1 if (ph == 1 or ph == 2) else 0]
		# Laterne: Flackern aus festen Zufallswerten, 10 Bilder/s: keine, kleine oder große Scheibe
		var fl := flicker[posmod(step, flicker.size())]
		if fl >= 0.18:
			lantern_fx.visible = true
			lantern_fx.texture = lantern_tex[1 if fl >= 0.62 else 0]
		smoke.frame = posmod(step, 20)

	# Wellenbretter: kreisen wie die Wellen einer Bühne (y = sin, x = cos), ganze Pixel
	for row in [waves_back, waves_front]:
		for item in row:
			var sp: Sprite2D = item[0]
			var w: Array = item[1]
			var om: float = TAU / float(w[5])
			var small: Texture2D = wave_tex[w[0]][0]
			var y: float = float(w[2]) - small.get_height() + float(w[3]) * sin(om * t15 + float(w[6]))
			var x: float = float(w[1]) + float(w[4]) * cos(om * t15 + float(w[6]))
			sp.texture = wave_tex[w[0]][shot]
			sp.position = _xf(Vector2(round(x), round(y))).round()
	spray.queue_redraw()

	cursor.visible = int(floorf(t * 2.0)) % 2 == 0


func _draw_spray() -> void:
	# Gischt: Am höchsten Punkt jeder großen Welle fliegen Tropfen aus den Krallen (Wurfparabel), 15 Bilder/s.
	# Gedruckte Tropfen werden nicht ausgeblendet: Sie bleiben deckend und schrumpfen zum Schluss 9 -> 7 -> 5 px,
	# dann verschwinden sie.
	var t := floorf((tick / 30.0 + t0) * 15.0 + 1e-4) / 15.0
	var tex: Texture2D = spray_tex[shot]
	var cell := 10.0 if shot == 0 else 16.0
	for wi in waves_front.size():
		var item: Array = waves_front[wi]
		var w: Array = item[1]
		var per := float(w[5])
		var om := TAU / per
		var small: Texture2D = wave_tex[w[0]][0]
		var size := small.get_size()
		var y0: float = float(w[2]) - size.y + float(w[3]) * sin(om * t + float(w[6]))
		var x0: float = float(w[1]) + float(w[4]) * cos(om * t + float(w[6]))
		var base := Vector2(round(x0), round(y0))
		# höchster Punkt: om*t + phase = 3π/2 + 2πn
		var n_now := floorf((om * t + float(w[6]) - 1.5 * PI) / TAU)
		for dn in [0.0, -1.0]:
			var n: float = n_now + dn
			var tb := (1.5 * PI + TAU * n - float(w[6])) / om - 0.12
			var age := t - tb
			if age < 0.0 or age > 0.75:
				continue
			for j in 7:
				var r := int(posmod(int(n) * 97 + wi * 31 + j * 7, 3990))
				var ox := size.x * (0.55 + 0.35 * spray_rnd[r])
				var oy := size.y * (0.08 + 0.2 * spray_rnd[r + 1])
				var vx := 30.0 + 60.0 * spray_rnd[r + 2]
				var vy := -(55.0 + 55.0 * spray_rnd[r + 3])
				var k := int(spray_rnd[r + 4] * 2.999)      # Tropfen 5, 7 oder 9 px
				k -= int(age >= 0.5) + int(age >= 0.625)   # zum Schluss schrumpfen statt ausblenden
				if k < 0:
					continue
				var p := _xf(base + Vector2(ox + vx * age, oy + vy * age + 0.5 * 260.0 * age * age))
				spray.draw_texture_rect_region(tex, Rect2((p - Vector2(cell, cell) * 0.5).round(), Vector2(cell, cell)),
					Rect2(k * cell, 0, cell, cell))

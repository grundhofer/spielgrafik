extends Node2D
## Hafen von Lornholm als klassischer Zeichentrick: gemalter Hintergrund, davor Cels (flache Farben, Tusche,
## harter Schatten), die auf Zweien laufen: Figur, Boote, Möwen und Effekte wechseln 15-mal je Sekunde (jedes Bild
## zwei Videobilder lang). Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur über
## RandomNumberGenerator mit festem Seed.
## Daten: res://art/sprites.json (Blatt des Dachses, scripts/build_sprites.py), res://art/walk.json (gemessener
## Vorschub je Laufbild, scripts/measure_walk.py).

const TICKS_PER_S := 15.0  # auf Zweien bei 30 fps
const SEED := 20261012
const GLINT_CYCLE := 100

# Lage im Bild (1280x720, gemessen im Ausschnitt von scripts/build_bg.py)
const FOOT_Y := 612.0
const END_X := 470.0
const LANTERN := Vector2(881, 279)
const WINDOW := Vector2(173, 336)
const LAMP := Vector2(1120, 88)
const BOAT_A := Vector2(752, 506)  # Mitte der Wasserlinie
const BOAT_B := Vector2(352, 428)
const WATER_COL := Color(0.07, 0.15, 0.29)
const HULL_WATER := Color(0.12, 0.26, 0.46)  # Wasserfarbe an den Booten (im Hintergrund gemessen)
const MASK_BAND := Rect2i(290, 372, 810, 180)  # Bereich der Wassermaske (scripts/build_water_mask.py)

# Ablauf in Ticks (1 Tick = 1/15 s)
const WALK_TICKS := 39       # Laufbilder 0..38, letztes ist walk_6
const STAND_TICKS := 4
const TALK_START := 47
const BLINKS := [70, 86]     # Blinzeln nach der Dachs-Zeile
const TITLE_TICK := 3
const NARRATION_TICK := 12
const LABEL_DY := 3.0  # mittige Zeilenbox sitzt 3,5 px zu hoch (Unterlänge); im Render gemessen
const HOVER_TICK := 69
const PARSER_TICK := 58

const TITLE := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind.\nAm Kai wartet ein Paket auf dich."  # Erzähler (Untertitelkarte)
const BADGER_LINE := "Moin! Ein Paket für dich."  # eigene Zeile des Dachses (Sprechtext mit Mund-Cels)
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const INK := Color(0.11, 0.075, 0.13)
const CREAM := Color(0.957, 0.906, 0.784)
const SPEECH := Color(1.0, 0.94, 0.70)
const BADGE := Color(0.85, 0.34, 0.17)
const HILITE := Color(1.0, 0.82, 0.33)
const RED := Color(0.72, 0.18, 0.14)

var t := 0.0
var tick := 0
var meta: Dictionary
var advance: Array = []
var walk_x := PackedFloat32Array()
var frame_index := {}

var badger: Sprite2D
var shadow: Sprite2D
var boats: Array = []   # [Sprite2D boat, Sprite2D refl, Vector2 base, float amp_deg, float period, float phase, ShaderMaterial, ShaderMaterial]
var gulls: Array = []   # [Sprite2D, Vector2 start, float speed, float phase, float bob]
var glints: Array = []  # [start_tick, life, Vector2 pos, int len, Color]
var glint_node: Node2D
var wave_node: Node2D
var lantern_glow: Sprite2D
var lantern_core: Sprite2D
var window_glow: Sprite2D
var lamp_glow: Sprite2D
var twinkle: Sprite2D
var flicker := PackedFloat32Array()

var glint_stats := {"tries": 0, "rejected": 0, "placed": 0}
var title_box: Control
var narration_box: Control
var speech: Label
var choice_lbls: Array = []
var hilite: Panel
var parser_lbl: Label
var parser_fs := 23
var cursor: ColorRect

var font_body: FontVariation
var font_title: FontFile


func _ready() -> void:
	meta = JSON.parse_string(FileAccess.get_file_as_string("res://art/sprites.json"))
	var walk: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/walk.json"))
	advance = walk["advance"]
	for f in meta["frames"]:
		frame_index[f["name"]] = int(f["index"])
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	_build_walk_path(float(walk["walk_6_to_stand"]["advance_px"]))
	_build_lights(rng)
	_build_boats()
	_build_gulls()
	_build_glints(rng)
	_build_badger()
	_build_ui()
	_apply_probe()
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):  # Langzeitprüfung: Start bei t0 Sekunden
			t = float(a.substr(5))
	_update()


func _apply_probe() -> void:
	# Prüfschalter (nach --): --probe-badger zeigt nur die Figur vor Magenta (scripts/measure_feet.py),
	# --probe-glints nur Glitzer und Boote ohne Spiegelbild vor Magenta (scripts/measure_glints.py)
	var args := OS.get_cmdline_user_args()
	if "--probe-badger" in args:
		for n in [$Bg, $Far, $Glints, $Boats, $Fx, $Lights, $UI]:
			n.visible = false
		shadow.visible = false
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
	if "--probe-glints" in args:
		for n in [$Bg, $Far, $Fx, $Actor, $Lights, $UI]:
			n.visible = false
		for b in boats:
			(b[1] as Sprite2D).visible = false
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
		print("Glitzer: ", glint_stats)


# ---------------------------------------------------------------- Aufbau

func _build_walk_path(stand_adv: float) -> void:
	# Wurzel-x je Laufbild aus dem gemessenen Vorschub; Ende so, dass die Figur bei END_X steht.
	var xs := [0.0]
	for k in range(1, WALK_TICKS):
		xs.append(xs[k - 1] + float(advance[(k - 1) % 8]))
	var end_walk := END_X - stand_adv
	var off: float = end_walk - xs[WALK_TICKS - 1]
	walk_x.resize(WALK_TICKS + 1)
	for k in WALK_TICKS:
		walk_x[k] = xs[k] + off
	walk_x[WALK_TICKS] = END_X


func _build_badger() -> void:
	var actor := $Actor
	shadow = Sprite2D.new()
	shadow.texture = load("res://art/shadow.png")
	shadow.modulate = Color(1, 1, 1, 0.5)
	actor.add_child(shadow)
	badger = Sprite2D.new()
	badger.texture = load("res://art/badger_cels.png")
	badger.hframes = meta["frames"].size()
	badger.centered = false
	badger.offset = Vector2(-round(float(meta["root_x"])), -float(meta["baseline"]))
	actor.add_child(badger)


func _build_boats() -> void:
	var specs := [["res://art/boat_b.png", BOAT_B, 1.4, 3.6, 1.1], ["res://art/boat_a.png", BOAT_A, 1.7, 3.1, 0.0]]
	var bshader := load("res://shaders/cel_boat.gdshader")
	var rshader := load("res://shaders/cel_reflection.gdshader")
	for s in specs:
		var tex: Texture2D = load(s[0])
		var w := float(tex.get_width())
		var h := float(tex.get_height())
		var refl := Sprite2D.new()
		refl.texture = tex
		refl.centered = false
		refl.flip_v = true
		refl.offset = Vector2(-w * 0.5, 0)
		var rm := ShaderMaterial.new()
		rm.shader = rshader
		rm.set_shader_parameter("waterline", s[1].y)
		rm.set_shader_parameter("depth", h * 0.7)
		rm.set_shader_parameter("water", WATER_COL)
		refl.material = rm
		$Boats.add_child(refl)
		var boat := Sprite2D.new()
		boat.texture = tex
		boat.centered = false
		boat.offset = Vector2(-w * 0.5, -h)
		var bm := ShaderMaterial.new()
		bm.shader = bshader
		bm.set_shader_parameter("waterline", s[1].y + 1.0)
		bm.set_shader_parameter("water", HULL_WATER)
		boat.material = bm
		$Boats.add_child(boat)
		boats.append([boat, refl, s[1], s[2], s[3], s[4], bm, rm, w])


func _build_gulls() -> void:
	var tex: Texture2D = load("res://art/gull.png")
	for g in [[Vector2(-60, 214), 105.0, 0.0, 6.0], [Vector2(-260, 128), 92.0, 2.0, 4.0]]:  # unter der Erzählerkarte
		var sp := Sprite2D.new()
		sp.texture = tex
		sp.hframes = 4
		$Far.add_child(sp)
		gulls.append([sp, g[0], g[1], g[2], g[3]])


func _is_water(img: Image, x: int, y: int) -> bool:
	if not MASK_BAND.has_point(Vector2i(x, y)):
		return false
	var c := img.get_pixel(x, y)
	return c.r > 0.5 or c.g > 0.5


func _build_glints(rng: RandomNumberGenerator) -> void:
	# Glitzer als Effekt-Cels: kurze flache Striche, die für 3–6 Zeichnungen erscheinen. Lage nur auf Wasser: Die
	# Wassermaske (res://art/water_mask.png aus scripts/build_water_mask.py; R = blaues Wasser, G = oranger
	# Widerschein) schließt Steg, Pfähle, Laternenpfahl, Felsen und Kai aus. Jeder gezogene Strich muss mit seiner
	# vollen Länge und beiden Zeilen auf Wasser liegen, sonst wird er verworfen (bis zu 4 Ziehungen je Versuch).
	# Die Ebene liegt unter den Booten: Rumpf und Segel decken Striche dahinter ab.
	var img: Image = (load("res://art/water_mask.png") as Texture2D).get_image()
	if img.is_compressed():
		img.decompress()
	var pools := [[], []]  # 0 = oranger Widerschein, 1 = blaues Wasser
	for y in range(MASK_BAND.position.y, MASK_BAND.end.y):
		for x in range(MASK_BAND.position.x, MASK_BAND.end.x):
			var c := img.get_pixel(x, y)
			if c.g > 0.5:
				pools[0].append(Vector2i(x, y))
			elif c.r > 0.5:
				pools[1].append(Vector2i(x, y))
	# je Tick: drei Versuche im Widerschein (orange), zwei auf dem übrigen Wasser (hellblau)
	var kinds := [[0, Color(1.0, 0.80, 0.52), 3], [1, Color(0.62, 0.74, 0.92), 2]]
	for k in range(0, GLINT_CYCLE):
		for kd in kinds:
			var pool: Array = pools[int(kd[0])]
			for n in int(kd[2]):
				if rng.randf() >= 0.55 or pool.is_empty():
					continue
				glint_stats["tries"] += 1
				for attempt in 4:
					var p: Vector2i = pool[rng.randi_range(0, pool.size() - 1)]
					# Striche in der Ferne kürzer (Perspektive): 6 px an der Kimm bis 14 px vorn
					var depth := clampf(float(p.y - MASK_BAND.position.y) / float(MASK_BAND.size.y), 0.0, 1.0)
					var ln := rng.randi_range(4, int(round(lerpf(6.0, 14.0, depth))))
					var x0 := p.x - int(floor(ln * 0.5))
					var ok := true
					for xx in range(x0, x0 + ln):
						if not (_is_water(img, xx, p.y) and _is_water(img, xx, p.y + 1)):
							ok = false
							break
					if not ok:
						glint_stats["rejected"] += 1
						continue
					glints.append([k, rng.randi_range(3, 6), Vector2(p), ln, kd[1]])
					glint_stats["placed"] += 1
					break
	glint_node = Node2D.new()
	glint_node.draw.connect(_draw_glints)
	$Glints.add_child(glint_node)
	wave_node = Node2D.new()
	wave_node.draw.connect(_draw_waves)
	$Fx.add_child(wave_node)


func _add_glow(pos: Vector2, scale_px: float, col: Color) -> Sprite2D:
	var sp := Sprite2D.new()
	sp.texture = load("res://art/glow.png")
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	sp.material = m
	sp.position = pos
	sp.scale = Vector2.ONE * scale_px / 128.0
	sp.modulate = col
	$Lights.add_child(sp)
	return sp


func _build_lights(rng: RandomNumberGenerator) -> void:
	# Flackern der Laterne: eine Tabelle je Tick (15 Werte je Sekunde), gemischt aus zwei Zufallsfolgen
	var a := 0.0
	for k in 200:
		a = lerp(a, rng.randf(), 0.55)
		flicker.append(a)
	window_glow = _add_glow(WINDOW, 150.0, Color(1.0, 0.6, 0.25, 0.25))
	lantern_glow = _add_glow(LANTERN, 230.0, Color(1.0, 0.66, 0.3, 0.45))
	lantern_core = _add_glow(LANTERN + Vector2(0, 2), 70.0, Color(1.0, 0.85, 0.5, 0.5))
	lamp_glow = _add_glow(LAMP, 110.0, Color(1.0, 0.8, 0.45, 0.4))
	twinkle = Sprite2D.new()
	twinkle.texture = load("res://art/twinkle.png")
	twinkle.hframes = 3
	twinkle.position = LAMP
	$Lights.add_child(twinkle)


func _panel(fill: Color, border: Color, bw: int, radius: int) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.border_color = border
	sb.set_border_width_all(bw)
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	return sb


func _label(text: String, font: Font, size: int, col: Color, outline := 0, ocol := Color.BLACK) -> Label:
	var l := Label.new()
	l.text = text
	var ls := LabelSettings.new()
	ls.font = font
	ls.font_size = size
	ls.font_color = col
	ls.outline_size = outline
	ls.outline_color = ocol
	l.label_settings = ls
	return l


func _build_ui() -> void:
	var ui := $UI
	font_title = load("res://fonts/LilitaOne-Regular.ttf")
	var gs: FontFile = load("res://fonts/Grandstander-wght.ttf")
	font_body = FontVariation.new()
	font_body.base_font = gs
	font_body.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): 700}

	# Ortstitel als Titelkarte: Cel-Fläche mit Tusche-Rand und hartem Schatten, springt auf Zweien auf
	title_box = Control.new()
	title_box.size = Vector2(380, 58)
	title_box.position = Vector2(640 - 190, 18)
	title_box.pivot_offset = title_box.size * 0.5
	var tsh := Panel.new()
	tsh.add_theme_stylebox_override("panel", _panel(Color(0.1, 0.06, 0.16, 0.9), Color(0, 0, 0, 0), 0, 29))
	tsh.position = Vector2(5, 6)
	tsh.size = title_box.size
	title_box.add_child(tsh)
	var tp := Panel.new()
	tp.add_theme_stylebox_override("panel", _panel(CREAM, INK, 3, 29))
	tp.size = title_box.size
	title_box.add_child(tp)
	var tl := _label(TITLE, font_title, 32, RED)
	tl.size = title_box.size
	tl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	tl.position = Vector2(0, 1)
	title_box.add_child(tl)
	ui.add_child(title_box)

	# Erzähler als Untertitelkarte unter dem Titel: dunkle Cel-Fläche mit cremefarbener Schrift, getrennt vom
	# Sprechtext der Figur (die Zeile ist Erzähltext, kein Satz des Dachses)
	narration_box = Control.new()
	var nfs := 23
	var nw := 0.0
	for ln in LINE.split("\n"):
		nw = maxf(nw, font_body.get_string_size(ln, HORIZONTAL_ALIGNMENT_LEFT, -1, nfs).x)
	narration_box.size = Vector2(round(nw) + 48, 74)
	narration_box.position = Vector2(round(640 - narration_box.size.x * 0.5), 92)
	narration_box.pivot_offset = narration_box.size * 0.5
	var nsh := Panel.new()
	nsh.add_theme_stylebox_override("panel", _panel(Color(0.05, 0.03, 0.08, 0.85), Color(0, 0, 0, 0), 0, 12))
	nsh.position = Vector2(4, 5)
	nsh.size = narration_box.size
	narration_box.add_child(nsh)
	var npn := Panel.new()
	npn.add_theme_stylebox_override("panel", _panel(Color(0.19, 0.12, 0.25), CREAM, 2, 12))
	npn.size = narration_box.size
	narration_box.add_child(npn)
	var nl := _label(LINE, font_body, nfs, CREAM)
	nl.size = narration_box.size
	nl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	nl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	narration_box.add_child(nl)
	ui.add_child(narration_box)

	# Sprechtext über der Figur (Adventure-Konvention: farbige Schrift mit dunkler Kontur), nur für die eigene
	# Zeile des Dachses, zu der die Mund-Cels laufen
	speech = _label(BADGER_LINE, font_body, 30, SPEECH, 10, Color(0.09, 0.05, 0.14))
	speech.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	speech.size = Vector2(620, 44)
	ui.add_child(speech)

	# Auswahlleiste unten: Cel-Fläche mit Tusche-Rand und hartem Schatten
	var bar := Control.new()
	bar.position = Vector2(16, 646)
	bar.size = Vector2(1248, 60)
	var bsh := Panel.new()
	bsh.add_theme_stylebox_override("panel", _panel(Color(0.1, 0.06, 0.16, 0.9), Color(0, 0, 0, 0), 0, 16))
	bsh.position = Vector2(0, 6)
	bsh.size = bar.size
	bar.add_child(bsh)
	var bp := Panel.new()
	bp.add_theme_stylebox_override("panel", _panel(CREAM, INK, 3, 16))
	bp.size = bar.size
	bar.add_child(bp)
	hilite = Panel.new()
	hilite.add_theme_stylebox_override("panel", _panel(HILITE, INK, 2, 14))
	hilite.visible = false
	bar.add_child(hilite)
	# Eingabefeld rechts (weiße Cel-Fläche), Antworten links davon
	var fs := 23
	var pw := font_body.get_string_size(PARSER, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var field := Panel.new()
	field.add_theme_stylebox_override("panel", _panel(Color(1.0, 0.98, 0.93), INK, 2, 10))
	field.size = Vector2(pw + 44, 40)
	field.position = Vector2(bar.size.x - field.size.x - 12, 10)
	bar.add_child(field)
	parser_lbl = _label("", font_body, fs, INK)
	parser_lbl.position = field.position + Vector2(14, LABEL_DY)
	parser_lbl.size = Vector2(pw + 8, field.size.y)
	parser_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	bar.add_child(parser_lbl)
	cursor = ColorRect.new()
	cursor.color = INK
	cursor.size = Vector2(11, 23)
	bar.add_child(cursor)
	var x := 16.0
	for i in CHOICES.size():
		var badge := Panel.new()
		badge.add_theme_stylebox_override("panel", _panel(BADGE, INK, 2, 14))
		badge.position = Vector2(x, 16)
		badge.size = Vector2(28, 28)
		bar.add_child(badge)
		var num := _label(str(i + 1), font_title, 20, CREAM)
		num.position = Vector2(x, 16)
		num.size = Vector2(28, 28)
		num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		bar.add_child(num)
		var l := _label(CHOICES[i], font_body, fs, INK)
		# auf Leistenhöhe, senkrecht mittig wie Ziffern-Badge (y 16–44) und Auswahlfläche (y 8–52): Mitte y 30
		l.position = Vector2(x + 37, LABEL_DY)
		l.size = Vector2(font_body.get_string_size(CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x + 8, bar.size.y)
		l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		bar.add_child(l)
		choice_lbls.append(l)
		var w := font_body.get_string_size(CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		if i == 1:
			hilite.position = Vector2(x - 7, 8)
			hilite.size = Vector2(w + 54, 44)
			hilite.pivot_offset = hilite.size * 0.5
		x += 37 + w + 34
	if x - 34 > field.position.x - 12:
		push_error("Auswahlleiste: Antworten (bis %d px) überdecken das Eingabefeld (ab %d px)" % [x - 34, field.position.x])
	parser_fs = fs
	ui.add_child(bar)


# ---------------------------------------------------------------- Ablauf

func _process(delta: float) -> void:
	t += delta
	_update()


func _update() -> void:
	tick = int(floor(t * TICKS_PER_S + 0.001))
	var tt := tick / TICKS_PER_S  # Zeit auf Zweien: alle Bewegungen springen 15-mal je Sekunde
	_update_badger()
	_update_boats(tt)
	_update_gulls(tt)
	_update_lights(tt)
	glint_node.queue_redraw()
	wave_node.queue_redraw()
	_update_ui()


func _mouth(k: int) -> String:
	# Eigene kurze Zeile des Dachses („Moin! Ein Paket für dich.“), Silben je zwei Ticks: offen/halb, dann halb/zu.
	# „Moin!“, Pause, „Ein Pa-ket für dich.“; danach Ruhe mit zwei Blinzlern. Die Erzählerzeile hat keine Mund-Cels.
	var seq := "ba" + "000" + "a0" + "ba" + "a0" + "ba" + "ba" + "0"   # 16 Ticks
	if k >= 0 and k < seq.length():
		match seq[k]:
			"a": return "front_talk_a"
			"b": return "front_talk_b"
		return "front"
	if (k + TALK_START) in BLINKS:
		return "front_blink"
	return "front"


func _update_badger() -> void:
	var fname := "front"
	var x := END_X
	var sc := Vector2.ONE
	if tick < WALK_TICKS:
		fname = "walk_%d" % (tick % 8)
		x = walk_x[tick]
	elif tick < WALK_TICKS + STAND_TICKS:
		fname = "stand"
	else:
		var k := tick - (WALK_TICKS + STAND_TICKS)
		# Drehung zur Kamera: ein Bild gestaucht, eines gestreckt, dann Ruhe (Squash & Stretch)
		if k == 0:
			sc = Vector2(1.05, 0.94)
		elif k == 1:
			sc = Vector2(0.97, 1.04)
		fname = _mouth(tick - TALK_START)
	badger.frame = frame_index[fname]
	badger.position = Vector2(round(x), FOOT_Y)
	badger.scale = sc
	shadow.position = Vector2(round(x) - 4, FOOT_Y - 2)
	shadow.scale = Vector2(1.0 if fname.begins_with("walk") or fname == "stand" else 1.12, 1.0)


func _update_boats(tt: float) -> void:
	for b in boats:
		var boat: Sprite2D = b[0]
		var refl: Sprite2D = b[1]
		var base: Vector2 = b[2]
		var ph := TAU * tt / float(b[4]) + float(b[5])
		var rot := deg_to_rad(float(b[3]) * sin(ph))
		var bob := 1.6 * sin(ph - 0.9)
		boat.position = Vector2(base.x, base.y + bob)
		boat.rotation = rot
		refl.position = Vector2(base.x, base.y - bob)
		refl.rotation = -rot
		(b[6] as ShaderMaterial).set_shader_parameter("tick", float(tick))
		(b[7] as ShaderMaterial).set_shader_parameter("tick", float(tick))


func _update_gulls(tt: float) -> void:
	for g in gulls:
		var sp: Sprite2D = g[0]
		var start: Vector2 = g[1]
		var x: float = fposmod(start.x + float(g[2]) * tt + 120.0, 1520.0) - 120.0  # fliegt endlos durchs Bild
		var y: float = start.y + float(g[4]) * sin(tt * 1.3 + float(g[3]))
		sp.position = Vector2(round(x), round(y))
		# Flügelschlag: oben, oben, Mitte, unten, unten, Mitte (6 Zeichnungen = 0,4 s); zwischendurch Gleiten
		var cyc := [0, 0, 1, 2, 2, 1]
		var k := (tick + int(float(g[3]) * 3.0)) % 30
		sp.frame = 1 if k >= 18 else cyc[k % 6]


func _update_lights(tt: float) -> void:
	var f := flicker[tick % flicker.size()]
	lantern_glow.modulate.a = 0.30 + 0.32 * f
	lantern_glow.scale = Vector2.ONE * (210.0 + 40.0 * f) / 128.0
	lantern_core.modulate.a = 0.35 + 0.4 * f
	window_glow.modulate.a = 0.16 + 0.12 * flicker[(tick + 37) % flicker.size()]
	# Leuchtfeuer: alle 2,4 s ein Funkeln (vier Zeichnungen auf Zweien), dazu der Lichthof
	var k := tick % 36
	var seq := [0, 1, 2, 0]
	if k < seq.size():
		twinkle.visible = true
		twinkle.frame = seq[k]
		lamp_glow.modulate.a = 0.75
		lamp_glow.scale = Vector2.ONE * 150.0 / 128.0
	else:
		twinkle.visible = false
		lamp_glow.modulate.a = 0.35
		lamp_glow.scale = Vector2.ONE * 100.0 / 128.0


func _draw_waves() -> void:
	# Wellenstriche an der Wasserlinie der Boote (Effekt-Cel über den Booten, zwei Zeichnungen im Wechsel alle 4 Ticks)
	var alt := posmod(int(floor(tick / 4.0)), 2)
	for bt in boats:
		var base: Vector2 = bt[2]
		var bw: float = bt[8]
		for r in [[-0.40, 16], [0.47, 13], [0.05, 9]]:
			var rx: float = base.x + bw * float(r[0]) + (3.0 if alt == 1 else -2.0) * (1.0 if r[0] > 0 else -1.0)
			var ln: int = int(r[1]) - alt * 3
			wave_node.draw_rect(Rect2(round(rx - ln * 0.5), base.y + 1.0 + alt, ln, 2), Color(0.68, 0.78, 0.92, 0.9))


func _draw_glints() -> void:
	for g in glints:
		var age := posmod(tick - int(g[0]), GLINT_CYCLE)  # Glitzerfolge wiederholt sich alle 100 Ticks
		if age >= int(g[1]):
			continue
		var p: Vector2 = g[2]
		var n: int = g[3]
		# wächst und schrumpft über die Lebensdauer (Zeichnungen, keine Überblendung)
		var life := int(g[1])
		var s: float = 1.0 - absf((float(age) + 0.5) / life * 2.0 - 1.0)
		var ln: int = max(2, int(round(n * (0.35 + 0.65 * s))))
		var c: Color = g[4]
		glint_node.draw_rect(Rect2(p.x - floor(ln * 0.5), p.y, ln, 2), c)


func _update_ui() -> void:
	# Titelkarte springt auf: 0,3 -> 1,18 -> 0,94 -> 1,0 (je ein Tick)
	var k := tick - TITLE_TICK
	var pop := [0.3, 1.18, 0.94]
	title_box.visible = k >= 0
	var ts := 1.0
	if k >= 0 and k < pop.size():
		ts = pop[k]
	title_box.scale = Vector2.ONE * ts
	# Sprechtext ab dem ersten Wort, über dem Kopf, im Bild gehalten
	speech.visible = tick >= TALK_START - 1
	speech.position = Vector2(clamp(END_X - speech.size.x * 0.5, 12.0, 1268.0 - speech.size.x), 340)
	# Erzählerkarte springt wie die Titelkarte auf
	var nk := tick - NARRATION_TICK
	narration_box.visible = nk >= 0
	var ns := 1.0
	if nk >= 0 and nk < pop.size():
		ns = pop[nk]
	narration_box.scale = Vector2.ONE * ns
	# Auswahl 2 wird angewählt (Fläche springt auf, Text rot)
	var hk := tick - HOVER_TICK
	hilite.visible = hk >= 0
	var hs := 1.0
	if hk == 0:
		hs = 0.8
	elif hk == 1:
		hs = 1.08
	hilite.scale = Vector2.ONE * hs
	(choice_lbls[1] as Label).label_settings.font_color = RED if hk >= 0 else INK
	# Eingabezeile tippt mit 15 Zeichen/s, Blockcursor blinkt
	var n: int = clamp(tick - PARSER_TICK, 0, PARSER.length())
	parser_lbl.text = PARSER.substr(0, n)
	var w := font_body.get_string_size(parser_lbl.text, HORIZONTAL_ALIGNMENT_LEFT, -1, parser_fs).x
	cursor.position = Vector2(parser_lbl.position.x + w + 3, 19)
	cursor.visible = posmod(int(floor(tick / 4.0)), 2) == 0 or (n > 0 and n < PARSER.length())

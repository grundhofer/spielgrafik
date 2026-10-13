extends Node2D
## Ligne claire – Hafen von Lornholm (Katalogeintrag "ligne-claire").
##
## Ein Comic-Panel auf Papier: Hintergrund aus agy (flach eingerastet, scripts/build_bg.py), der Dachs als
## vorgerendertes Sprite mit Tuschelinien (blender/render_badger.py + scripts/ink_badger.py), dazu ein
## Nahaufnahme-Panel als Einschub. Alle Effekte sind flache Formen mit derselben schwarzen Kontur wie Figur und
## Hintergrund, die Oberfläche besteht aus Bildunterschrift-Kästen und einer Sprechblase.
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur aus RandomNumberGenerator mit festem Seed.

const SEED := 20261010
const INK := Color8(20, 20, 22)
const PAPER := Color8(244, 238, 222)
const CAPTION_FILL := Color8(248, 226, 140)
const BOX_FILL := Color8(253, 250, 241)
const RED := Color8(192, 50, 38)
const LINE_W := 3.0                         # Rahmen von Kästen, Sprechblase und Einschub (bewusst kräftiger)
const FX_LINE_W := 2.0                      # Zeichenlinien der Effekte = Hintergrund und Figur (gemessen 2 px)

const PANEL := Rect2(16, 16, 1248, 632)     # Innenfläche des Hauptpanels (Bildschirmkoordinaten)
const VIEW_DY := 46.0                       # so viele Zeilen des Hintergrunds liegen über dem Panel (Bildausschnitt)
const SPRITE_FPS := 15.0                    # Figur auf Zweien (30 fps / 2)

# Lagen im Hintergrund (Panelkoordinaten, im aufbereiteten bg.png gemessen)
const LAMP := Vector2(1076, 150)
const LAMP_RECT := Rect2(1059, 139, 34, 22)
const LANTERN := Vector2(705, 362)
const CHIMNEY := Vector2(87, 193)

# Dachs im Hauptpanel (Panelkoordinaten). Vorschub = Rückweg des Standfußes je Laufbild:
# 0,367 m je Zyklus / 8 Bilder × 109 px/m = 5,0 px (render.json / badger.json).
const FEET_Y := 636.0
const X0 := 20.0
const STEP_PX := 5.0
const WALK_FRAMES := 59     # Laufbilder 0..58; Bild 58 ist Zyklusbild 2 (linker Fuß steht bei +2 px)
const STOP_SHIFT := 2.0     # Standbild hat beide Fersen bei 0 px: 2 px nachrücken, damit der Standfuß stehen bleibt
const F_TURN := 59          # Bilder 59..63: Stand seitlich, dann Drehung zur Kamera
const F_WAVE := 64          # Bilder 64..86: Winken (23 Bilder)
const F_IDLE := 87          # danach Idle in Schleife (30 Bilder)

# Nahaufnahme-Einschub (Bildschirmkoordinaten) und Oberfläche
# Abstände: Einschub-Steg 10 px neben dem Bildunterschrift-Kasten, 15 px links vom Laternenarm; Leiste unter dem
# Panel im Papierrand (8 px Steg), damit Kairand, Taurolle und Kisten ganz sichtbar bleiben.
const INSET_POS := Vector2(406, 30)
const INSET_H := 299                        # Brustbild unten um 20 px gekürzt: Leuchtstriche der Laterne frei
const CAPTION_RECT := Rect2(14, 14, 376, 74)
const STRIP_RECT := Rect2(14, 662, 1252, 46)
const T_BALLOON := 4.36
const T_CHOICE := 4.6
const T_PARSER := 4.45

var t := 0.0
var font: FontFile
var badger: Sprite2D
var shadow: Ellipse
var cu: Sprite2D
var inset_root: Control
var balloon: Balloon
var choice_labels: Array[Label] = []
var parser: Label
var cursor: ColorRect
var sheets := {}
var cu_sheets := {}
var meta := {}
var cu_meta := {}
var fx: Array[Node2D] = []


func _ready() -> void:
	font = load("res://fonts/ComicNeue-Bold.ttf")
	meta = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger.json"))
	cu_meta = JSON.parse_string(FileAccess.get_file_as_string("res://art/closeup.json"))
	for row in ["walk", "turn", "wave", "idle"]:
		sheets[row] = load("res://art/badger_%s.png" % row)
	for row in ["wave", "idle"]:
		cu_sheets[row] = load("res://art/closeup_%s.png" % row)
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED

	# Papier (Hintergrundfarbe des Projekts) und Hauptpanel mit Beschnitt
	var clip := Control.new()
	clip.position = PANEL.position
	clip.size = PANEL.size
	clip.clip_contents = true
	add_child(clip)
	# Alles in Hintergrundkoordinaten (bg.png, bg_layout.json) hängt an "world"; das Panel zeigt die Zeilen
	# VIEW_DY bis VIEW_DY + PANEL.size.y.
	var world := Node2D.new()
	world.position = Vector2(0, -VIEW_DY)
	clip.add_child(world)
	var bg := Sprite2D.new()
	bg.texture = load("res://art/bg.png")
	bg.centered = false
	world.add_child(bg)

	var glints := Glints.new()
	glints.setup(bg.texture.get_image(), rng)
	var beam := Beam.new()
	var lantern := LanternFx.new()
	lantern.setup(rng)
	var smoke := Smoke.new()
	smoke.setup(rng)
	var gulls := Gulls.new()
	for n: Node2D in [glints, beam, lantern, smoke, gulls]:
		world.add_child(n)
		fx.append(n)

	shadow = Ellipse.new()
	shadow.rx = 30.0
	shadow.ry = 5.0
	shadow.color = Color(0.27, 0.2, 0.24, 0.3)
	world.add_child(shadow)
	badger = Sprite2D.new()
	badger.centered = false
	badger.offset = -Vector2(meta["anchor"][0], meta["anchor"][1]).round()
	world.add_child(badger)

	# Panelrahmen: schwarze Kontur über dem Papierrand
	var frame := Box.new()
	frame.rect = PANEL.grow(2.0)
	frame.fill = Color(0, 0, 0, 0)
	frame.width = 4.0
	add_child(frame)

	_build_inset()
	_build_caption()
	_build_strip()

	balloon = Balloon.new()
	balloon.center = INSET_POS + Vector2(140, 46)
	balloon.radii = Vector2(130, 36)       # ganz im Einschub: 8 px Abstand zu dessen Rahmen
	balloon.tip = INSET_POS + Vector2(178, 104)
	balloon.font = font
	balloon.text = "AM KAI WARTET EIN\nPAKET AUF DICH."
	balloon.visible = false
	add_child(balloon)
	balloon.setup()
	# Prüfläufe (scripts/probe_feet.py): Figur bzw. Schatten ausblenden, um die Figur per Differenzbild zu messen
	var args := OS.get_cmdline_user_args()
	if "--probe-no-shadow" in args or "--probe-no-badger" in args:
		shadow.hide()
	if "--probe-no-badger" in args:
		badger.hide()
	_update()


func _build_inset() -> void:
	var fw: int = cu_meta["frame_size"][0]
	var fh: int = cu_meta["frame_size"][1]
	var r := Rect2(INSET_POS, Vector2(fw, INSET_H))
	inset_root = Control.new()
	inset_root.position = Vector2.ZERO
	inset_root.visible = false
	add_child(inset_root)
	var gutter := Box.new()             # weißer Steg um den Einschub, wie im Album
	gutter.rect = r.grow(5.0)
	gutter.fill = Color8(250, 247, 238)
	gutter.width = 0.0
	inset_root.add_child(gutter)
	var clip := Control.new()
	clip.position = r.position
	clip.size = r.size
	clip.clip_contents = true
	inset_root.add_child(clip)
	# Hintergrund der Nahaufnahme: zwei flache Flächen (Abendhimmel, Meer) und eine Horizontlinie, wie im Album
	var sky := ColorRect.new()
	sky.size = Vector2(fw, INSET_H)
	sky.color = Color8(245, 168, 113)
	clip.add_child(sky)
	var sea := ColorRect.new()
	sea.position = Vector2(0, round(0.64 * fh))
	sea.size = Vector2(fw, INSET_H - sea.position.y)
	sea.color = Color8(104, 136, 156)
	clip.add_child(sea)
	var hz := ColorRect.new()
	hz.position = Vector2(0, sea.position.y - 1)
	hz.size = Vector2(fw, 2)
	hz.color = INK
	clip.add_child(hz)
	cu = Sprite2D.new()
	cu.centered = false
	clip.add_child(cu)
	var border := Box.new()
	border.rect = r.grow(LINE_W / 2.0)
	border.fill = Color(0, 0, 0, 0)
	border.width = LINE_W
	inset_root.add_child(border)


func _label(text: String, size: int, color: Color, pos: Vector2) -> Label:
	var l := Label.new()
	var s := LabelSettings.new()
	s.font = font
	s.font_size = size
	s.font_color = color
	s.line_spacing = -2.0
	l.label_settings = s
	l.text = text
	l.position = pos
	add_child(l)
	return l


func _build_caption() -> void:
	var cap := Box.new()
	cap.rect = CAPTION_RECT
	cap.fill = CAPTION_FILL
	cap.width = LINE_W
	add_child(cap)
	_label("HAFEN VON LORNHOLM", 15, Color8(120, 52, 30), CAPTION_RECT.position + Vector2(16, 9))
	_label("DIE LATERNE FLACKERT IM WIND.", 22, INK, CAPTION_RECT.position + Vector2(16, 31))


func _build_strip() -> void:
	var strip := Box.new()
	strip.rect = STRIP_RECT
	strip.fill = BOX_FILL
	strip.width = LINE_W
	add_child(strip)
	var x := STRIP_RECT.position.x + 18.0
	var y := STRIP_RECT.position.y + 11.0
	var items := ["ZUM LEUCHTTURM GEHEN", "DAS PAKET ANSEHEN", "MIT DEM DACHS SPRECHEN"]
	for i in items.size():
		var badge := NumberBadge.new()
		badge.center = Vector2(x + 11, y + 12)
		badge.number = str(i + 1)
		badge.font = font
		add_child(badge)
		var l := _label(items[i], 19, INK, Vector2(x + 28, y + 1))
		choice_labels.append(l)
		x += 28 + font.get_string_size(items[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x + 40
	parser = _label("> NIMM PAKET", 19, INK, Vector2(STRIP_RECT.end.x - 190, y + 1))
	parser.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	parser.visible_characters = 2
	cursor = ColorRect.new()
	cursor.size = Vector2(10, 17)
	cursor.color = INK
	add_child(cursor)


func _process(delta: float) -> void:
	t += delta
	_update()


func _update() -> void:
	for n in fx:
		n.set("t", t)
		n.queue_redraw()
	var f := int(floor(t * SPRITE_FPS + 0.0001))
	var row := "walk"
	var i := 0
	var x := X0
	if f < WALK_FRAMES:
		i = f % 8
		x = X0 + STEP_PX * f
	else:
		x = X0 + STEP_PX * (WALK_FRAMES - 1) + STOP_SHIFT
		if f < F_WAVE:
			row = "turn"
			i = f - F_TURN
		elif f < F_IDLE:
			row = "wave"
			i = f - F_WAVE
		else:
			row = "idle"
			i = (f - F_IDLE) % 30
	_set_frame(badger, sheets[row], meta["rows"][row]["frames"], i)
	badger.position = Vector2(round(x), FEET_Y)
	shadow.position = badger.position + Vector2(2, 1)

	# Nahaufnahme: gleiche Bilder wie die Figur im Panel, ab dem Winken
	inset_root.visible = f >= F_WAVE
	if f >= F_WAVE:
		var crow := "wave" if f < F_IDLE else "idle"
		var ci := f - F_WAVE if f < F_IDLE else (f - F_IDLE) % 30
		_set_frame(cu, cu_sheets[crow], cu_meta["rows"][crow]["frames"], ci)
		cu.position = Vector2.ZERO

	balloon.visible = t >= T_BALLOON
	if balloon.visible:
		# zwei Bilder lang leicht kleiner: Sprechblase "springt" auf
		balloon.scale_k = 0.9 if t < T_BALLOON + 2.0 / 30.0 else 1.0
		balloon.queue_redraw()

	for k in choice_labels.size():
		choice_labels[k].label_settings.font_color = RED if (k == 1 and t >= T_CHOICE) else INK
	var typed := clampi(int((t - T_PARSER) * 18.0), 0, 10) if t >= T_PARSER else 0
	parser.visible_characters = 2 + typed
	var shown := parser.text.substr(0, 2 + typed)
	var w := font.get_string_size(shown, HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x
	cursor.position = parser.position + Vector2(w + 3, 4)
	cursor.visible = fmod(t, 0.8) < 0.5 or (t >= T_PARSER and typed < 10)


func _set_frame(s: Sprite2D, tex: Texture2D, frames: int, i: int) -> void:
	if s.texture != tex:
		s.texture = tex
		s.hframes = frames
	s.frame = i


# ---------------------------------------------------------------------------------------------------------------
# Zeichen-Bausteine. Jede Form: flache Füllung, Kontur in INK (Kästen LINE_W, gezeichnete Effekte FX_LINE_W).

class Box extends Node2D:
	var rect := Rect2()
	var fill := Color.WHITE
	var width := 3.0

	func _draw() -> void:
		if fill.a > 0.0:
			draw_rect(rect, fill)
		if width > 0.0:
			draw_rect(rect, INK, false, width)


class Ellipse extends Node2D:
	var rx := 10.0
	var ry := 4.0
	var color := Color.BLACK

	func _draw() -> void:
		var pts := PackedVector2Array()
		for k in 32:
			var a := TAU * k / 32.0
			pts.append(Vector2(cos(a) * rx, sin(a) * ry))
		draw_colored_polygon(pts, color)


class NumberBadge extends Node2D:
	var center := Vector2.ZERO
	var number := "1"
	var font: Font

	func _draw() -> void:
		draw_circle(center, 11.0, INK, true, -1.0, true)
		var w := font.get_string_size(number, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x
		draw_string(font, center + Vector2(-w / 2.0, 6), number, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color8(253, 250, 241))


class Balloon extends Node2D:
	var center := Vector2.ZERO
	var radii := Vector2(100, 40)
	var tip := Vector2.ZERO
	var text := ""
	var font: Font
	var scale_k := 1.0
	var label: Label

	func setup() -> void:
		label = Label.new()
		var s := LabelSettings.new()
		s.font = font
		s.font_size = 21
		s.font_color = INK
		s.line_spacing = -3.0
		label.label_settings = s
		label.text = text
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		label.size = radii * 2.0
		label.position = center - radii + Vector2(0, -1)
		add_child(label)

	func _draw() -> void:
		var r := radii * scale_k
		var d := (tip - center)
		var am := atan2(d.y / r.y, d.x / r.x)
		var spread := 0.2
		var pts := PackedVector2Array()
		var n := 72
		for k in n + 1:
			var a := am + spread + (TAU - 2.0 * spread) * k / n
			pts.append(center + Vector2(cos(a) * r.x, sin(a) * r.y))
		pts.append(center + (tip - center) * scale_k)
		draw_colored_polygon(pts, Color8(253, 251, 245))
		var outline := pts.duplicate()
		outline.append(pts[0])
		draw_polyline(outline, INK, LINE_W, true)
		label.scale = Vector2.ONE * scale_k
		label.pivot_offset = radii


class Beam extends Node2D:
	## Drehendes Leuchtfeuer als flacher, heller Keil (wie eine Rasterfläche im Druck) mit Tuschekontur.
	const PERIOD := 7.0
	const TH0 := 1.265          # Phase: zur Kamera bei 0,34 s, nach rechts bei 2,1 s, voll nach links bei 5,6 s
	const LENGTH := 430.0
	var t := 0.0

	func _draw() -> void:
		var th := TH0 + TAU * t / PERIOD
		var c := cos(th)
		var s := sin(th)
		var dx := -1.0 if c > 0.0 else 1.0
		var L := LENGTH * absf(c)
		if L > 10.0:
			# drei flache Tonstufen (wie Raster im Druck) statt Verlauf; Kontur nur an den ersten beiden
			var o := LAMP + Vector2(dx * 15.0, 0)
			var a := 0.46 if s >= 0.0 else 0.3
			var steps := [[0.0, 0.55, 1.0], [0.55, 0.8, 0.62], [0.8, 1.0, 0.3]]
			for st in steps:
				var u0: float = st[0]
				var u1: float = st[1]
				var h0 := 7.0 + 25.0 * u0
				var h1 := 7.0 + 25.0 * u1
				var p0 := o + Vector2(dx * L * u0, 0)
				var p1 := o + Vector2(dx * L * u1, 0)
				var pts := PackedVector2Array([p0 + Vector2(0, -h0), p1 + Vector2(0, -h1), p1 + Vector2(0, h1),
					p0 + Vector2(0, h0)])
				draw_colored_polygon(pts, Color(1.0, 0.97, 0.78, a * st[2]))
				if u0 < 0.7:                    # Kegelkanten in voller Tusche und Zeichenlinienstärke
					draw_line(pts[0], pts[1], INK, FX_LINE_W, true)
					draw_line(pts[3], pts[2], INK, FX_LINE_W, true)
		# Aufblitzen, wenn der Strahl zur Kamera zeigt: Lampe hell, kurze Leuchtstriche wie im Comic
		if s > 0.8:
			var k := (s - 0.8) / 0.2
			draw_rect(LAMP_RECT, Color(1.0, 1.0, 0.86, 0.85 * k))
			for j in 8:
				var a2 := TAU * j / 8.0 + 0.39
				var v := Vector2(cos(a2), sin(a2) * 0.9)
				draw_line(LAMP + v * 27.0, LAMP + v * (27.0 + 12.0 * k), INK, FX_LINE_W, true)


class LanternFx extends Node2D:
	## Flackern: flacher Lichthof in zwei Stufen, Radius springt 10-mal pro Sekunde; Leuchtstriche um die Laterne.
	var t := 0.0
	var rnd := PackedFloat32Array()
	const ANGLES := [35.0, 60.0, 85.0, 110.0, 135.0, 160.0]   # nur nach unten: oben Arm, links Einschub, rechts Pfahl

	func setup(rng: RandomNumberGenerator) -> void:
		for k in 400:
			rnd.append(rng.randf())

	func _draw() -> void:
		var step := int(floor(t * 10.0 + 0.0001))
		var u := rnd[step % 200]
		var r := 30.0 + 7.0 * u
		draw_circle(LANTERN, r, Color(1.0, 0.92, 0.5, 0.24), true, -1.0, true)
		draw_circle(LANTERN, r * 0.64, Color(1.0, 0.96, 0.7, 0.22), true, -1.0, true)
		for j in ANGLES.size():
			if rnd[200 + (step * 7 + j * 13) % 200] < 0.38:
				continue
			var a: float = deg_to_rad(ANGLES[j])
			var v := Vector2(cos(a), sin(a))
			var r0 := 38.0 + 3.0 * u
			draw_line(LANTERN + v * r0, LANTERN + v * (r0 + 10.0), INK, FX_LINE_W, true)


class Smoke extends Node2D:
	## Comic-Rauch: runde Wölkchen mit gemeinsamer Außenkontur (erst alle Konturen, dann alle Füllungen).
	const INTERVAL := 0.42
	const LIFE := 3.3
	const COLOR := Color8(229, 225, 233)
	var t := 0.0
	var phase := PackedFloat32Array()

	func setup(rng: RandomNumberGenerator) -> void:
		for k in 64:
			phase.append(rng.randf_range(0.0, TAU))

	func _puffs() -> Array:
		var out := []
		var k0 := int(floor((t - LIFE) / INTERVAL))
		for k in range(k0, int(floor(t / INTERVAL)) + 1):
			var age := t - k * INTERVAL
			if age < 0.0 or age > LIFE:
				continue
			var ph := phase[posmod(k, 64)]
			# flacher Anstieg mit Wind nach rechts: bleibt 8 px unter dem Bildunterschrift-Kasten
			var p := CHIMNEY + Vector2(12.0 * age + 3.0 * age * age + sin(age * 2.2 + ph) * 2.5, -18.0 * age)
			var r := 4.0 + 10.0 * pow(age / LIFE, 0.6)
			if age > LIFE - 0.3:
				r *= (LIFE - age) / 0.3
			out.append([p, r])
		return out

	func _draw() -> void:
		var ps := _puffs()
		for q in ps:
			draw_circle(q[0], q[1] + FX_LINE_W, INK, true, -1.0, true)
		for q in ps:
			draw_circle(q[0], q[1], COLOR, true, -1.0, true)


class Gulls extends Node2D:
	## Zwei Möwen als Comic-Kürzel: weiße Flügel mit schwarzer Kontur, 4 Flügelstellungen bei 10 Bildern/s.
	var t := 0.0
	const BIRDS := [[960.0, 300.0, 46.0, 0], [640.0, 262.0, 54.0, 2]]   # x0, y, Tempo nach links, Phasenversatz
	const FLAP := [1.0, 0.35, -0.55, 0.35]

	func _wing(o: Vector2, side: float, a: float, s: float) -> PackedVector2Array:
		return PackedVector2Array([o + Vector2(0, -1.5) * s, o + Vector2(side * 6.0, -5.0 * a - 1.0) * s,
			o + Vector2(side * 13.0, -2.0 * a + 1.0) * s, o + Vector2(side * 6.0, -5.0 * a + 2.2) * s,
			o + Vector2(0, 1.8) * s])

	func _draw() -> void:
		var fr := int(floor(t * 10.0 + 0.0001))
		for b in BIRDS:
			var o := Vector2(b[0] - b[2] * t, b[1] + sin(t * 1.3 + b[3]) * 3.0).round()
			var a: float = FLAP[(fr + b[3]) % 4]
			var s := 1.7
			for side in [-1.0, 1.0]:
				var w := _wing(o, side, a, s)
				draw_colored_polygon(w, Color8(250, 250, 246))
				var ol := w.duplicate()
				ol.append(w[0])
				draw_polyline(ol, INK, FX_LINE_W, true)
			draw_circle(o + Vector2(-2.5, 0.5), 3.2, INK, true, -1.0, true)
			draw_circle(o + Vector2(-2.5, 0.5), 2.0, Color8(250, 250, 246), true, -1.0, true)


class Glints extends Node2D:
	## Glitzern auf dem Wasser: kurze weiße Striche auf gemessenen Wasserflächen, die 6-mal pro Sekunde wechseln.
	var t := 0.0
	var marks := []

	func setup(img: Image, rng: RandomNumberGenerator) -> void:
		var water := Color8(104, 136, 156)
		var tries := 0
		while marks.size() < 26 and tries < 4000:
			tries += 1
			var p := Vector2(rng.randf_range(580, 1010), rng.randf_range(408, 596)).round()
			var L := rng.randf_range(8.0, 20.0)
			var ok := true
			for dx in range(-int(L / 2.0) - 3, int(L / 2.0) + 4, 2):
				for dy in [-3, 0, 3]:
					var c := img.get_pixel(clampi(int(p.x) + dx, 0, img.get_width() - 1), int(p.y) + dy)
					if absf(c.r - water.r) + absf(c.g - water.g) + absf(c.b - water.b) > 0.12:
						ok = false
			if ok:
				marks.append([p, L, rng.randi_range(0, 5)])

	func _draw() -> void:
		var step := int(floor(t * 6.0 + 0.0001))
		for m in marks:
			if (step + m[2]) % 6 < 3:
				var p: Vector2 = m[0]
				draw_line(p - Vector2(m[1] / 2.0, 0), p + Vector2(m[1] / 2.0, 0), Color8(236, 242, 246), 2.0)

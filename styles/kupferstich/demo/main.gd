extends Node2D
## Kupferstich & Radierung – Hafen von Lornholm (Katalogeintrag "kupferstich").
##
## Eine Buchseite: oben die Bildtafel als Stich mit Plattenrand, darunter der Text mit Initiale.
## Die Tafel ist ein KI-Stich (gpt-image), als Tuschedichte aufbereitet (scripts/build_plate.py) und im Shader
## gedruckt; alle Umgebungseffekte verändern nur die Linien: Licht dünnt sie aus (Laterne, Leuchtturmstrahl,
## Glitzern), das Wasser wellt sie, der Rauch ist als gestochene Ballen gezeichnet, die Möwen als Federstriche.
## Der Dachs ist ein KI-Laufbogen in Spielgröße (scripts/build_badger.py), gedruckt auf dasselbe Papier.
## Ablauf der Figur steht als Tabelle in art/timeline.json (scripts/choreo.py). Alles hängt nur von der
## aufsummierten Zeit t ab; Zufall nur aus RandomNumberGenerator mit festem Seed.

const SEED := 18711011
const INK := Color(0.169, 0.125, 0.09)
const FPS := 30.0
const T_PARSER := 4.2          # Parserzeile beginnt zu tippen
const TYPE_CPS := 14.0
const T_CHOICE := 4.75         # Antwort 2 wird angewählt (Unterstreichung)
const LH_PERIOD := 6.0         # Umlauf des Leuchtfeuers
const LH_LEFT_AT := 5.0        # zu diesem Zeitpunkt zeigt der Strahl ganz nach links (Poster)
const BORDER := 2.0            # Breite der gestochenen Einfassungslinie in plate_ink.png (Spalten/Zeilen 0–1)

var t := 0.0
var lay: Dictionary
var scene: Dictionary
var tl: Dictionary
var plate_mat: ShaderMaterial
var badger_mat: ShaderMaterial
var badger: Sprite2D
var shadow: Sprite2D
var gulls: Gulls
var swash: Swash
var parser: Label
var cursor: ColorRect
var flicker := PackedFloat32Array()
var plate_pos := Vector2.ZERO
var lantern_screen := Vector2.ZERO
var probe_badger_only := false
var probe_no_badger := false
var probe_log := false
var f_rm: FontFile
var f_it: FontFile
var f_sc: FontFile
var f_cap: FontFile


func _json(path: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	probe_badger_only = "--probe-badger-only" in args
	probe_no_badger = "--probe-no-badger" in args
	probe_log = "--probe-log" in args
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in 400:
		flicker.append(rng.randf())
	lay = _json("res://art/layout.json")
	scene = _json("res://art/scene.json")
	tl = _json("res://art/timeline.json")
	var bmeta := _json("res://art/badger.json")
	var orn := _json("res://art/ornaments.json")
	f_rm = load("res://fonts/IMFeENrm28P.ttf")
	f_it = load("res://fonts/IMFeENit28P.ttf")
	f_sc = load("res://fonts/IMFeENsc28P.ttf")
	f_cap = load("res://fonts/IMFeFCrm28P.ttf")

	var pr: Array = lay["plate"]
	plate_pos = Vector2(pr[0], pr[1])
	var paper_tex: Texture2D = load("res://art/paper.png")

	# Papier
	var paper := Sprite2D.new()
	paper.texture = paper_tex
	paper.centered = false
	add_child(paper)

	# Bildtafel: die Platte selbst (mit gestochener Einfassungslinie am Rand) liegt frei; Möwen, Schatten und Dachs
	# liegen in einem Clip, der um die Breite der Einfassungslinie eingerückt ist, damit die papiergefüllte Silhouette
	# des Dachses am Tafelrand die Linie nicht überdeckt. "stage" verschiebt zurück: Kinder nutzen Plattenkoordinaten.
	var clip := Control.new()
	clip.position = plate_pos + Vector2(BORDER, BORDER)
	clip.size = Vector2(pr[2], pr[3]) - Vector2(2.0 * BORDER, 2.0 * BORDER)
	clip.clip_contents = true
	clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var stage := Node2D.new()
	stage.position = -Vector2(BORDER, BORDER)
	clip.add_child(stage)

	plate_mat = ShaderMaterial.new()
	plate_mat.shader = load("res://shaders/plate.gdshader")
	plate_mat.set_shader_parameter("mask_tex", load("res://art/plate_mask.png"))
	plate_mat.set_shader_parameter("ink_color", INK)
	plate_mat.set_shader_parameter("plate_size", Vector2(pr[2], pr[3]))
	var lan: Array = scene["lantern"]["center"]
	var lamp: Array = scene["lamp"]["center"]
	var win: Array = scene["window"]["center"]
	plate_mat.set_shader_parameter("lantern_pos", Vector2(lan[0], lan[1]))
	plate_mat.set_shader_parameter("lamp_pos", Vector2(lamp[0], lamp[1]))
	plate_mat.set_shader_parameter("window_pos", Vector2(win[0], win[1]))
	plate_mat.set_shader_parameter("horizon_y", float(scene["horizon_y"]))
	lantern_screen = plate_pos + Vector2(lan[0], lan[1])
	var plate := Sprite2D.new()
	plate.texture = load("res://art/plate_ink.png")
	plate.centered = false
	plate.material = plate_mat
	plate.position = plate_pos
	add_child(plate)
	add_child(clip)

	gulls = Gulls.new()
	gulls.ink = INK
	stage.add_child(gulls)

	shadow = Sprite2D.new()
	shadow.texture = load("res://art/shadow.png")
	shadow.centered = false
	shadow.modulate = Color(INK, 0.9)
	stage.add_child(shadow)

	badger_mat = ShaderMaterial.new()
	badger_mat.shader = load("res://shaders/badger.gdshader")
	badger_mat.set_shader_parameter("paper_tex", paper_tex)
	badger_mat.set_shader_parameter("ink_color", INK)
	badger_mat.set_shader_parameter("lantern_screen", lantern_screen)
	badger = Sprite2D.new()
	badger.texture = load("res://art/badger.png")
	badger.hframes = (bmeta["frames"] as Array).size()
	badger.centered = false
	badger.material = badger_mat
	stage.add_child(badger)

	_build_text(orn)

	if probe_badger_only:
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
		paper.visible = false
		plate.visible = false
		gulls.visible = false
		shadow.visible = false
		for c in get_children():
			if c is Control and c != clip:
				c.visible = false
		badger_mat.set_shader_parameter("light_amount", 0.0)
	if probe_no_badger:
		badger.visible = false
		shadow.visible = false
	_apply(0.0)


func _build_text(orn: Dictionary) -> void:
	var page := Control.new()
	page.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(page)

	# Initiale: gestochener Rahmen (KI-Ornament) + Buchstabe aus der Schrift
	var ini: Dictionary = orn["initial"]
	var ipos := Vector2(86, 574)
	var frame := TextureRect.new()
	frame.texture = load("res://art/orn_initial.png")
	frame.position = ipos
	frame.size = Vector2(ini["w"], ini["h"])
	frame.modulate = INK
	page.add_child(frame)
	var field: Array = ini["field"]
	var letter := Initial.new()
	letter.font = f_cap
	letter.ink = INK
	letter.rect = Rect2(ipos + Vector2(field[0], field[1]), Vector2(field[2], field[3]))
	page.add_child(letter)

	var x0 := ipos.x + float(ini["w"]) + 16.0
	# Kolumnentitel: Ort in Kapitälchen, gesperrt
	var head_font := FontVariation.new()
	head_font.base_font = f_sc
	head_font.spacing_glyph = 2
	var head := Label.new()
	head.text = "Hafen von Lornholm"
	head.position = Vector2(x0, 568)
	_style(head, head_font, 21)
	page.add_child(head)

	# Absatz: nach der Initiale das erste Wort in Kapitälchen (Buchsatz)
	var para := RichTextLabel.new()
	para.bbcode_enabled = true
	para.fit_content = true
	para.scroll_active = false
	para.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	para.position = Vector2(x0, 600)
	para.size = Vector2(500, 80)
	para.mouse_filter = Control.MOUSE_FILTER_IGNORE
	para.add_theme_font_override("normal_font", f_rm)
	para.add_theme_font_size_override("normal_font_size", 25)
	para.add_theme_color_override("default_color", INK)
	para.add_theme_constant_override("line_separation", 2)
	para.text = "[font=res://fonts/IMFeENsc28P.ttf]ie Laterne[/font] flackert im Wind. Am Kai wartet ein Paket auf dich."
	page.add_child(para)

	# Zierlinie unter dem Absatz (Schlussstück)
	var rule := TextureRect.new()
	rule.texture = load("res://art/orn_rule.png")
	var rw: float = orn["rule"]["w"]
	rule.position = Vector2(x0 + (500.0 - rw) * 0.5, 672)
	rule.size = Vector2(rw, orn["rule"]["h"])
	rule.modulate = INK
	page.add_child(rule)

	# Schlussvignette rechts unten (gleicht die Initiale links aus)
	var vig := TextureRect.new()
	vig.texture = load("res://art/orn_vignette.png")
	vig.size = Vector2(orn["vignette"]["w"], orn["vignette"]["h"])
	vig.position = Vector2(1196.0 - vig.size.x, 700.0 - vig.size.y)
	vig.modulate = INK
	page.add_child(vig)

	# Senkrechte Doppellinie zwischen den Spalten
	var sep := Rules.new()
	sep.ink = INK
	sep.x = 736.0
	sep.y0 = 578.0
	sep.y1 = 700.0
	page.add_child(sep)

	# Auswahl: römische Ziffern, Kursive
	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	var nums := ["I.", "II.", "III."]
	var cy := 570.0
	for i in 3:
		var n := Label.new()
		n.text = nums[i]
		n.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		n.position = Vector2(760, cy + i * 31.0)
		n.size = Vector2(40, 30)
		_style(n, f_rm, 23)
		page.add_child(n)
		var c := Label.new()
		c.text = choices[i]
		c.position = Vector2(810, cy + i * 31.0)
		_style(c, f_it, 24)
		page.add_child(c)
	swash = Swash.new()
	swash.ink = INK
	swash.from = Vector2(810, cy + 31.0 + 28.0)
	swash.to = Vector2(810 + f_it.get_string_size(choices[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 24).x + 6, cy + 31.0 + 28.0)
	page.add_child(swash)

	parser = Label.new()
	parser.text = "> nimm paket"
	parser.position = Vector2(772, 668)
	parser.visible_characters = 0
	parser.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	_style(parser, f_it, 24)
	page.add_child(parser)
	cursor = ColorRect.new()
	cursor.color = INK
	cursor.size = Vector2(2, 22)
	cursor.mouse_filter = Control.MOUSE_FILTER_IGNORE
	page.add_child(cursor)


func _style(l: Label, f: Font, size: int) -> void:
	var ls := LabelSettings.new()
	ls.font = f
	ls.font_size = size
	ls.font_color = INK
	l.label_settings = ls
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	t += delta
	_apply(t)


func _apply(tt: float) -> void:
	var tick := int(floor(tt * FPS + 0.5))
	var line: Array = tl["timeline"]
	var e: Dictionary = line[min(tick, line.size() - 1)]
	badger.frame = int(e["f"])
	badger.position = Vector2(e["x"], e["y"])
	if probe_log:
		print("PROBE tick=%d frame=%d x=%d drawn=%d" % [tick, badger.frame, int(e["x"]), Engine.get_frames_drawn()])
	var fw: float = tl["frame_w"]
	shadow.position = Vector2(round(float(e["x"]) + fw * 0.5 - 58.0), float(tl["feet_y"]) - 9.0)

	# Laterne flackert: alle 3 Takte (10-mal pro Sekunde) ein neuer Zufallswert, zu dem Stärke und Radius über
	# 2 Takte überblenden (Takt 0: alter Wert, 1: Mitte, 2: neuer Wert). Kleine Spanne, damit der Schein nicht
	# als Papierscheibe pulsiert. Fenster unruhig.
	var fi := floori(tick / 3.0)
	var fu := [0.0, 0.5, 1.0][tick % 3] as float
	var lk := lerpf(0.92 + 0.08 * flicker[(fi + 396) % 397], 0.92 + 0.08 * flicker[fi % 397], fu)
	var lr := lerpf(66.0 + 16.0 * flicker[(fi + 130) % 397], 66.0 + 16.0 * flicker[(fi + 131) % 397], fu)
	plate_mat.set_shader_parameter("lantern_k", lk)
	plate_mat.set_shader_parameter("lantern_r", lr)
	plate_mat.set_shader_parameter("window_k", 0.45 + 0.2 * flicker[(fi + 61) % 397])
	badger_mat.set_shader_parameter("lantern_k", lk)
	plate_mat.set_shader_parameter("t", tt)
	plate_mat.set_shader_parameter("glint_step", floor(tt * 6.0))

	# Leuchtfeuer: Umlauf in LH_PERIOD s, Strahl als Projektion, Aufblitzen zur Kamera
	var phi := TAU * (tt - LH_LEFT_AT) / LH_PERIOD + 1.5 * PI
	var sp := sin(phi)
	var cp := cos(phi)
	plate_mat.set_shader_parameter("beam_dir", -1.0 if sp < 0.0 else 1.0)
	plate_mat.set_shader_parameter("beam_len", 760.0 * abs(sp))
	plate_mat.set_shader_parameter("beam_k", (0.75 + 0.25 * max(cp, 0.0)) * smoothstep(0.08, 0.3, abs(sp)))
	plate_mat.set_shader_parameter("flash_k", pow(max(cp, 0.0), 10.0))

	# Rauch: alle 0,8 s ein Ballen aus zwei Bögen, Lebensdauer 4 s, vorgewärmt; der Wind treibt ihn flach nach
	# rechts (über dem Schornstein liegen nur 46 px Himmel bis zum Plattenrand)
	var ch: Array = scene["chimney_top"]
	var puffs := PackedVector4Array()
	var spawn := 0.8
	var life := 4.0
	var k0 := int(floor((tt - life) / spawn)) + 1
	for k in range(k0, k0 + 6):
		var age := tt - k * spawn
		if age < 0.0 or age > life or puffs.size() >= 12:
			continue
		var u := age / life
		var x := float(ch[0]) + 2.0 + 16.0 * age + 2.6 * age * age
		var y := float(ch[1]) - 6.0 - 7.0 * age + 0.8 * age * age + 2.0 * sin(age * 1.9 + 2.0 * k)
		var r := 5.0 + 3.4 * age
		var a := smoothstep(0.0, 0.3, age) * (1.0 - smoothstep(0.5, 1.0, u))
		puffs.append(Vector4(x, y, r, a))
		puffs.append(Vector4(x - 0.75 * r, y + 0.3 * r + 1.0, r * 0.68, a))
	plate_mat.set_shader_parameter("puffs", puffs)
	plate_mat.set_shader_parameter("puff_count", puffs.size())

	gulls.t = tt
	gulls.queue_redraw()

	# Oberfläche
	swash.k = clamp((tt - T_CHOICE) / 0.25, 0.0, 1.0)
	swash.queue_redraw()
	var n := int(clamp(floor((tt - T_PARSER) * TYPE_CPS), 0, parser.text.length()))
	parser.visible_characters = n
	var w := f_it.get_string_size(parser.text.substr(0, n), HORIZONTAL_ALIGNMENT_LEFT, -1, 24).x
	cursor.position = parser.position + Vector2(w + 3.0, 6.0)
	cursor.visible = tt >= T_PARSER - 0.6 and fmod(tt, 0.8) < 0.5


class Gulls extends Node2D:
	## Zwei Möwen als gestochene Federstriche: jeder Flügel ein spitz zulaufender Bogen.
	var t := 0.0
	var ink := Color.BLACK

	func _draw() -> void:
		# Flügelschlag in 6 Stellungen; die Stellung springt 10- bzw. 6-mal pro Sekunde (auf Dreien / Fünfen)
		_gull(Vector2(1110.0 - 95.0 * t, 150.0 + 8.0 * sin(t * 0.9)), 21.0, 10.0, 0)
		_gull(Vector2(430.0 + 55.0 * t, 64.0 + 5.0 * sin(t * 1.3 + 1.0)), 13.0, 6.0, 2)

	func _gull(c: Vector2, size: float, fps: float, ph: int) -> void:
		var idx := (int(floor(t * fps + 0.001)) + ph) % 6
		var lift := cos(TAU * float(idx) / 6.0)
		for side in [-1.0, 1.0]:
			var tip := c + Vector2(side * size, -size * 0.35 * lift - size * 0.1)
			var mid := c + Vector2(side * size * 0.45, -size * 0.45 * lift - size * 0.25)
			var pts := PackedVector2Array()
			var n := 9
			for i in n:
				var u := float(i) / float(n - 1)
				pts.append(c.lerp(mid, u).lerp(mid.lerp(tip, u), u))
			_taper(pts, 1.6 * size / 15.0 + 0.4, 0.25)

	func _taper(pts: PackedVector2Array, w0: float, w1: float) -> void:
		var left := PackedVector2Array()
		var right := PackedVector2Array()
		for i in pts.size():
			var u := float(i) / float(pts.size() - 1)
			var dir := (pts[min(i + 1, pts.size() - 1)] - pts[max(i - 1, 0)]).normalized()
			var nrm: Vector2 = Vector2(-dir.y, dir.x) * lerpf(w0, w1, u) * 0.5
			left.append(pts[i] + nrm)
			right.append(pts[i] - nrm)
		right.reverse()
		var poly := left + right
		draw_colored_polygon(poly, ink)
		draw_polyline(poly, Color(ink, 0.5), 0.6, true)


class Swash extends Node2D:
	## Unterstreichung der gewählten Antwort als geschwellte Linie (dick in der Mitte, spitz an den Enden).
	var from := Vector2.ZERO
	var to := Vector2.ZERO
	var k := 0.0
	var ink := Color.BLACK

	func _draw() -> void:
		if k <= 0.0:
			return
		var end := from.lerp(to, k)
		var n := 24
		var top := PackedVector2Array()
		var bot := PackedVector2Array()
		for i in n:
			var u := float(i) / float(n - 1)
			var p := from.lerp(end, u) + Vector2(0, 1.5 * sin(u * PI * 1.0))
			var w := 0.25 + 1.1 * sin(u * PI)
			top.append(p + Vector2(0, -w))
			bot.append(p + Vector2(0, w))
		bot.reverse()
		var poly := top + bot
		draw_colored_polygon(poly, ink)
		draw_polyline(poly, Color(ink, 0.5), 0.6, true)


class Rules extends Node2D:
	## Senkrechte Doppellinie (fett + fein) als Spaltentrenner, wie im Buchsatz.
	var x := 0.0
	var y0 := 0.0
	var y1 := 0.0
	var ink := Color.BLACK

	func _draw() -> void:
		draw_rect(Rect2(x, y0, 2.0, y1 - y0), ink)
		draw_rect(Rect2(x + 5.0, y0, 1.0, y1 - y0), Color(ink, 0.85))


class Initial extends Node2D:
	## Buchstabe der Initiale, in der Mitte des leeren Feldes des gestochenen Rahmens.
	var font: Font
	var rect := Rect2()
	var ink := Color.BLACK

	func _draw() -> void:
		var size := int(rect.size.y * 1.32)
		var w := font.get_string_size("D", HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		var cap := font.get_ascent(size) * 0.66
		var base := Vector2(rect.position.x + (rect.size.x - w) * 0.5, rect.position.y + (rect.size.y + cap) * 0.5)
		draw_string(font, base, "D", HORIZONTAL_ALIGNMENT_LEFT, -1, size, ink)

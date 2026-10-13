extends Node2D
## Buchmalerei & Manuskript – Hafen von Lornholm (Katalogeintrag "buchmalerei").
##
## Eine Seite aus einem Stundenbuch um 1410: links die Miniatur (KI-Bild, gpt-image) in einem Rahmen aus Gold- und
## Farbleiste, rechts die Textspalte in Textura (Texturina) mit roter Initiale auf blauem Fleuronnée, Rubrik in
## Rot und Paragraphenzeichen in Rot und Blau; in allen Rändern Dornblattranken mit Blattgold (Code,
## scripts/build_page.py). Der Dachs-Kurier ist eine KI-Figur in Bedeutungsgröße, als Schnittfigur aus Körper und
## Unterarm gebaut: er gleitet ins Bild, schaukelt dabei leicht und hebt dann die Hand zum Redegestus.
## Blattgold in Miniatur und Seite schimmert (Shader), Wellenkringel kommen und gehen, Rauch steigt, das
## Leuchtfeuer strahlt, die Laterne flackert, zwei Vögel ziehen über den Goldgrund. Alles hängt nur von der
## aufsummierten Zeit t ab; Zufall nur aus RandomNumberGenerator mit festem Seed.

const SEED := 20261013
const INK := Color(0.165, 0.106, 0.075)
const RED := Color(0.698, 0.173, 0.106)
const BLUE := Color(0.165, 0.259, 0.612)
const GOLD := Color(0.95, 0.78, 0.34)
const SMOKE := Color(0.66, 0.66, 0.74)
const WHITE := Color(0.965, 0.94, 0.88)
const RULE := Color(0.62, 0.34, 0.26, 0.20)

const T_GLIDE0 := 0.2          # Dachs gleitet ab hier ins Bild …
const T_GLIDE1 := 2.8          # … und steht hier
const X_START := -150.0        # Fußpunkt in Fensterkoordinaten
const X_END := 246.0
const FOOT_Y := 488.0
const ARM_GLIDE := 14.0        # Unterarm beim Gleiten nach vorn geneigt (Grad, im Uhrzeigersinn)
const T_RAISE := 2.85          # Hand hebt sich zum Redegestus
const T_WRITE := 0.6           # Text beginnt sich zu schreiben
const CPS := 21.0              # Zeichen pro Sekunde
const T_CHOICES := 3.75
const T_PARSER := 4.7
const TYPE_CPS := 12.0
const LINE_H := 35.0
const DROLL_FOOT := Vector2(1080.0, 661.0)   # Fußpunkt der Drolerie auf dem Rankenstiel (build_page.py: y = 658 + 15 sin …)
const BODY_SIZE := 27
const BODY_TEXT := "ie Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."

var t := 0.0
var page_info: Dictionary
var mini_info: Dictionary
var badger_info: Dictionary
var droll_info: Dictionary
var droll_root: Node2D
var droll_mat: ShaderMaterial
var page_mat: ShaderMaterial
var mini_mat: ShaderMaterial
var win_origin := Vector2.ZERO
var badger_root: Node2D
var arm_pivot: Node2D
var body_labels: Array[Label] = []
var body_counts: Array[int] = []
var choice_nodes: Array = []
var parser_label: Label
var parser_mark: Label
var parser_cursor: ColorRect
var parser_font: Font
var flick_vals := PackedFloat32Array()
var probe_no_badger := false
var f_body: FontVariation
var f_rubric: FontVariation
var f_initial: FontVariation


func _json(path: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func _font(wght: float, opsz: float) -> FontVariation:
	var fv := FontVariation.new()
	fv.base_font = load("res://fonts/Texturina-VF.ttf")
	var ts := TextServerManager.get_primary_interface()
	fv.variation_opentype = {ts.name_to_tag("wght"): wght, ts.name_to_tag("opsz"): opsz}
	return fv


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	probe_no_badger = "--probe-no-badger" in args
	for a in args:
		if a.begins_with("--t0="):
			t = float(a.substr(5))
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in 400:
		flick_vals.append(rng.randf())
	page_info = _json("res://art/page.json")
	mini_info = _json("res://art/miniature.json")
	badger_info = _json("res://art/badger.json")
	droll_info = _json("res://art/drollery.json")
	f_body = _font(560, 24)
	f_rubric = _font(700, 30)
	f_initial = _font(820, 72)

	# Seite
	var page := Sprite2D.new()
	page.texture = load("res://art/page.png")
	page.centered = false
	page_mat = ShaderMaterial.new()
	page_mat.shader = load("res://shaders/page.gdshader")
	page_mat.set_shader_parameter("gold_mask", load("res://art/page_gold.png"))
	page.material = page_mat
	add_child(page)

	# Randfigur (Drolerie) im unteren Rand: Hase mit Goldtrompete steht auf der Ranke
	var dfoot := Vector2(droll_info["foot"][0], droll_info["foot"][1])
	var dsize := Vector2(droll_info["size"][0], droll_info["size"][1])
	droll_root = Node2D.new()
	droll_root.position = DROLL_FOOT
	add_child(droll_root)
	var droll := Sprite2D.new()
	droll.texture = load("res://art/drollery.png")
	droll.centered = false
	droll.position = -dfoot
	droll_mat = ShaderMaterial.new()
	droll_mat.shader = load("res://shaders/sprite_gold.gdshader")
	droll_mat.set_shader_parameter("gold_mask", load("res://art/drollery_gold.png"))
	droll_mat.set_shader_parameter("origin", DROLL_FOOT - dfoot)
	droll_mat.set_shader_parameter("size", dsize)
	droll.material = droll_mat
	droll_root.add_child(droll)

	# Miniaturfenster
	var w: Array = page_info["window"]
	win_origin = Vector2(w[0], w[1])
	var win := Control.new()
	win.position = win_origin
	win.size = Vector2(w[2], w[3])
	win.clip_contents = true
	add_child(win)
	var mini := Sprite2D.new()
	mini.texture = load("res://art/miniature.png")
	mini.centered = false
	mini_mat = ShaderMaterial.new()
	mini_mat.shader = load("res://shaders/miniature.gdshader")
	mini_mat.set_shader_parameter("mask_tex", load("res://art/mini_mask.png"))
	mini_mat.set_shader_parameter("nocrest_tex", load("res://art/mini_nocrest.png"))
	mini_mat.set_shader_parameter("origin", win_origin)
	mini_mat.set_shader_parameter("size", Vector2(w[2], w[3]))
	mini.material = mini_mat
	win.add_child(mini)

	var lamp: Array = mini_info["lighthouse_lamp"]
	var lant: Array = mini_info["lantern"]
	var chim: Array = mini_info["chimney_top"]
	win.add_child(Smoke.new(self, Vector2(chim[0], chim[1] - 1.0)))
	win.add_child(Birds.new(self))
	win.add_child(LampRays.new(self, Vector2(lamp[0], lamp[1])))
	win.add_child(LanternRays.new(self, Vector2(lant[0], lant[1])))

	# Dachs: Unterarm hinter dem Körper, dreht um die Manschette
	var foot := Vector2(badger_info["foot"][0], badger_info["foot"][1])
	var pivot := Vector2(badger_info["pivot"][0], badger_info["pivot"][1])
	badger_root = Node2D.new()
	win.add_child(badger_root)
	arm_pivot = Node2D.new()
	arm_pivot.position = pivot - foot
	badger_root.add_child(arm_pivot)
	var arm := Sprite2D.new()
	arm.texture = load("res://art/badger_arm.png")
	arm.centered = false
	arm.position = -pivot
	arm_pivot.add_child(arm)
	var body := Sprite2D.new()
	body.texture = load("res://art/badger_body.png")
	body.centered = false
	body.position = -foot
	badger_root.add_child(body)
	badger_root.visible = not probe_no_badger

	_build_text()
	_update()


# ------------------------------------------------------------------ Text
func _label(text: String, font: Font, size: int, color: Color, pos: Vector2, width := 0.0) -> Label:
	var l := Label.new()
	l.text = text
	var ls := LabelSettings.new()
	ls.font = font
	ls.font_size = size
	ls.font_color = color
	ls.line_spacing = 0
	l.label_settings = ls
	l.position = pos
	if width > 0.0:
		l.size = Vector2(width, 0)
	l.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	add_child(l)
	return l


func _wrap(text: String, widths: Array) -> PackedStringArray:
	var words := text.split(" ")
	var lines := PackedStringArray()
	var cur := ""
	for wd in words:
		var trial := wd if cur == "" else cur + " " + wd
		var maxw: float = widths[min(lines.size(), widths.size() - 1)]
		if f_body.get_string_size(trial, HORIZONTAL_ALIGNMENT_LEFT, -1, BODY_SIZE).x > maxw and cur != "":
			lines.append(cur)
			cur = wd
		else:
			cur = trial
	if cur != "":
		lines.append(cur)
	return lines


func _build_text() -> void:
	var tx: Array = page_info["text"]
	var ini: Array = page_info["initial"]
	var x0: float = tx[0]
	var x1: float = tx[0] + tx[2]
	var ix1: float = ini[0] + ini[2] + 3.0
	add_child(Ruling.new(self, x0, x1, ini[1]))

	# Rubrik (Ort) in Rot
	_label("Hafen von Lornholm", f_rubric, 30, RED, Vector2(x0, tx[1] - 2.0))
	# Initiale: roter Buchstabe mittig im Fleuronnée-Feld
	# Größe und Versatz gemessen: Glyphe 0,69 x Schriftgröße hoch, Oberkante 0,567 x Schriftgröße unter dem Label
	var ini_l := _label("D", f_initial, 112, RED, Vector2(ini[0], ini[1] + ini[3] * 0.5 - 0.692 * 56.0 - 0.567 * 112.0), ini[2])
	ini_l.size = Vector2(ini[2], ini[3])
	ini_l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	ini_l.label_settings.outline_size = 3
	ini_l.label_settings.outline_color = Color(0.36, 0.07, 0.04)
	# Fließtext, die ersten drei Zeilen neben der Initiale, danach volle Breite; Blocksatz
	var widths := [x1 - ix1, x1 - ix1, x1 - ix1, x1 - x0]
	var lines := _wrap(BODY_TEXT, widths)
	var total := 0
	for i in lines.size():
		var lx: float = ix1 if i < 3 else x0
		var lw: float = x1 - lx
		var l := _label(lines[i], f_body, BODY_SIZE, INK, Vector2(lx, ini[1] + i * LINE_H - 1.0), lw)
		# Blocksatz nur, wenn die Zeile ohnehin fast voll ist (sonst klaffen in der schmalen Spalte Lücken)
		var fill := f_body.get_string_size(lines[i], HORIZONTAL_ALIGNMENT_LEFT, -1, BODY_SIZE).x / lw
		if i < lines.size() - 1 and fill > 0.86:
			l.horizontal_alignment = HORIZONTAL_ALIGNMENT_FILL
		body_labels.append(l)
		total += lines[i].length()
		body_counts.append(total)
	# Auswahl mit Paragraphenzeichen in Rot und Blau
	var cy: float = ini[1] + max(lines.size(), 3) * LINE_H + 22.0
	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	for i in choices.size():
		var y := cy + i * LINE_H
		var pc := _label("¶", f_body, BODY_SIZE, RED if i % 2 == 0 else BLUE, Vector2(x0, y))
		var tl := _label(choices[i], f_body, BODY_SIZE, INK, Vector2(x0 + 22.0, y))
		choice_nodes.append([pc, tl])
	# Parserzeile
	var py := cy + choices.size() * LINE_H + 18.0
	parser_mark = _label(">", f_body, BODY_SIZE, RED, Vector2(x0, py))
	parser_label = _label("nimm paket", f_body, BODY_SIZE, INK, Vector2(x0 + 22.0, py))
	parser_font = f_body
	parser_cursor = ColorRect.new()
	parser_cursor.color = INK
	parser_cursor.size = Vector2(2.5, 22.0)
	parser_cursor.position = Vector2(x0 + 24.0, py + 8.0)
	add_child(parser_cursor)


# ------------------------------------------------------------------ Ablauf
func _process(delta: float) -> void:
	t += delta
	_update()


func _ease(u: float) -> float:
	u = clampf(u, 0.0, 1.0)
	return u * u * (3.0 - 2.0 * u)


func flick(k: float) -> float:
	var i := int(floor(k)) % flick_vals.size()
	return flick_vals[i]


func _update() -> void:
	page_mat.set_shader_parameter("t", t)
	mini_mat.set_shader_parameter("t", t)
	mini_mat.set_shader_parameter("flick", flick(t * 10.0))
	droll_mat.set_shader_parameter("t", t)
	# Drolerie bläst: wiegt sich um die Füße
	droll_root.rotation = deg_to_rad(2.2) * sin(TAU * t / 1.3)

	# Dachs gleitet (ohne Schritte, wie eine Figur auf einem Spielbrett) und schaukelt dabei leicht
	var u := (t - T_GLIDE0) / (T_GLIDE1 - T_GLIDE0)
	var x := lerpf(X_START, X_END, _ease(u))
	var speed := 0.0
	if u > 0.0 and u < 1.0:
		speed = 6.0 * u * (1.0 - u) / 1.5
	badger_root.position = Vector2(round(x), FOOT_Y)
	badger_root.rotation = deg_to_rad(1.3) * sin(TAU * t / 0.9) * speed
	# Unterarm: beim Gleiten nach vorn geneigt, dann Redegestus mit kleinen Schlägen
	var arm := ARM_GLIDE + 2.0 * sin(TAU * t / 0.9 + 0.8) * speed
	if t >= T_RAISE:
		var r := _ease((t - T_RAISE) / 0.45)
		var beat := -1.5 + 5.0 * pow(sin(PI * max(0.0, t - T_RAISE - 0.45) / 0.7), 2.0)
		arm = lerpf(ARM_GLIDE, beat, r)
	arm_pivot.rotation = deg_to_rad(arm)

	# Text schreibt sich
	var n := int(floor(max(0.0, t - T_WRITE) * CPS))
	var prev := 0
	for i in body_labels.size():
		body_labels[i].visible_characters = clampi(n - prev, 0, body_counts[i] - prev)
		prev = body_counts[i]
	for i in choice_nodes.size():
		var a := clampf((t - T_CHOICES - i * 0.22) / 0.3, 0.0, 1.0)
		for nd in choice_nodes[i]:
			nd.modulate.a = a
	var k := int(floor(max(0.0, t - T_PARSER) * TYPE_CPS))
	k = clampi(k, 0, parser_label.text.length())
	parser_label.visible_characters = k
	var wdt := parser_font.get_string_size(parser_label.text.substr(0, k), HORIZONTAL_ALIGNMENT_LEFT, -1,
			BODY_SIZE).x
	parser_cursor.position.x = parser_label.position.x + wdt + 3.0
	parser_cursor.visible = t >= T_PARSER - 0.6 and fmod(t, 0.8) < 0.5
	parser_mark.modulate.a = clampf((t - T_PARSER + 0.6) / 0.3, 0.0, 1.0)


# ------------------------------------------------------------------ Zeichnende Knoten
class Ruling extends Node2D:
	## Blasse Linierung der Textspalte wie mit Tinte vorgezogen
	var x0: float
	var x1: float
	var y0: float
	func _init(_m, a: float, b: float, top: float) -> void:
		x0 = a
		x1 = b
		y0 = top
	func _draw() -> void:
		for i in range(-1, 13):
			var y := y0 + i * 35.0 + 27.0
			draw_line(Vector2(x0 - 4.0, y), Vector2(x1 + 4.0, y), Color(0.62, 0.34, 0.26, 0.16), 1.0)
		draw_line(Vector2(x0 - 1.0, y0 - 60.0), Vector2(x0 - 1.0, y0 + 13 * 35.0), Color(0.62, 0.34, 0.26, 0.12), 1.0)
		draw_line(Vector2(x1 + 1.0, y0 - 60.0), Vector2(x1 + 1.0, y0 + 13 * 35.0), Color(0.62, 0.34, 0.26, 0.12), 1.0)


class Smoke extends Node2D:
	## Rauch als gemaltes Band wie in der Buchmalerei: geschlängelt, mit Tuschekontur, flacher Füllung und
	## weißer Glanzlinie; die Welle läuft nach oben, der Wind biegt das Band nach rechts.
	const L := 84.0
	var m
	var src: Vector2
	func _init(main, origin: Vector2) -> void:
		m = main
		src = origin
	func _process(_d: float) -> void:
		queue_redraw()
	func _centre(s: float) -> Vector2:
		var t: float = m.t
		var a := 1.5 + 5.5 * s
		return src + Vector2(38.0 * pow(s, 1.7) + a * sin(TAU * 1.5 * s - t * 2.8), -L * s)
	func _width(s: float) -> float:
		return (2.6 + 5.0 * s) * (1.0 - smoothstep(0.72, 1.0, s)) + 0.6
	func _draw() -> void:
		var n := 90
		for i in n + 1:
			var s := float(i) / n
			draw_circle(_centre(s), _width(s) + 1.3, INK, true, -1.0, true)
		for i in n + 1:
			var s := float(i) / n
			draw_circle(_centre(s), _width(s), SMOKE, true, -1.0, true)
		var hl := PackedVector2Array()
		for i in range(8, 62):
			var s := float(i) / n
			hl.append(_centre(s) + Vector2(-0.45 * _width(s), 0.0))
		draw_polyline(hl, WHITE, 1.1, true)


class Birds extends Node2D:
	## Zwei Vögel als Federstriche über dem Goldgrund, Flügelschlag mit 6 Bildern/s
	var m
	func _init(main) -> void:
		m = main
	func _process(_d: float) -> void:
		queue_redraw()
	func _draw() -> void:
		var poses := [
			[Vector2(-7, -4), Vector2(-3, -1.5), Vector2(0, 0), Vector2(3, -1.5), Vector2(7, -4)],
			[Vector2(-7, -1), Vector2(-3, -2), Vector2(0, 0), Vector2(3, -2), Vector2(7, -1)],
			[Vector2(-7, 2.5), Vector2(-3, -0.5), Vector2(0, 0), Vector2(3, -0.5), Vector2(7, 2.5)],
			[Vector2(-7, -1), Vector2(-3, -2), Vector2(0, 0), Vector2(3, -2), Vector2(7, -1)]]
		var birds := [[520.0, 70.0, 0], [430.0, 96.0, 2]]
		for b in birds:
			var x: float = fposmod(b[0] - 34.0 * m.t + 40.0, 880.0) - 40.0   # fliegen endlos durch
			var y: float = b[1] + 3.0 * sin(m.t * 1.3 + b[2])
			var pose: Array = poses[(int(floor(m.t * 6.0)) + b[2]) % 4]
			var pts := PackedVector2Array()
			for v in pose:
				pts.append(Vector2(round(x), round(y)) + v * 1.6)
			draw_polyline(pts, INK, 2.0, true)


class LampRays extends Node2D:
	## Leuchtfeuer: Strahlenkranz in Zinnober wie die Lichtstrahlen der Buchmalerei; dreht sich langsam,
	## pulsiert, und alle 3 s blitzt es auf (Strahl zeigt zum Betrachter)
	var m
	var c: Vector2
	func _init(main, center: Vector2) -> void:
		m = main
		c = center
	func _process(_d: float) -> void:
		queue_redraw()
	func _draw() -> void:
		var t: float = m.t
		var pulse := 0.5 + 0.5 * sin(TAU * t / 1.6)
		var flash := pow(max(0.0, sin(TAU * t / 3.0 - 3.875)), 14.0)   # alle 3 s, Höhepunkt bei 2,6 s und 5,6 s
		for i in 16:
			var a := i * TAU / 16.0 + t * 0.35
			if sin(a) > 0.45:
				continue        # nicht in den Turm hinein
			var long := 1.0 if i % 2 == 0 else 0.55
			var L := (6.0 + 8.0 * pulse + 34.0 * flash) * long
			var d := Vector2(cos(a), sin(a))
			draw_line(c + d * 6.0, c + d * (6.0 + L), RED, 1.6, true)
		draw_circle(c, 3.6 + 1.2 * pulse + 2.0 * flash, Color(1.0, 0.93, 0.62), true, -1.0, true)
		draw_circle(c, 3.6 + 1.2 * pulse + 2.0 * flash, RED, false, 1.2, true)


class LanternRays extends Node2D:
	## Laterne: kurze goldene Strahlen, flackern 10-mal pro Sekunde
	var m
	var c: Vector2
	func _init(main, center: Vector2) -> void:
		m = main
		c = center
	func _process(_d: float) -> void:
		queue_redraw()
	func _draw() -> void:
		var k: float = floor(m.t * 10.0)
		for i in 8:
			var a := i * TAU / 8.0 + 0.2
			var f: float = m.flick(k * 7.0 + i * 13.0)
			var L := 3.0 + 8.0 * f
			var d := Vector2(cos(a), sin(a))
			draw_line(c + d * 11.0, c + d * (11.0 + L), GOLD, 1.5, true)

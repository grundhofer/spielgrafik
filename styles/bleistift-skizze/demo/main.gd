extends Node2D
## Bleistiftskizze & Notizbuch – Hafen von Lornholm (Katalogeintrag "bleistift-skizze").
##
## Eine Seite aus einem karierten Skizzenbuch mit Spiralbindung: oben die Bleistiftzeichnung des Hafens (KI-Bild,
## scripts/build_drawing.py), auf das Papier multipliziert und zum Rand hin auslaufend; darunter Notizen in
## Kugelschreiber als Textoberfläche. Alles, was sich bewegt, ist gezeichnet: Line-Boil auf Zeichnung und Figur
## (drei Fassungen, Wechsel alle 3 Takte), Rauch als Kringel, Leuchtturmstrahl als schraffierter Keil aus Buntstift,
## Laternenschein als flackernder Hof aus Buntstiftschraffur mit Strahlen, Möwen als Häkchen, auf dem Wasser
## Wellenstriche aus Grafit und herausradierte Lichter. Ein Bleistift liegt auf dem Blatt (Polygone).
## Effekte bewegen sich auf Dreien (10 Bilder/s) wie eine Zeichentrickanimation.
## Der Dachs ist ein KI-Laufbogen in Spielgröße (scripts/build_badger.py), Ablauf in art/timeline.json
## (scripts/choreo.py). Alles hängt nur von der aufsummierten Zeit ab; Zufall nur mit festem Seed.

const Pencil := preload("res://pencil.gd")

const SEED := 20261012
const FPS := 30.0
const BOIL_TICKS := 3          # Line-Boil: neue Fassung alle 3 Takte (10/s), drei Fassungen
const LH_PERIOD := 6.0         # Umlauf des Leuchtfeuers
const LH_LEFT_AT := 5.53       # Strahl zeigt ganz nach links (Poster)
const T_CHECK := 4.1           # Häkchen bei Antwort 2
const T_PARSER := 4.5          # Parserzeile wird geschrieben
const WRITE_CPS := 14.0

const GRAPHITE := Color(0.2, 0.204, 0.235)
const BALLPOINT := Color(0.13, 0.2, 0.47)
const YELLOW := Color(0.97, 0.74, 0.18)
const ORANGE := Color(0.93, 0.47, 0.13)
const AMBER := Color(0.95, 0.6, 0.1)

var t := 0.0
var lay: Dictionary
var tl: Dictionary
var drawing_mat: ShaderMaterial
var badger_mat: ShaderMaterial
var badger: Sprite2D
var fx: Array[Node2D] = []
var shadow: Shadow
var check: Check
var parser: Label
var f_bold: FontVariation
var f_body: FontVariation
var probe_badger_only := false
var no_boil := false
var probe_log := false
var last_step := -1


func _json(path: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	probe_badger_only = "--probe-badger-only" in args
	no_boil = "--no-boil" in args or (probe_badger_only and not "--boil-probe" in args)
	probe_log = "--probe-log" in args
	lay = _json("res://art/layout.json")
	tl = _json("res://art/timeline.json")
	var bmeta := _json("res://art/badger.json")
	var paper_tex: Texture2D = load("res://art/paper.png")
	var tooth_tex: Texture2D = load("res://art/tooth.png")
	var boil_tex: Texture2D = load("res://art/boil.png")
	var caveat: FontFile = load("res://fonts/Caveat-wght.ttf")
	f_bold = FontVariation.new()
	f_bold.base_font = caveat
	f_bold.variation_opentype = {"weight": 700}
	f_body = FontVariation.new()
	f_body.base_font = caveat
	f_body.variation_opentype = {"weight": 500}

	var paper := Sprite2D.new()
	paper.texture = paper_tex
	paper.centered = false
	add_child(paper)

	var fr: Array = lay["frame"]
	drawing_mat = ShaderMaterial.new()
	drawing_mat.shader = load("res://shaders/drawing.gdshader")
	drawing_mat.set_shader_parameter("boil_tex", boil_tex)
	drawing_mat.set_shader_parameter("tooth_tex", tooth_tex)
	drawing_mat.set_shader_parameter("size", Vector2(fr[2], fr[3]))
	drawing_mat.set_shader_parameter("boil_on", not no_boil)
	var drawing := Sprite2D.new()
	drawing.texture = load("res://art/drawing.png")
	drawing.centered = false
	drawing.position = Vector2(fr[0], fr[1])
	drawing.material = drawing_mat
	add_child(drawing)

	var a: Dictionary = lay["anchors"]
	var pencil_mat := ShaderMaterial.new()
	pencil_mat.shader = load("res://shaders/pencil.gdshader")
	pencil_mat.set_shader_parameter("tooth_tex", tooth_tex)
	var eraser_mat := ShaderMaterial.new()
	eraser_mat.shader = load("res://shaders/eraser.gdshader")
	eraser_mat.set_shader_parameter("paper_tex", paper_tex)
	eraser_mat.set_shader_parameter("tooth_tex", tooth_tex)

	var ripples := Water.new()
	ripples.slots = 34
	ripples.sd = 100
	ripples.areas = [[740, 345, 935, 470, 3.0], [420, 312, 850, 338, 2.0], [930, 345, 1236, 392, 2.0]]
	fx.append(ripples)
	var glints := Water.new()
	glints.eraser = true
	glints.slots = 14
	glints.sd = 200
	glints.areas = [[440, 395, 720, 470, 3.0], [360, 440, 740, 482, 2.0], [930, 350, 1236, 392, 2.0]]
	glints.material = eraser_mat
	fx.append(glints)
	var smoke := Smoke.new()
	smoke.origin = _v(a["chimney"]) + Vector2(1, -4)
	fx.append(smoke)
	var beam := Beam.new()
	beam.lamp = _v(a["lamp"])
	fx.append(beam)
	var glow := Glow.new()
	glow.center = _v(a["lantern"]) + Vector2(1, -4)
	fx.append(glow)
	var gulls := Gulls.new()
	fx.append(gulls)
	for n in fx:
		if n != glints:
			n.material = pencil_mat
		add_child(n)

	shadow = Shadow.new()
	shadow.material = pencil_mat
	add_child(shadow)

	badger_mat = ShaderMaterial.new()
	badger_mat.shader = load("res://shaders/badger.gdshader")
	badger_mat.set_shader_parameter("boil_tex", boil_tex)
	badger_mat.set_shader_parameter("tooth_tex", tooth_tex)
	badger_mat.set_shader_parameter("paper_tex", paper_tex)
	badger_mat.set_shader_parameter("boil_on", not no_boil)
	badger_mat.set_shader_parameter("boil_amp", 0.8)
	var btex: Texture2D = load("res://art/badger.png")
	badger_mat.set_shader_parameter("sheet_size", Vector2(btex.get_width(), btex.get_height()))
	badger_mat.set_shader_parameter("frame_w", float(bmeta["frame_w"]))
	badger = Sprite2D.new()
	badger.texture = btex
	badger.hframes = (bmeta["order"] as Array).size()
	badger.centered = false
	badger.material = badger_mat
	add_child(badger)

	_build_notes()

	if probe_badger_only:
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
		for c in get_children():
			if c != badger:
				c.visible = false
		badger_mat.set_shader_parameter("paper_tex", ImageTexture.create_from_image(
				Image.create_empty(4, 4, false, Image.FORMAT_RGB8)))
	_apply(0.0)


func _v(p: Array) -> Vector2:
	return Vector2(p[0], p[1])


func _build_notes() -> void:
	var notes := Node2D.new()
	add_child(notes)
	var ink := Ink.new()
	notes.add_child(ink)

	# Ort als Überschrift, zweimal unterstrichen
	var head := _label("Hafen von Lornholm", f_bold, 40, Vector2(60, 560))
	notes.add_child(head)
	var hw := f_bold.get_string_size(head.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 40).x
	ink.add(PackedVector2Array([Vector2(56, 611), Vector2(60 + hw * 0.5, 609), Vector2(66 + hw, 612)]), 2.2, 11)
	ink.add(PackedVector2Array([Vector2(70, 617), Vector2(60 + hw * 0.55, 616), Vector2(48 + hw, 618)]), 1.6, 12)

	var body := _label("Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich.", f_body, 31, Vector2(60, 618))
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.size = Vector2(620, 80)
	body.label_settings.line_spacing = -4.0
	notes.add_child(body)

	# Auswahl als Liste mit gezeichneten Kästchen
	var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	var x0 := 790.0
	for i in 3:
		var y := 566.0 + 38.0 * i
		notes.add_child(_label(choices[i], f_body, 31, Vector2(x0 + 34, y)))
		var b := Vector2(x0, y + 15)
		ink.add(PackedVector2Array([b, b + Vector2(21, -1), b + Vector2(22, 20), b + Vector2(-1, 21), b + Vector2(0, -2)]),
				1.8, 30 + i, 0.6)
	check = Check.new()
	check.a = Vector2(x0 + 3, 566.0 + 38.0 + 24.0)
	notes.add_child(check)

	# Parserzeile: wird mit der Hand geschrieben
	parser = _label("> nimm paket", f_body, 31, Vector2(x0 + 34, 566.0 + 38.0 * 3))
	parser.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	parser.visible_characters = 0
	notes.add_child(parser)
	# Trennstrich zwischen Text und Auswahl
	ink.add(PackedVector2Array([Vector2(744, 572), Vector2(742, 640), Vector2(745, 708)]), 1.6, 40, 0.9)

	# Bleistift, der auf dem Blatt liegt (rechts unten, vom Bildrand angeschnitten)
	var stift := Stift.new()
	stift.position = Vector2(1122, 668)
	stift.rotation = deg_to_rad(-19.0)
	add_child(stift)


func _label(text: String, font: Font, size: int, pos: Vector2) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	var ls := LabelSettings.new()
	ls.font = font
	ls.font_size = size
	ls.font_color = BALLPOINT
	l.label_settings = ls
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	return l


func _process(delta: float) -> void:
	t += delta
	_apply(t)


func _apply(tt: float) -> void:
	var tick := int(floor(tt * FPS + 0.5))
	var phase := (tick / BOIL_TICKS) % 3
	var step := tick / BOIL_TICKS                     # Effekte auf Dreien
	var ft := float(step * BOIL_TICKS) / FPS
	drawing_mat.set_shader_parameter("phase", phase)
	badger_mat.set_shader_parameter("phase", phase)

	var line: Array = tl["timeline"]
	var e: Dictionary = line[mini(tick, line.size() - 1)]
	badger.frame = int(e["f"])
	badger.position = Vector2(e["x"], e["y"])
	if probe_log:
		print("PROBE tick=%d frame=%d x=%d drawn=%d" % [tick, badger.frame, int(e["x"]), Engine.get_frames_drawn()])
	shadow.center = Vector2(float(e["x"]) + 76.0, float(tl["feet_y"]) - 2.0)
	shadow.phase = 0 if no_boil else phase
	shadow.queue_redraw()

	if step != last_step:              # Effekte ändern sich nur auf Dreien: nur dann neu zeichnen
		last_step = step
		for n in fx:
			n.set("t", ft)
			n.set("step", step)
			n.set("phase", 0 if no_boil else phase)
			n.queue_redraw()

	check.k = clampf((tt - T_CHECK) / 0.2, 0.0, 1.0)
	check.queue_redraw()
	parser.visible_characters = int(clampf(floor((tt - T_PARSER) * WRITE_CPS), 0.0, parser.text.length()))


## Kugelschreiberstriche der Notizen (Unterstreichung, Kästchen, Trennstrich); ruhig, ohne Boil (Lesbarkeit).
class Ink extends Node2D:
	var items := []

	func add(pts: PackedVector2Array, w: float, sd: int, wobble := 1.0) -> void:
		items.append([pts, w, sd, wobble])

	func _draw() -> void:
		for it in items:
			Pencil.stroke(self, it[0], Color(BALLPOINT, 0.92), it[1], SEED + it[2], it[3], 0.05)


## Häkchen in Kugelschreiber, wird in 0,2 s gezogen.
class Check extends Node2D:
	var a := Vector2.ZERO
	var k := 0.0

	func _draw() -> void:
		if k <= 0.0:
			return
		var p0 := a + Vector2(-2, -10)
		var p1 := a + Vector2(7, 2)
		var p2 := a + Vector2(26, -30)
		var pts := PackedVector2Array([p0])
		if k < 0.35:
			pts.append(p0.lerp(p1, k / 0.35))
		else:
			pts.append(p1)
			pts.append(p1.lerp(p2, (k - 0.35) / 0.65))
		Pencil.stroke(self, pts, Color(BALLPOINT, 0.95), 2.6, SEED + 77, 0.4, 0.0)


## Wasser: kurze Striche, die erscheinen, ein Stück treiben und wieder vergehen (je Platz 0,8 s, versetzt).
## Zwei Arten: Wellenstriche aus Grafit ("~") auf dem hellen Wasser und Lichter, die aus dem dunklen Grafit unter
## den Booten und vor dem Kai herausradiert sind (Material eraser.gdshader).
class Water extends Node2D:
	var t := 0.0
	var step := 0
	var phase := 0
	var eraser := false
	var slots := 20
	var areas := []            # x0, y0, x1, y1, Gewicht (Bildschirmpixel)
	var sd := 0
	const LIFE := 8            # Schritte (0,8 s)

	func _draw() -> void:
		var wsum := 0.0
		for ar in areas:
			wsum += ar[4]
		for k in slots:
			var s := step + k * 5
			var cyc := s / LIFE
			var u := float(s % LIFE) / float(LIFE)
			var rng := RandomNumberGenerator.new()
			rng.seed = SEED + sd + k * 1009 + cyc * 7919
			var pick := rng.randf() * wsum
			var ar: Array = areas[0]
			for cand in areas:
				pick -= cand[4]
				if pick <= 0.0:
					ar = cand
					break
			var p := Vector2(rng.randf_range(ar[0], ar[2]), rng.randf_range(ar[1], ar[3]))
			var depth := clampf((p.y - 312.0) / 170.0, 0.0, 1.0)
			var length := lerpf(12.0, 40.0, depth) * rng.randf_range(0.6, 1.2)
			var env := sin(PI * (u + 0.5 / LIFE))
			p.x += lerpf(1.5, 6.0, depth) * u * 2.0
			var lo := Vector2(-length * 0.5, 0)
			var hi := Vector2(length * 0.5, rng.randf_range(-0.6, 0.6))
			var amp := lerpf(0.8, 2.0, depth)
			if eraser:
				Pencil.line(self, p + lo, p + hi, Color(1, 1, 1, 0.95 * env), lerpf(2.0, 3.4, depth),
						SEED + sd + k * 31 + phase * 5, 0.5)
			else:
				var pts := PackedVector2Array([p + lo, p + lo * 0.35 + Vector2(0, -amp), p - lo * 0.35 + Vector2(0, amp), p + hi])
				Pencil.stroke(self, pts, Color(GRAPHITE, 0.6 * env), lerpf(1.3, 2.0, depth),
						SEED + sd + k * 31 + phase * 5, 0.4, 0.2)


## Rauch: eine durchgehende Kringellinie wie in einer Kritzelei. Die Schlaufen wandern nach oben, werden dabei
## größer und blasser, der Wind biegt die Säule nach rechts.
class Smoke extends Node2D:
	var t := 0.0
	var step := 0
	var phase := 0
	var origin := Vector2.ZERO
	const RISE := 78.0
	const LOOPS := 3.7
	const FLOW := 1.6          # Schlaufen je Sekunde

	func _draw() -> void:
		var pts := PackedVector2Array()
		var n := 160
		for i in n:
			var s := float(i) / float(n - 1)
			var base := origin + Vector2(44.0 * s * s + 2.5 * sin(s * 5.0 + t * 0.9), -RISE * s)
			var r := 2.5 + 13.0 * s
			var th := TAU * (LOOPS * s - FLOW * t)
			pts.append(base + Vector2(r * 1.15 * cos(th), r * 0.7 * sin(th)))
		Pencil.stroke(self, pts, Color(GRAPHITE, 0.85), 1.9, SEED + 500 + phase * 3, 0.6, 0.0, 0.85)


## Leuchtturm: der Strahl als Keil aus zwei Grafitlinien, mit gelbem Buntstift schräg schraffiert. Er läuft um:
## Länge = Projektion (|sin|), wenn er zur Kamera zeigt, ein Kranz aus kurzen Strichen (Aufblitzen).
class Beam extends Node2D:
	var t := 0.0
	var step := 0
	var phase := 0
	var lamp := Vector2.ZERO

	func _draw() -> void:
		var phi := TAU * (t - LH_LEFT_AT) / LH_PERIOD + 1.5 * PI
		var sp := sin(phi)
		var cp := cos(phi)
		var dir := -1.0 if sp < 0.0 else 1.0
		var reach := 640.0 if dir < 0.0 else 1236.0 - lamp.x
		var length := reach * absf(sp)
		var k := smoothstep(0.1, 0.3, absf(sp))
		if k > 0.0 and length > 20.0:
			var hw0 := 4.0
			var hw1 := 10.0 + 0.055 * length
			var end := lamp + Vector2(dir * length, 0.06 * length)
			var nrm := Vector2(0, 1)
			# Schraffur im Keil: schräge Striche, zum Ende hin seltener und heller
			var n := int(length / 7.0)
			for i in range(1, n):
				var v := float(i) / float(n)
				var p := lamp.lerp(end, v)
				var hw := lerpf(hw0, hw1, v)
				var tilt := Vector2(dir * 0.45 * hw, 0)
				var a := 0.62 * k * (1.0 - 0.75 * v)
				Pencil.line(self, p - nrm * hw + tilt, p + nrm * hw - tilt, Color(YELLOW, a), 2.0,
						SEED + 900 + i * 7 + phase, 0.4)
			for s: float in [-1.0, 1.0]:
				var a2 := lamp + nrm * s * hw0
				var b2 := end + nrm * s * hw1
				Pencil.line(self, a2, b2, Color(GRAPHITE, 0.55 * k), 1.6, SEED + 950 + int(s) + phase * 11, 1.0)
				Pencil.line(self, a2, a2.lerp(b2, 0.55), Color(ORANGE, 0.35 * k), 1.4, SEED + 960 + int(s) + phase * 11, 1.4)
		# Aufblitzen, wenn der Strahl zur Kamera zeigt
		var flash := pow(maxf(cp, 0.0), 6.0)
		if flash > 0.05:
			for i in 12:
				var ang := TAU * float(i) / 12.0 + 0.13
				var d := Vector2(cos(ang), sin(ang))
				var r0 := 9.0
				Pencil.line(self, lamp + d * r0, lamp + d * (r0 + 6.0 + 18.0 * flash), Color(YELLOW, 0.9 * flash),
						2.0, SEED + 980 + i + phase * 13, 0.5)


## Laterne: ein Hof aus gelber Buntstiftschraffur um das Glas und kurze Striche, die nach außen strahlen. Je Schritt
## (10/s) neue Zufallswerte: Stärke, Länge der Strahlen und welche Schraffurstriche gerade gezogen sind (Flackern).
class Glow extends Node2D:
	var t := 0.0
	var step := 0
	var phase := 0
	var center := Vector2.ZERO
	const N := 16
	const R := Vector2(36.0, 47.0)      # Halbachsen des Glases samt Rahmen

	func _skip(v: Vector2) -> bool:
		# links oben hängt die Laterne am Arm: dort nichts zeichnen
		var ang := fposmod(v.angle(), TAU)
		return ang > 2.75 and ang < 4.3

	func _draw() -> void:
		var rng := RandomNumberGenerator.new()
		rng.seed = SEED + 300 + step * 101
		var k := 0.6 + 0.4 * rng.randf()
		# Schraffurhof: Striche unter 60°, Abstand 6 px, im Ring 1,05–1,05+0,75·k der Glasellipse
		var dir := Vector2(cos(-PI / 3.0), sin(-PI / 3.0))
		var nrm := Vector2(-dir.y, dir.x)
		var outer := 1.05 + 0.75 * k
		var j := 0
		for c in range(-96, 97, 6):
			var seg := PackedVector2Array()
			for si in range(-110, 111, 2):
				var p := nrm * float(c) + dir * float(si)
				var e := Vector2(p.x / R.x, p.y / R.y).length()
				var inside := e > 1.05 and e < outer and not _skip(p)
				if inside:
					seg.append(center + p)
				if (not inside or si == 110) and seg.size() >= 3:
					if rng.randf() < 0.75:
						var a := 0.75 * k * (1.0 - 0.6 * (Vector2(seg[seg.size() / 2].x - center.x, seg[seg.size() / 2].y - center.y) / R).length() / outer)
						Pencil.line(self, seg[0], seg[seg.size() - 1], Color(AMBER, a), 2.3, SEED + 360 + j * 3 + phase, 0.5)
					j += 1
				if not inside:
					seg.clear()
		# Strahlen
		for i in N:
			var ang := TAU * float(i) / float(N) + 0.1
			var d := Vector2(cos(ang), sin(ang))
			if _skip(d):
				continue
			var r0 := Vector2(R.x * d.x, R.y * d.y).length()
			var length := (8.0 + 24.0 * rng.randf()) * k
			var col := YELLOW if i % 2 == 0 else ORANGE
			Pencil.line(self, center + d * (r0 + 4.0), center + d * (r0 + 4.0 + length), Color(col, 0.5 + 0.45 * k),
					2.2, SEED + 320 + i * 5 + phase, 0.6)


## Möwen als Häkchen-Paare, vier Flügelstellungen (10 bzw. 5 Bilder/s, auf Dreien bzw. Sechsen).
class Gulls extends Node2D:
	var t := 0.0
	var step := 0
	var phase := 0
	const LIFT := [1.0, 0.35, -0.45, 0.35]

	func _draw() -> void:
		_gull(Vector2(980.0 - 62.0 * t, 92.0 + 6.0 * sin(t * 0.9)), 19.0, LIFT[step % 4], 1)
		_gull(Vector2(610.0 + 38.0 * t, 66.0 + 4.0 * sin(t * 1.3 + 1.0)), 12.0, LIFT[(step / 2 + 2) % 4], 2)

	func _gull(c: Vector2, size: float, lift: float, id: int) -> void:
		for side: float in [-1.0, 1.0]:
			var tip := c + Vector2(side * size, -size * 0.38 * lift - size * 0.08)
			var mid := c + Vector2(side * size * 0.42, -size * (0.42 * lift + 0.22))
			var pts := PackedVector2Array([c, mid, tip])
			var smooth := PackedVector2Array()
			for i in 9:
				var u := float(i) / 8.0
				smooth.append(c.lerp(mid, u).lerp(mid.lerp(tip, u), u))
			Pencil.stroke(self, smooth, Color(GRAPHITE, 0.9), 1.4 + size / 14.0, SEED + 700 + id * 10 + int(side) + phase * 3,
					0.4, 0.25)


## Schatten unter dem Dachs: schräge Grafitschraffur in einer flachen Ellipse.
class Shadow extends Node2D:
	var center := Vector2.ZERO
	var phase := 0
	const RX := 64.0
	const RY := 9.0

	func _draw() -> void:
		var x := -RX
		var i := 0
		while x <= RX:
			var h := RY * sqrt(maxf(0.0, 1.0 - (x / RX) * (x / RX)))
			if h > 1.5:
				var a := center + Vector2(x - h * 0.8, h)
				var b := center + Vector2(x + h * 0.8, -h)
				Pencil.line(self, a, b, Color(GRAPHITE, 0.62), 1.8, SEED + 1200 + i * 3 + phase, 0.4)
			x += 4.5
			i += 1


## Ein gelber Sechskant-Bleistift, der auf dem Blatt liegt: Grafitspitze, angespitztes Holz mit gewellter Lack-
## kante, drei Lackfacetten, weicher Schlagschatten auf dem Papier. Nur Polygone, Kanten mit 1-px-Linie geglättet.
class Stift extends Node2D:
	const W := 22.0             # Breite über die Facetten
	const LEN := 330.0

	func _poly(pts: PackedVector2Array, col: Color) -> void:
		draw_colored_polygon(pts, col)
		var ring := pts.duplicate()
		ring.append(pts[0])
		draw_polyline(ring, col, 1.0, true)

	func _draw() -> void:
		var h := W * 0.5
		# Schatten: mehrere aufgeweitete Umrisse mit wenig Deckung, nach rechts unten versetzt
		for i in 5:
			var g := 1.0 + float(i) * 2.2
			var o := Vector2(5.0, 9.0)
			_poly(PackedVector2Array([o + Vector2(-g, 0), o + Vector2(40, -h - g), o + Vector2(LEN, -h - g),
					o + Vector2(LEN, h + g), o + Vector2(40, h + g)]), Color(0.18, 0.15, 0.12, 0.05))
		# Holzkegel
		_poly(PackedVector2Array([Vector2(9, -3.6), Vector2(44, -h), Vector2(44, h), Vector2(9, 3.6)]), Color(0.88, 0.74, 0.55))
		_poly(PackedVector2Array([Vector2(9, 0.5), Vector2(44, 2.0), Vector2(44, h), Vector2(9, 3.6)]), Color(0.78, 0.62, 0.43))
		# Grafitspitze
		_poly(PackedVector2Array([Vector2(0, 0.6), Vector2(10, -3.8), Vector2(10, 3.8)]), Color(0.24, 0.24, 0.27))
		_poly(PackedVector2Array([Vector2(1.5, 0.2), Vector2(10, -3.4), Vector2(10, -1.0)]), Color(0.47, 0.47, 0.5))
		# Lackfacetten mit gewellter Kante zum Holz (Schnitt des Anspitzers)
		var facets := [[-h, -h / 3.0, Color(0.99, 0.83, 0.33)], [-h / 3.0, h / 3.0, Color(0.96, 0.71, 0.13)],
				[h / 3.0, h, Color(0.83, 0.56, 0.08)]]
		for f in facets:
			var y0: float = f[0]
			var y1: float = f[1]
			var mid := (y0 + y1) * 0.5
			var pts := PackedVector2Array([Vector2(46, y0), Vector2(LEN, y0), Vector2(LEN, y1), Vector2(46, y1)])
			pts.append(Vector2(40 + 2.0 * absf(mid) / h, mid))
			_poly(pts, f[2])
		draw_line(Vector2(46, -h / 3.0), Vector2(LEN, -h / 3.0), Color(0.75, 0.52, 0.1, 0.6), 1.0, true)
		draw_line(Vector2(46, h / 3.0), Vector2(LEN, h / 3.0), Color(0.62, 0.4, 0.05, 0.7), 1.0, true)
		# Glanzlicht auf der oberen Facette
		draw_line(Vector2(60, -h + 2.5), Vector2(LEN, -h + 2.5), Color(1, 0.95, 0.75, 0.6), 1.5, true)

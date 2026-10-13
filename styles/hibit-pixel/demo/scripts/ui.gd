extends Control
## Oberfläche im Stil moderner Pixel-Spiele, alles auf dem 640×360-Raster von Godot gezeichnet:
## Ortsschild oben rechts, unten ein Dialogfenster mit Porträtrahmen, Namensreiter, Schreibmaschinentext,
## Parserzeile und rechts die drei Auswahlpunkte mit hüpfendem Pfeil.
## Schrift: Pixel Operator (16 px, CC0) ohne Kantenglättung, Hinting und Subpixel-Positionen; Namensreiter in
## Pixel Operator 8 (8 px).

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const SPEAKER := "Dachs-Kurier"

# Fenster
const BOX := Rect2i(6, 290, 628, 64)
const PORT := Rect2i(13, 295, 54, 54)
const TEXT_X := 76
const DIV_X := 404
const CH_X := 420
const TITLE_RIGHT := 620   # rechte Kante des Ortsnamens

# Farben (aus der Palette des Hintergrunds gewählt)
const INK := Color(0.055, 0.047, 0.11, 0.9)
const INK2 := Color(0.09, 0.075, 0.17, 0.92)
const EDGE_D := Color(0.02, 0.016, 0.05, 1.0)
const EDGE_L := Color(0.93, 0.80, 0.6, 1.0)
const EDGE_M := Color(0.62, 0.47, 0.42, 1.0)
const TXT := Color(0.96, 0.92, 0.86, 1.0)
const TXT_DIM := Color(0.62, 0.6, 0.74, 1.0)
const GOLD := Color(1.0, 0.78, 0.38, 1.0)
const SHADOW := Color(0.03, 0.02, 0.07, 0.85)

var t := 0.0
var f16: FontFile
var f16b: FontFile
var f8: FontFile
var portrait: Texture2D
var wrapped: Array = []


func _font(path: String) -> FontFile:
	var f: FontFile = load(path)
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.generate_mipmaps = false
	return f


func _ready() -> void:
	f16 = _font("res://fonts/PixelOperator.ttf")
	f16b = _font("res://fonts/PixelOperator-Bold.ttf")
	f8 = _font("res://fonts/PixelOperator8.ttf")
	portrait = load("res://art/portrait.png")
	wrapped = _wrap(LINE, DIV_X - 10 - TEXT_X)


func _wrap(s: String, width: int) -> Array:
	var lines: Array = []
	var cur := ""
	for w in s.split(" "):
		var cand := w if cur == "" else cur + " " + w
		if f16.get_string_size(cand, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x > width and cur != "":
			lines.append(cur)
			cur = w
		else:
			cur = cand
	lines.append(cur)
	return lines


func step(time: float, _badger: Dictionary) -> void:
	t = time
	queue_redraw()


func _frame(r: Rect2i, fill: Color) -> void:
	# Fenster mit abgeschrägten Ecken: außen dunkel, helle Linie, innen dunkle Linie
	var x0 := r.position.x
	var y0 := r.position.y
	var x1 := r.end.x - 1
	var y1 := r.end.y - 1
	draw_rect(Rect2(x0 + 2, y0 + 2, r.size.x - 4, r.size.y - 4), fill)
	# äußere dunkle Kante
	draw_rect(Rect2(x0 + 2, y0, r.size.x - 4, 1), EDGE_D)
	draw_rect(Rect2(x0 + 2, y1, r.size.x - 4, 1), EDGE_D)
	draw_rect(Rect2(x0, y0 + 2, 1, r.size.y - 4), EDGE_D)
	draw_rect(Rect2(x1, y0 + 2, 1, r.size.y - 4), EDGE_D)
	draw_rect(Rect2(x0 + 1, y0 + 1, 1, 1), EDGE_D)
	draw_rect(Rect2(x1 - 1, y0 + 1, 1, 1), EDGE_D)
	draw_rect(Rect2(x0 + 1, y1 - 1, 1, 1), EDGE_D)
	draw_rect(Rect2(x1 - 1, y1 - 1, 1, 1), EDGE_D)
	# helle Linie (oben heller als unten)
	draw_rect(Rect2(x0 + 2, y0 + 1, r.size.x - 4, 1), EDGE_L)
	draw_rect(Rect2(x0 + 2, y1 - 1, r.size.x - 4, 1), EDGE_M)
	draw_rect(Rect2(x0 + 1, y0 + 2, 1, r.size.y - 4), EDGE_L)
	draw_rect(Rect2(x1 - 1, y0 + 2, 1, r.size.y - 4), EDGE_M)
	# innere dunkle Linie
	draw_rect(Rect2(x0 + 2, y0 + 2, r.size.x - 4, 1), EDGE_D)
	draw_rect(Rect2(x0 + 2, y0 + 2, 1, r.size.y - 4), EDGE_D)


func _text(f: Font, pos: Vector2, s: String, col: Color, size := 16, shadow := true) -> void:
	if shadow:
		draw_string(f, pos + Vector2(1, 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, SHADOW)
	draw_string(f, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, col)


func _ease_px(p: float) -> float:
	p = clampf(p, 0.0, 1.0)
	return 1.0 - (1.0 - p) * (1.0 - p)


func _draw() -> void:
	_draw_title()
	_draw_box()


func _draw_title() -> void:
	# Ortsschild oben rechts im freien Himmel (über dem Leuchtfeuerkegel, weg vom Schornsteinrauch links):
	# gleitet in ganzen Pixeln von rechts herein, Zierlinie wächst nach links
	var p := _ease_px((t - 0.2) / 0.5)
	if p <= 0.0:
		return
	var w := int(f16b.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x)
	var x := float(TITLE_RIGHT - w) + floorf((1.0 - p) * 24.0)
	var a := p
	var col := Color(TXT.r, TXT.g, TXT.b, a)
	_text(f16b, Vector2(x, 22), LOCATION, col)
	var rx := x + w + 4.0                       # rechtes Ende der Zierlinie
	var lw := int(floorf(_ease_px((t - 0.45) / 0.6) * (w + 18)))
	if lw > 0:
		draw_rect(Rect2(rx - lw, 26, lw, 1), Color(GOLD.r, GOLD.g, GOLD.b, a))
		draw_rect(Rect2(rx - lw + 1, 27, lw, 1), Color(SHADOW.r, SHADOW.g, SHADOW.b, 0.7 * a))
		# ausdünnendes Ende links (Pixel-Dithering statt Verlauf)
		for i in 6:
			if i % 2 == 0:
				draw_rect(Rect2(rx - lw - 1 - i, 26, 1, 1), Color(GOLD.r, GOLD.g, GOLD.b, a * 0.8))
		draw_rect(Rect2(rx + 2, 25, 2, 2), Color(GOLD.r, GOLD.g, GOLD.b, a))


func _draw_box() -> void:
	# Fenster fährt ab 0,7 s in 4 Schritten von unten herein (ganze Pixel)
	var p := _ease_px((t - 0.7) / 0.3)
	if p <= 0.0:
		return
	var dy := int(floorf((1.0 - p) * 72.0))
	var box := Rect2i(BOX.position + Vector2i(0, dy), BOX.size)
	_frame(box, INK)
	# Namensreiter
	var tw := int(f8.get_string_size(SPEAKER, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x)
	var tab := Rect2i(box.position.x + 62, box.position.y - 11, tw + 14, 13)
	draw_rect(Rect2(tab.position.x + 1, tab.position.y, tab.size.x - 2, tab.size.y), EDGE_D)
	draw_rect(Rect2(tab.position.x + 2, tab.position.y + 1, tab.size.x - 4, tab.size.y - 1), EDGE_L)
	draw_rect(Rect2(tab.position.x + 3, tab.position.y + 2, tab.size.x - 6, tab.size.y - 2), Color(0.36, 0.2, 0.2, 1.0))
	draw_string(f8, Vector2(tab.position.x + 7, tab.position.y + 10), SPEAKER, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, GOLD)
	# Porträt
	var pr := Rect2i(PORT.position + Vector2i(0, dy), PORT.size)
	_frame(pr, Color(0.16, 0.1, 0.18, 1.0))
	# Hintergrund im Rahmen: zwei warme Stufen (Laternenlicht)
	draw_rect(Rect2(pr.position.x + 3, pr.position.y + 3, pr.size.x - 5, 16), Color(0.24, 0.13, 0.2, 1.0))
	draw_rect(Rect2(pr.position.x + 3, pr.position.y + 19, pr.size.x - 5, 10), Color(0.2, 0.11, 0.18, 1.0))
	var pf := _portrait_frame()
	draw_texture_rect_region(portrait, Rect2(pr.position.x + 2, pr.position.y + 2, 51, 51), Rect2(pf * 52, 0, 51, 51))
	# Text (Schreibmaschine ab 1,0 s, 34 Zeichen/s)
	var shown := int(floorf(maxf(0.0, t - 1.0) * 34.0))
	var y := box.position.y + 18
	var left := shown
	for ln in wrapped:
		var s: String = ln
		if left <= 0:
			break
		_text(f16, Vector2(TEXT_X, y), s.substr(0, mini(left, s.length())), TXT)
		left -= s.length() + 1
		y += 15
	# Parserzeile ab 3,6 s
	if t > 3.6:
		var n := int(floorf((t - 3.6) * 14.0))
		var ps := PARSER.substr(0, mini(n, PARSER.length()))
		var py := box.position.y + 55
		_text(f16, Vector2(TEXT_X, py), ps, TXT_DIM)
		var cw := int(f16.get_string_size(ps, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x)
		if int(floorf(t * 3.0)) % 2 == 0:
			draw_rect(Rect2(TEXT_X + cw + 2, py - 9, 5, 10), TXT_DIM)
	# Trennlinie (gepunktet)
	for yy in range(box.position.y + 8, box.end.y - 7, 2):
		draw_rect(Rect2(DIV_X, yy, 1, 1), EDGE_M)
	# Auswahl ab 3,0 s, eine nach der anderen
	var sel := 0 if t < 4.5 else 1
	for i in CHOICES.size():
		var ta := 3.0 + 0.2 * i
		if t < ta:
			continue
		var cy := box.position.y + 18 + i * 17
		var slide := int(floorf((1.0 - _ease_px((t - ta) / 0.2)) * 8.0))
		var col: Color = GOLD if i == sel else TXT
		if i == sel:
			draw_rect(Rect2(CH_X - 6, cy - 11, DIV_X + 220 - CH_X, 14), Color(0.3, 0.16, 0.22, 0.85))
			var bob := 1 if int(floorf(t * 5.0)) % 2 == 0 else 0
			_arrow(Vector2(CH_X - 4 + bob, cy - 8))
		_text(f16, Vector2(CH_X + 8 + slide, cy), CHOICES[i], col)


func _arrow(p: Vector2) -> void:
	# kleiner Pixelpfeil 4×7
	for i in 4:
		draw_rect(Rect2(p.x + i, p.y + i, 1, 7 - 2 * i), GOLD)
	draw_rect(Rect2(p.x, p.y + 7, 4, 1), SHADOW)


func _portrait_frame() -> int:
	# 0 neutral, 1 blinzeln, 2 sprechen; spricht, solange getippt wird (Mund im Wechsel, 7,5 Hz).
	# Mundbild nur einmal je 7,5-Hz-Takt entscheiden: jede Mundstellung hält so mindestens 4 Aufnahmebilder.
	# Im Takt, in dem ein Punkt getippt wird, bleibt der Mund zu (Satzpause); Leerzeichen zählen nicht, sonst
	# träfe der Taktbeginn bei 34 Zeichen/s zu oft eine Wortlücke und der Mund ginge kaum auf.
	var k := int(floorf(t * 7.5 + 0.0001))
	var tk := float(k) / 7.5
	var typing := tk >= 1.0 and tk < 1.0 + float(LINE.length()) / 34.0
	if typing:
		var i0 := int((tk - 1.0) * 34.0 + 0.0001)
		var i1 := int((tk + 1.0 / 7.5 - 1.0) * 34.0 + 0.0001)
		if LINE.substr(i0, i1 - i0 + 1).contains("."):
			return 0
		return 2 if k % 2 == 0 else 0
	for b in [0.9, 4.2]:
		if t >= b and t < b + 0.1:
			return 1
	return 0

extends Control
## Oberfläche im N64-Stil, gezeichnet in 320×240 (geht mit durch die Videoausgabe und wird dort weich):
##  - Ortsname als Titelkarte zu Beginn (Buchstaben fallen einzeln ein, dunkle Kontur, Schatten), blendet aus.
##  - Dialogfenster: abgerundetes, halbdurchsichtiges dunkles Fenster, weiße runde Schrift mit Schatten,
##    Schlüsselwort rot, Text erscheint Zeichen für Zeichen; danach drei Antworten mit hüpfendem Zeiger.
## Alle Zeiten über einen Bildzähler (30 Bilder/s) aus der aufsummierten Zeit von main.gd (set_time()).

const TITLE := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const KEYWORD := "Paket"
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]

const TITLE_IN := 0.25          # s: erster Buchstabe
const TITLE_STEP := 2           # Bilder je Buchstabe
const TITLE_OUT := 2.1          # s: Ausblenden beginnt
const TITLE_FADE := 0.3
const BOX_OPEN := 2.45          # s: Fenster öffnet sich
const BOX_OPEN_FRAMES := 6
const TYPE_START := 2.7         # s: erstes Zeichen
const CHARS_PER_FRAME := 2      # 60 Zeichen/s
const CHOICE_DELAY := 8         # Bilder nach dem letzten Zeichen
const CURSOR_HALF := 5          # Bilder: Zeiger hüpft (5 links, 5 rechts)

## Fenster (320×240-Koordinaten); main.gd setzt es vor dem ersten Bild.
var box := Rect2(16, 160, 288, 74)
var text_size := 12
var line_h := 13
var t := 0.0

var font_text: FontFile
var font_title: FontFile
var col_text := Color("f4f1ea")
var col_key := Color("ff6a5a")
var col_choice := Color("8cf08c")
var col_cursor := Color("58c8ff")
var col_title := Color("ffe27a")
var lines: Array[String] = []


func _ready() -> void:
	font_text = load("res://fonts/VarelaRound-Regular.ttf")
	font_title = load("res://fonts/Sniglet-ExtraBold.ttf")
	for f in [font_text, font_title]:
		f.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
		f.hinting = TextServer.HINTING_LIGHT
		f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED


func setup(rect: Rect2) -> void:
	box = rect
	_wrap_line()


func set_time(value: float) -> void:
	t = value
	queue_redraw()


func _frame(sec: float) -> int:
	return int(round(sec * 30.0))


func _wrap_line() -> void:
	# erst an Satzenden umbrechen, dann nach Breite
	lines.clear()
	for sentence in LINE.replace(". ", ".\n").split("\n"):
		_wrap_sentence(sentence)


func _wrap_sentence(text: String) -> void:
	var words := text.split(" ")
	var cur := ""
	var maxw := box.size.x - 22
	for w in words:
		var test := w if cur == "" else cur + " " + w
		if font_text.get_string_size(test, HORIZONTAL_ALIGNMENT_LEFT, -1, text_size).x > maxw and cur != "":
			lines.append(cur)
			cur = w
		else:
			cur = test
	if cur != "":
		lines.append(cur)


func _draw() -> void:
	if lines.is_empty():
		_wrap_line()
	var f := _frame(t)
	_draw_title(f)
	_draw_box(f)


# --- Titelkarte ----------------------------------------------------------------------------------------------
func _draw_title(f: int) -> void:
	var f0 := _frame(TITLE_IN)
	if f < f0:
		return
	var fade := 1.0 - clampf((t - TITLE_OUT) / TITLE_FADE, 0.0, 1.0)
	if fade <= 0.0:
		return
	var size := 22
	var w := font_title.get_string_size(TITLE, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var x := roundf(160.0 - w / 2.0)
	var base_y := 62.0
	var drop := [-7.0, -3.0, 1.0, 0.0]          # Buchstabe fällt in 4 Bildern ein und federt
	for i in TITLE.length():
		var ch := TITLE[i]
		var adv := font_title.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
		var k := f - f0 - i * TITLE_STEP
		if k >= 0 and ch != " ":
			var p := Vector2(x, base_y + float(drop[mini(k, 3)]))
			var a := fade * clampf(float(k + 1) / 2.0, 0.0, 1.0)
			draw_string_outline(font_title, p + Vector2(2, 2), ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size, 5, Color(0, 0, 0, 0.5 * a))
			draw_string_outline(font_title, p, ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size, 5, Color(0.22, 0.08, 0.16, a))
			draw_string(font_title, p, ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(col_title, a))
		x += adv


# --- Dialogfenster -------------------------------------------------------------------------------------------
func _draw_box(f: int) -> void:
	var fo := _frame(BOX_OPEN)
	if f < fo:
		return
	var open := clampf(float(f - fo + 1) / BOX_OPEN_FRAMES, 0.0, 1.0)
	open = 1.0 - (1.0 - open) * (1.0 - open)
	var c := box.get_center()
	var sz := box.size * Vector2(0.2 + 0.8 * open, 0.3 + 0.7 * open)
	var r := Rect2((c - sz / 2.0).round(), sz.round())
	_round_rect(r, 9.0, Color(0.03, 0.02, 0.07, 0.66 * open))
	_round_rect(Rect2(r.position + Vector2(3, 2), Vector2(r.size.x - 6, r.size.y * 0.42)), 7.0, Color(0.5, 0.55, 0.9, 0.07 * open))
	if open < 1.0:
		return
	var typed := maxi(0, (f - _frame(TYPE_START) + 1) * CHARS_PER_FRAME)
	var x0 := box.position.x + 12
	var y := box.position.y + 5 + text_size
	var shown := 0
	for ln in lines:
		var n := clampi(typed - shown, 0, ln.length())
		_draw_rich(ln, n, Vector2(x0, y))
		shown += ln.length() + 1
		y += line_h
	var total := LINE.length()
	if typed < total:
		return
	var f_done := _frame(TYPE_START) + int(ceil(float(total) / CHARS_PER_FRAME)) - 1
	var f_choice := f_done + CHOICE_DELAY
	if f < f_choice:
		return
	y += 2
	var k := f - f_choice
	for i in CHOICES.size():
		var sel := i == 1
		_shadow_text(CHOICES[i], Vector2(x0 + 14, y), col_choice if sel else col_text)
		if sel:
			var bob := 0.0 if (k / CURSOR_HALF) % 2 == 0 else 2.0
			_cursor(Vector2(x0 + bob, y - 9))
		y += line_h


func _draw_rich(ln: String, n: int, p: Vector2) -> void:
	# die ersten n Zeichen der Zeile; Schlüsselwort rot
	var s := ln.substr(0, n)
	var idx := ln.find(KEYWORD)
	var x := p.x
	var i := 0
	while i < s.length():
		var in_key := idx >= 0 and i >= idx and i < idx + KEYWORD.length()
		var j := i
		while j < s.length() and (idx >= 0 and j >= idx and j < idx + KEYWORD.length()) == in_key:
			j += 1
		var part := s.substr(i, j - i)
		_shadow_text(part, Vector2(x, p.y), col_key if in_key else col_text)
		x += font_text.get_string_size(part, HORIZONTAL_ALIGNMENT_LEFT, -1, text_size).x
		i = j


func _shadow_text(s: String, p: Vector2, col: Color) -> void:
	if s == "":
		return
	p = p.round()
	draw_string(font_text, p + Vector2(1, 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, text_size, Color(0, 0, 0, 0.8))
	draw_string(font_text, p, s, HORIZONTAL_ALIGNMENT_LEFT, -1, text_size, col)


func _cursor(p: Vector2) -> void:
	# Dreieck nach rechts mit dunkler Kontur und hellem Glanz
	draw_colored_polygon(PackedVector2Array([p + Vector2(-1, -1.5), p + Vector2(9.5, 4), p + Vector2(-1, 9.5)]), Color(0, 0, 0, 0.75))
	draw_colored_polygon(PackedVector2Array([p, p + Vector2(8, 4), p + Vector2(0, 8)]), col_cursor)
	draw_colored_polygon(PackedVector2Array([p + Vector2(1, 1), p + Vector2(5, 3), p + Vector2(1, 3.5)]), Color(1, 1, 1, 0.65))


func _round_rect(r: Rect2, rad: float, col: Color) -> void:
	var pts := PackedVector2Array()
	var centers := [Vector2(r.end.x - rad, r.position.y + rad), Vector2(r.end.x - rad, r.end.y - rad),
		Vector2(r.position.x + rad, r.end.y - rad), Vector2(r.position.x + rad, r.position.y + rad)]
	for k in 4:
		for s in 7:
			var a := deg_to_rad(-90.0 + 90.0 * k + 15.0 * s)
			pts.append(centers[k] + Vector2(cos(a), sin(a)) * rad)
	draw_colored_polygon(pts, col)

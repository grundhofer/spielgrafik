extends Node2D
## Textfenster im Stil der Palettenspiele um 1990: Doppelrahmen in Palettenfarben, Ortsname mit Farbzyklus
## (Goldrampe läuft durch die Schrift, siehe title.gd und ui_cycle.gdshader), Erzählzeile, drei Antworten mit
## Auswahlpfeil und Parserzeile mit blinkender Schreibmarke. Ortsname in der Pixel-Bastarda Jacquarda Bastarda 9
## (13 px = ihre Rastergröße), Erzählung, Antworten und Parser in Pixel Operator 8 (8 px), damit sie ohne
## Fraktur-Übung lesbar sind. Beide ohne Kantenglättung: Jedes Pixel hat eine Palettenfarbe, der Bildschirm bleibt
## bei höchstens 256 Farben.

# Links unten über Fässern und Kisten: Boote, Wasser mit Spiegelung, Wellen und Laterne bleiben frei.
# Pixel Operator 8 bei 8 px: Großbuchstaben 7 px über, Unterlänge 2 px unter der Grundlinie, Zeilenabstand 10.
const BOX := Rect2i(4, 126, 176, 110)      # x, y, Breite, Höhe (Szenenpixel), 19 % des Bildes
const LINES := ["Die Laterne flackert im", "Wind. Am Kai wartet ein", "Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const BODY_SIZE := 8
const LINE_BASE := [30, 40, 50]
const SEP_Y := [55, 91]
const CHOICE_BASE := [65, 75, 85]
const PARSER_BASE := 102
const SELECT_AT := [1.9, 3.9]     # Auswahl springt 1 -> 2 -> 3

var cyc: Cycler
var font_title: FontFile
var font_body: FontFile
var at := 0.0


static func pixel_font(path: String) -> FontFile:
	var f: FontFile = load(path)
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.generate_mipmaps = false
	f.multichannel_signed_distance_field = false
	return f


func setup(c: Cycler) -> void:
	cyc = c
	font_title = pixel_font("res://fonts/JacquardaBastarda9-Regular.ttf")
	font_body = pixel_font("res://fonts/PixelOperator8.ttf")
	position = Vector2(BOX.position)
	$Title.setup(c, font_title)


func tick(t: float) -> void:
	at = t
	queue_redraw()


func _col(i: int) -> Color:
	return cyc.colors[i]


func _text(x: int, base: int, s: String, col: Color) -> void:
	draw_string(font_body, Vector2(x, base), s, HORIZONTAL_ALIGNMENT_LEFT, -1, BODY_SIZE, col)


func _draw() -> void:
	if cyc == null:
		return
	var w := BOX.size.x
	var h := BOX.size.y
	var fill := _col(0)
	var light := _col(1)
	var dark := _col(2)
	var text := _col(3)
	var gold := _col(10)
	var gold_dim := _col(11)
	# Doppelrahmen: dunkel, hell, dunkel, Fläche; Eckpunkte in Gold
	draw_rect(Rect2(0, 0, w, h), dark)
	draw_rect(Rect2(1, 1, w - 2, h - 2), light)
	draw_rect(Rect2(2, 2, w - 4, h - 4), dark)
	draw_rect(Rect2(3, 3, w - 6, h - 6), fill)
	for p in [Vector2(1, 1), Vector2(w - 2, 1), Vector2(1, h - 2), Vector2(w - 2, h - 2)]:
		draw_rect(Rect2(p, Vector2(1, 1)), gold)
	for i in LINES.size():
		_text(8, LINE_BASE[i], LINES[i], text)
	for sy in SEP_Y:
		for x in range(8, w - 8, 2):
			draw_rect(Rect2(x, sy, 1, 1), light)
	var sel := 0
	for s in SELECT_AT:
		if at >= s:
			sel += 1
	for i in CHOICES.size():
		var base: int = CHOICE_BASE[i]
		_text(10, base, "%d." % (i + 1), gold if i == sel else gold_dim)
		_text(25, base, CHOICES[i], gold if i == sel else text)
		if i == sel:
			for r in 5:                     # Auswahlpfeil 3x5, mittig auf der Höhe der Kleinbuchstaben
				var ln := 3 - absi(r - 2)
				draw_rect(Rect2(5, base - 6 + r, ln, 1), gold)
	# Parserzeile: Eingabe mit Schreibmarke, die mit 2 Hz blinkt (an der Zeit, nicht am Bild)
	_text(8, PARSER_BASE, PARSER, gold_dim)
	if int(floor(at * 2.0)) % 2 == 0:
		var cx := 8 + int(font_body.get_string_size(PARSER + " ", HORIZONTAL_ALIGNMENT_LEFT, -1, BODY_SIZE).x)
		draw_rect(Rect2(cx, PARSER_BASE - 7, 5, 8), gold)

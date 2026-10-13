extends Node2D
## Textfenster wie in Rollenspielen mit Kachelkarte: Ortsschild oben, Erzählzeile mit Schreibmaschinen-Effekt,
## Auswahl mit Zeiger und Parserzeile. Pixel Operator 8 ohne Kantenglättung, alle Koordinaten ganzzahlig.

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const BOX := Rect2i(4, 181, 418, 55)
const DIV_X := 226
const COL_TEXT := Color(0.96, 0.92, 0.82)
const COL_DIM := Color(0.66, 0.68, 0.78)
const COL_SEL := Color(1.0, 0.84, 0.42)
const COL_PARSER := Color(0.55, 0.9, 0.84)
const COL_FILL := Color(0.06, 0.08, 0.15, 0.93)
const COL_EDGE := Color(0.02, 0.02, 0.05)
const COL_BRASS := Color(0.84, 0.66, 0.38)
const COL_BRASS_D := Color(0.45, 0.32, 0.2)
const TYPE_START := 0.3
const TYPE_CPS := 30.0
const PARSER_START := 2.6
const PARSER_CPS := 9.0
const SELECTED := 1

var t := 0.0
var font: FontFile


func _ready() -> void:
	font = load("res://fonts/PixelOperator8.ttf")
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	font.generate_mipmaps = false
	font.multichannel_signed_distance_field = false


func set_time(v: float) -> void:
	t = v
	queue_redraw()


func _text(x: int, top: int, s: String, col: Color) -> void:
	draw_string(font, Vector2(x, top + roundi(font.get_ascent(8))), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, col)


func _width(s: String) -> int:
	return roundi(font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x)


func _frame(r: Rect2i) -> void:
	## Rahmen aus ganzen Pixeln: dunkle Außenlinie, Messinglinie, abgeschrägte Ecken
	var x0 := r.position.x
	var y0 := r.position.y
	var x1 := r.end.x - 1
	var y1 := r.end.y - 1
	draw_rect(Rect2(x0 + 1, y0 + 1, r.size.x - 2, r.size.y - 2), COL_FILL)
	for s in [[x0 + 2, y0, x1 - 2, y0], [x0 + 2, y1, x1 - 2, y1], [x0, y0 + 2, x0, y1 - 2], [x1, y0 + 2, x1, y1 - 2]]:
		draw_rect(Rect2(s[0], s[1], s[2] - s[0] + 1, s[3] - s[1] + 1), COL_EDGE)
	draw_rect(Rect2(x0 + 1, y0 + 1, 1, 1), COL_EDGE)
	draw_rect(Rect2(x1 - 1, y0 + 1, 1, 1), COL_EDGE)
	draw_rect(Rect2(x0 + 1, y1 - 1, 1, 1), COL_EDGE)
	draw_rect(Rect2(x1 - 1, y1 - 1, 1, 1), COL_EDGE)
	draw_rect(Rect2(x0 + 2, y0 + 1, r.size.x - 4, 1), COL_BRASS)
	draw_rect(Rect2(x0 + 1, y0 + 2, 1, r.size.y - 4), COL_BRASS)
	draw_rect(Rect2(x0 + 2, y1 - 1, r.size.x - 4, 1), COL_BRASS_D)
	draw_rect(Rect2(x1 - 1, y0 + 2, 1, r.size.y - 4), COL_BRASS_D)


func _draw() -> void:
	# Ortsschild oben in der Mitte
	var lw := _width(LOCATION)
	var plate := Rect2i(213 - (lw + 16) / 2, 3, lw + 16, 14)
	_frame(plate)
	_text(plate.position.x + 8, plate.position.y + 3, LOCATION, COL_SEL)
	# Textfenster
	_frame(BOX)
	var shown := int(max(0.0, (t - TYPE_START) * TYPE_CPS))
	var y := BOX.position.y + 6
	for line in LINES:
		var n := clampi(shown, 0, line.length())
		_text(BOX.position.x + 8, y, line.substr(0, n), COL_TEXT)
		shown -= line.length()
		y += 11
	# Parserzeile mit blinkender Schreibmarke
	var pn := clampi(int(max(0.0, (t - PARSER_START) * PARSER_CPS)), 0, PARSER.length())
	if t >= PARSER_START - 0.4:
		var ptxt := PARSER.substr(0, maxi(pn, 2))
		var py := BOX.position.y + 39
		_text(BOX.position.x + 8, py, ptxt, COL_PARSER)
		if fmod(t, 0.6) < 0.36:
			draw_rect(Rect2(BOX.position.x + 9 + _width(ptxt), py + 1, 5, 8), COL_PARSER)
	# Trennlinie und Auswahl
	draw_rect(Rect2(DIV_X, BOX.position.y + 6, 1, BOX.size.y - 12), COL_BRASS_D)
	for i in CHOICES.size():
		var cy := BOX.position.y + 6 + i * 14
		var sel := i == SELECTED
		_text(DIV_X + 18, cy, CHOICES[i], COL_SEL if sel else COL_DIM)
		if sel:
			var nx := DIV_X + 8 + (1 if fmod(t, 0.8) < 0.4 else 0)
			for k in 4:     # Zeiger: Dreieck 4 px breit, 7 px hoch
				draw_rect(Rect2(nx + k, cy + 1 + k, 1, 7 - 2 * k), COL_SEL)

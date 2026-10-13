extends Node2D
## Textleiste unter dem Szenenband (y 148..199, 26 % des Bildes): Ort, Erzählzeile mit Schreibmaschine,
## drei Auswahlen, Parserzeile mit Schreibmarke. Pixel Operator 8 ohne Kantenglättung; nur Farben, die in
## beiden Paletten gleich sind (der Palettenwechsel beim Schnitt lässt die Leiste stehen).

const TOP := 148
const COL_BG := Color("#0b0a14")
const COL_LINE := Color("#4a4579")
const COL_TEXT := Color("#f0e2c8")
const COL_DIM := Color("#9aa0b8")
const COL_ACC := Color("#ffd27a")
const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "nimm paket"
const TYPE_START := 0.5
const TYPE_CPS := 30.0            # 1 Zeichen je Bild bei 30 fps
const PARSER_START := 4.3
const PARSER_CPS := 10.0          # 1 Zeichen je 3 Bilder (gleichmäßige Haltezeit)
const SIZE := 8

var font: FontFile
var t := 0.0
var shot := "A"


func _ready() -> void:
	font = load("res://fonts/PixelOperator8.ttf")
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	font.generate_mipmaps = false


func set_time(tt: float, key: String) -> void:
	t = tt
	shot = key
	queue_redraw()


func _draw() -> void:
	draw_rect(Rect2(0, TOP, 320, 200 - TOP), COL_BG)
	draw_rect(Rect2(0, TOP, 320, 1), COL_LINE)
	var x0 := 6
	draw_string(font, Vector2(x0, TOP + 9), LOCATION.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE, COL_ACC)
	# Erzählzeile mit Schreibmaschine, Umbruch nach Wörtern
	var n := clampi(int(floor((t - TYPE_START) * TYPE_CPS + 0.001)), 0, LINE.length())   # +0,001: Rundung der Zeitsumme
	var lines: Array = wrap_words(LINE, 308)
	var shown := 0
	for i in lines.size():
		var ln: String = lines[i]
		var part := ln.substr(0, clampi(n - shown, 0, ln.length()))
		shown += ln.length() + 1
		draw_string(font, Vector2(x0, TOP + 19 + 10 * i), part, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE, COL_TEXT)
	# Auswahlen erscheinen nach dem Text; gewählt ist „Das Paket ansehen“
	if n >= LINE.length():
		var sel := 1
		var col2 := x0 + 14 + maxf(text_w(CHOICES[0]), text_w(CHOICES[2])) + 12
		var pos := [Vector2(x0, TOP + 39), Vector2(col2, TOP + 39), Vector2(x0, TOP + 49)]
		for i in CHOICES.size():
			var p: Vector2 = pos[i]
			draw_string(font, p, str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE, COL_ACC)
			draw_string(font, p + Vector2(10, 0), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE,
				COL_TEXT if i == sel else COL_DIM)
		# Parserzeile mit Schreibmarke (blinkt mit 2,5 Hz)
		var m := clampi(int(floor((t - PARSER_START) * PARSER_CPS + 0.001)), 0, PARSER.length())
		var txt := "> " + PARSER.substr(0, m)
		var pp := Vector2(col2, TOP + 49)
		draw_string(font, pp, txt, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE, COL_TEXT)
		var w := font.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x
		if int(floor(t * 5.0)) % 2 == 0:
			draw_rect(Rect2(pp.x + w + 1, pp.y - 7, 5, 8), COL_ACC)


func text_w(txt: String) -> float:
	return font.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x


func wrap_words(text: String, width: float) -> Array:
	var out := []
	var cur := ""
	for word in text.split(" "):
		var cand := word if cur == "" else cur + " " + word
		if font.get_string_size(cand, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x > width and cur != "":
			out.append(cur)
			cur = word
		else:
			cur = cand
	if cur != "":
		out.append(cur)
	return out

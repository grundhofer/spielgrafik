extends Node2D
## BG3-Textfenster oben über dem Himmel (oberhalb der Horizontzeile läuft Mode 1).
## 2bpp-Regeln: jede 8×8-Kachel hat 3 Farben + durchsichtig aus einer von 4 Paletten [Füllung, Hell, Dunkel];
## Hell und Dunkel sind überall gleich, die Füllung je Kachelzeile bildet Titelleiste und Verlauf.
## Das Fenster liegt auf dem um (4, 4) verschobenen Kachelraster (BG3HOFS/VOFS = −4) und gleitet beim
## Öffnen per VOFS von oben herein. Schrift Pixel Operator 8 ohne Kantenglättung, hell mit Schatten.

const BOX := Rect2i(4, 4, 248, 48)
const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const PARSER := "> nimm paket"
const ROW_PAL := [1, 1, 2, 2, 3, 3]      # Palette je Kachelzeile des Fensters
const TEXT_X := 12
const TITLE_TOP := 3                      # Oberkante der Schrift relativ zum Fenster
const LINE_TOP := [17, 27]
const PARSER_TOP := 37

var font: FontFile
var slide := 0          # VOFS-Versatz in Pixeln (0 = ganz offen)
var visible_win := false
var chars := 0
var parser_chars := 0
var cursor_on := false
@onready var main: Node2D = get_parent()


func _ready() -> void:
	font = load("res://fonts/PixelOperator8.ttf")
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED


func _c(pal: int, k: int) -> Color:
	return main.cgram_color(4 * pal + 1 + k)


func _draw() -> void:
	if not visible_win:
		return
	var x0 := BOX.position.x
	var y0 := BOX.position.y - slide
	var w := BOX.size.x
	var h := BOX.size.y
	var lo := _c(0, 2)
	var hi := _c(0, 1)
	for r in 6:      # Füllung je Kachelzeile (Ecken bleiben frei)
		var inset := 2 if r == 0 or r == 5 else 0
		draw_rect(Rect2(x0 + inset, y0 + r * 8, w - 2 * inset, 8), _c(ROW_PAL[r], 0))
	# Rahmen: außen dunkel, dann hell, dann dunkel; Ecken abgerundet (äußerste Pixel durchsichtig)
	for i in 3:
		var col := lo if i != 1 else hi
		draw_rect(Rect2(x0 + 2, y0 + i, w - 4, 1), col)
		draw_rect(Rect2(x0 + 2, y0 + h - 1 - i, w - 4, 1), col)
		draw_rect(Rect2(x0 + i, y0 + 2, 1, h - 4), col)
		draw_rect(Rect2(x0 + w - 1 - i, y0 + 2, 1, h - 4), col)
	for c in [Vector2i(1, 1), Vector2i(w - 2, 1), Vector2i(1, h - 2), Vector2i(w - 2, h - 2)]:
		draw_rect(Rect2(x0 + c.x, y0 + c.y, 1, 1), lo)
	draw_rect(Rect2(x0 + 3, y0 + 15, w - 6, 1), lo)       # Trennlinie unter der Titelleiste
	_text(LOCATION, TEXT_X, y0 + TITLE_TOP)
	var left := chars
	for i in LINES.size():
		if left <= 0:
			break
		var s: String = LINES[i]
		_text(s.substr(0, mini(left, s.length())), TEXT_X, y0 + LINE_TOP[i])
		left -= s.length()
	if parser_chars > 0 or cursor_on:
		var s := PARSER.substr(0, parser_chars)
		_text(s, TEXT_X, y0 + PARSER_TOP)
		if cursor_on:
			var cw := int(font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x)
			draw_rect(Rect2(TEXT_X + cw + 2, y0 + PARSER_TOP + 1, 5, 7), lo)
			draw_rect(Rect2(TEXT_X + cw + 1, y0 + PARSER_TOP, 5, 7), hi)


func _text(s: String, x: int, top: int) -> void:
	var base := top + roundi(font.get_ascent(8))
	draw_string(font, Vector2(x + 1, base + 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, _c(0, 2))
	draw_string(font, Vector2(x, base), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, _c(0, 1))

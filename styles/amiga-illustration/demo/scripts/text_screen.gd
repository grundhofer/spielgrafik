extends Node2D
## Textschirm: eigener Bildschirm mit 4 Farben in den Grundfarben der Workbench 1.x (Blau, Weiß, Schwarzblau,
## Orange). Statuszeile oben (invers), darunter das Bild, unten Raumtext und Parser mit orangem Blockcursor.
## Proportionale Pixelschrift ohne Kantenglättung, alle Positionen auf ganzen Pixeln.
## Fünf Zeilen à 9 px (156..200): Raumtext (2 Zeilen), Eingabe, Antwort, neue Eingabezeile. Der Zugzähler
## springt mit der Eingabetaste um eins weiter.

const BLUE := Color8(0x00, 0x55, 0xAA)
const WHITE := Color8(0xFF, 0xFF, 0xFF)
const INK := Color8(0x00, 0x00, 0x22)
const ORANGE := Color8(0xFF, 0x88, 0x00)
const SIZE := 8
const LINE_H := 9
const TEXT_X := 4
const TEXT_Y := 156
const LOCATION := "Hafen von Lornholm"
const MOVES := 12
const LINES := ["Die Laterne flackert im Wind. Am Kai wartet ein", "Paket auf dich."]
const PROMPT := "> "
const COMMAND := "nimm paket"
const ANSWER := "Der Dachs reicht dir das Paket."
# Abstände der Tastendrücke (s), fest wie eine echte Eingabe mit kleinen Pausen
const KEY_GAPS := [0.0, 0.11, 0.09, 0.12, 0.22, 0.10, 0.13, 0.09, 0.11, 0.12]

@onready var main: Node = get_parent()
var font: FontFile


func _ready() -> void:
	font = load("res://fonts/PixelOperator8.ttf")
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	font.generate_mipmaps = false
	font.multichannel_signed_distance_field = false


func _text(x: int, top: int, s: String, col: Color) -> void:
	draw_string(font, Vector2(x, top + roundi(font.get_ascent(SIZE))), s, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE, col)


func _width(s: String) -> int:
	return roundi(font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x)


func typed_chars(tt: float) -> int:
	var k := 0
	var at: float = main.TYPE_T0
	for i in COMMAND.length():
		at += float(KEY_GAPS[i])
		if tt >= at:
			k = i + 1
	return k


func _draw() -> void:
	var tt: float = main.t
	var entered: bool = tt >= main.ENTER_T
	draw_rect(Rect2(0, 0, 320, 200), BLUE)
	# Statuszeile (invers)
	draw_rect(Rect2(0, 0, 320, 10), WHITE)
	_text(4, 1, LOCATION, INK)
	var moves := "Züge: %d" % (MOVES + (1 if entered else 0))
	_text(316 - _width(moves), 1, moves, INK)
	# Raumtext
	for i in LINES.size():
		_text(TEXT_X, TEXT_Y + i * LINE_H, LINES[i], WHITE)
	# Parser: Eingabezeile, nach der Eingabetaste Antwort und neue Eingabezeile
	var y := TEXT_Y + LINES.size() * LINE_H
	var n := typed_chars(tt)
	_text(TEXT_X, y, PROMPT, ORANGE)
	_text(TEXT_X + _width(PROMPT), y, COMMAND.substr(0, n), WHITE)
	var cur_y := y
	var cur_x := TEXT_X + _width(PROMPT + COMMAND.substr(0, n)) + 1
	if entered:
		_text(TEXT_X, y + LINE_H, ANSWER, WHITE)
		cur_y = y + 2 * LINE_H
		_text(TEXT_X, cur_y, PROMPT, ORANGE)
		cur_x = TEXT_X + _width(PROMPT) + 1
	# Blockcursor: beim Tippen ständig an, sonst blinkend
	var typing := n > 0 and n < COMMAND.length() and not entered
	var on := typing or int(floor(tt * 2.5)) % 2 == 0
	if on:
		draw_rect(Rect2(cur_x, cur_y, 5, 8), ORANGE)

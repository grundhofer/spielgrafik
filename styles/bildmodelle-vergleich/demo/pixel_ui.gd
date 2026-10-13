extends Node2D
## Textbox der Schlussszene im VGA-Stil: Leiste 320×42 unter der Szene, Pixel Operator 8 ohne Kantenglättung,
## Ort gelb, Erzähltext tippt sich ein, Parserzeile mit blinkendem Cursor. Rechts in der Ortszeile steht, aus
## welchem Modell Bild und Figur stammen.

const TOP := 138
const PANEL := Color8(12, 12, 36)
const RIM := Color8(88, 96, 168)
const RIM_DARK := Color8(36, 40, 84)
const YELLOW := Color8(252, 216, 96)
const WHITE := Color8(232, 232, 240)
const CYAN := Color8(112, 224, 224)
const TAG := Color8(140, 148, 212)
const CODEX := Color8(236, 168, 96)
const AGY := Color8(120, 184, 228)

var tt := 0.0
var font: FontFile


func _ready() -> void:
	font = load("res://fonts/PixelOperator8.ttf")
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED


func _text(x: int, line_top: int, s: String, col: Color) -> int:
	draw_string(font, Vector2(x, line_top + roundi(font.get_ascent(8))), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, col)
	return x + int(font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x)


func _width(s: String) -> int:
	return int(font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x)


func _wrap(s: String, w: int) -> PackedStringArray:
	var out := PackedStringArray()
	var cur := ""
	for word in s.split(" "):
		var cand := word if cur == "" else cur + " " + word
		if _width(cand) > w and cur != "":
			out.append(cur)
			cur = word
		else:
			cur = cand
	if cur != "":
		out.append(cur)
	return out


func _draw() -> void:
	var main = get_parent().get_parent()
	draw_rect(Rect2(0, TOP, 320, 42), PANEL)
	draw_rect(Rect2(0, TOP, 320, 1), RIM)
	draw_rect(Rect2(0, TOP + 1, 320, 1), RIM_DARK)
	# Ortszeile + Herkunft
	_text(5, TOP + 4, "Hafen von Lornholm", YELLOW)
	var tag := ["Bild: ", "Codex", "  Dachs: ", "agy"]
	var cols := [TAG, CODEX, TAG, AGY]
	var w := 0
	for s in tag:
		w += _width(s)
	var x := 315 - w
	for i in tag.size():
		x = _text(x, TOP + 4, tag[i], cols[i])
	# Erzähltext tippt sich ein (Wortumbruch vorab über den ganzen Satz, damit nichts springt)
	var lines := _wrap(main.LINE, 310)
	var n := int(clampf((tt - main.TYPE_START) * main.TYPE_CPS, 0.0, 1000.0))
	var y := TOP + 14
	for ln in lines:
		var shown := ln.substr(0, clampi(n, 0, ln.length()))
		_text(5, y, shown, WHITE)
		n -= ln.length() + 1
		y += 9
	# Parserzeile
	var t_line: float = main.TYPE_START + float(main.LINE.length()) / main.TYPE_CPS + 0.1
	var pn := int(clampf((tt - t_line) * main.PARSER_CPS, 0.0, 100.0))
	var ps: String = main.PARSER.substr(0, mini(pn, main.PARSER.length()))
	var cx := _text(5, TOP + 32, ps if ps != "" else ">", CYAN)
	if fmod(tt, 0.5) < 0.3:
		draw_rect(Rect2(cx + 1, TOP + 32 + 7, 5, 1), CYAN)

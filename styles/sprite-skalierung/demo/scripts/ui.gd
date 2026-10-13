extends Node2D
## Textfenster oben über dem Himmel, Arcade-Schrift Press Start 2P in 8 px ohne Kantenglättung.
## Ort in Gelb mit rotem Schatten, Text weiß mit dunklem Schatten, Parserzeile grün mit blinkendem Block.

const BOX := Rect2i(4, 4, 312, 44)
const LOCATION := "HAFEN VON LORNHOLM"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const PARSER := "> nimm paket"
const TX := 11
const ROWS := [8, 18, 27, 37]
const CPS := 40.0
const PARSER_T := 1.9
const PARSER_CPS := 14.0

var main: Node2D
var font: FontFile
var tt := 0.0


func setup(m: Node2D) -> void:
	main = m
	font = FontFile.new()
	font.data = FileAccess.get_file_as_bytes("res://fonts/PressStart2P-Regular.ttf")
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	# Die Schrift setzt "fl" sonst als Ligatur in eine Zelle
	var ts := TextServerManager.get_primary_interface()
	font.opentype_feature_overrides = {ts.name_to_tag("liga"): 0, ts.name_to_tag("clig"): 0}
	z_index = 4000


func refresh(t: float) -> void:
	tt = t
	queue_redraw()


func _c(r: int, g: int, b: int) -> Color:
	return main.q5(Color8(r, g, b))


func _draw() -> void:
	var x0 := BOX.position.x
	var y0 := BOX.position.y
	var w := BOX.size.x
	var h := BOX.size.y
	# Rahmen: außen weiß, innen hellblau, Füllung dunkelblau; Ecken um ein Pixel abgeschrägt
	draw_rect(Rect2(x0 + 1, y0, w - 2, h), _c(250, 250, 250))
	draw_rect(Rect2(x0, y0 + 1, w, h - 2), _c(250, 250, 250))
	draw_rect(Rect2(x0 + 1, y0 + 1, w - 2, h - 2), _c(60, 150, 255))
	draw_rect(Rect2(x0 + 2, y0 + 2, w - 4, h - 4), _c(10, 18, 84))
	_text(LOCATION, TX, ROWS[0], _c(255, 214, 0), _c(190, 24, 24))
	var left := int(floor(maxf(tt - 0.1, 0.0) * CPS))
	for i in LINES.size():
		if left <= 0:
			break
		var s: String = LINES[i]
		_text(s.substr(0, mini(left, s.length())), TX, ROWS[1 + i], _c(250, 250, 250), _c(0, 0, 40))
		left -= s.length()
	if tt >= PARSER_T - 0.3:
		var n := clampi(int(floor((tt - PARSER_T) * PARSER_CPS)) + 1, 0, PARSER.length()) if tt >= PARSER_T else 0
		var s := PARSER.substr(0, n)
		_text(s, TX, ROWS[3], _c(90, 255, 110), _c(0, 60, 0))
		if fmod(tt, 0.5) < 0.3:
			var cw := 8 * s.length()
			draw_rect(Rect2(TX + cw + 1, ROWS[3], 7, 8), _c(90, 255, 110))


func _text(s: String, x: int, top: int, col: Color, shade: Color) -> void:
	var base := top + roundi(font.get_ascent(8))
	draw_string(font, Vector2(x + 1, base + 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, shade)
	draw_string(font, Vector2(x, base), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, col)

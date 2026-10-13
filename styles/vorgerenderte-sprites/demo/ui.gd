extends Node2D
## Textbox im Stil der vorgerenderten Spiele: Holzrahmen, Messingschild und drehendes Paket sind in
## Blender gerendert und auf 15 Farben gebracht (blender/render_ui.py, scripts/reduce_sprites.py);
## Godot zeichnet nur die Pixelschrift (Pixel Operator 8 / HB 8, CC0, ohne Kantenglättung) dazu.

const FONT := preload("res://fonts/PixelOperator8.ttf")
const FONT_B := preload("res://fonts/PixelOperatorHB8.ttf")
const FS := 8

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const FRAME_POS := Vector2i(4, 177)
const PLAQUE_POS := Vector2i(12, 169)
const COL2_X := 264
const ROW0 := 194          # erste Grundlinie
const ROW_H := 11

const TYPE_T := 0.4        # Text beginnt
const CPS := 40.0          # Zeichen pro Sekunde
const CHOICE_T := 2.2
const PARSER_T := 2.9
const SELECTED := 1

const INK := Color("1a0f10")
const FILL := Color(0.055, 0.04, 0.085, 0.86)
const TEXT := Color("f8e8c4")
const DIM := Color("c8b494")
const HOT := Color("ffc458")
const ENGRAVE := Color("2a1406")

var t := 0.0
var frame_tex: Texture2D
var plaque_tex: Texture2D
var cursor_tex: Texture2D
var cursor_n := 8


func _ready() -> void:
	frame_tex = load("res://sprites/ui_frame.png")
	plaque_tex = load("res://sprites/ui_plaque.png")
	cursor_tex = load("res://sprites/ui_cursor.png")
	cursor_n = int(cursor_tex.get_width() / cursor_tex.get_height() * 1.0 + 0.5)
	var f := FileAccess.open("res://sprites/ui_cursor.json", FileAccess.READ)
	if f:
		cursor_n = int(JSON.parse_string(f.get_as_text())["frames"])


func set_time(tt: float) -> void:
	t = tt
	queue_redraw()


func _text(font: Font, pos: Vector2, s: String, col: Color, shadow := INK) -> void:
	draw_string(font, pos + Vector2(1, 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, shadow)
	draw_string(font, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, col)


func _draw() -> void:
	var fs := frame_tex.get_size()
	# Füllung hinter dem Rahmen (halb durchscheinend wie die Farbrechnung der Konsole)
	draw_rect(Rect2(FRAME_POS.x + 4, FRAME_POS.y + 4, fs.x - 8, fs.y - 8), FILL)
	draw_texture(frame_tex, Vector2(FRAME_POS))
	# Messingschild mit eingravierter Schrift
	draw_texture(plaque_tex, Vector2(PLAQUE_POS))
	var ps := plaque_tex.get_size()
	var w := FONT_B.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, FS).x
	var px := PLAQUE_POS.x + int((ps.x - w) / 2)
	draw_string(FONT_B, Vector2(px, PLAQUE_POS.y + 11), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, ENGRAVE)
	# Erzähltext mit Schreibmaschine
	var n := int(max(0.0, (t - TYPE_T) * CPS))
	var y := ROW0
	for line in LINES:
		var s: String = line.substr(0, clampi(n, 0, line.length()))
		_text(FONT, Vector2(14, y), s, TEXT)
		n -= line.length() + 4
		y += ROW_H
	# Auswahl, Zeile für Zeile
	for i in CHOICES.size():
		if t < CHOICE_T + 0.15 * i:
			continue
		var col := HOT if i == SELECTED else DIM
		_text(FONT, Vector2(COL2_X, ROW0 + i * ROW_H), CHOICES[i], col)
	if t >= CHOICE_T:
		var k := int(floor(t * 10.0)) % cursor_n
		var cw := cursor_tex.get_width() / cursor_n
		var ch := cursor_tex.get_height()
		draw_texture_rect_region(cursor_tex, Rect2(COL2_X - cw - 2, ROW0 + SELECTED * ROW_H - ch + 2, cw, ch),
				Rect2(k * cw, 0, cw, ch))
	# Parserzeile mit blinkender Schreibmarke
	if t >= PARSER_T:
		var m := clampi(int((t - PARSER_T) * 12.0), 0, PARSER.length())
		var ps2 := PARSER.substr(0, m)
		var py := ROW0 + 3 * ROW_H - 1
		_text(FONT, Vector2(14, py), ps2, HOT)
		var cx := 14 + FONT.get_string_size(ps2, HORIZONTAL_ALIGNMENT_LEFT, -1, FS).x + 1
		if int(floor(t * 2.0)) % 2 == 0 or m < PARSER.length():
			draw_rect(Rect2(cx, py - 7, 5, 8), HOT)

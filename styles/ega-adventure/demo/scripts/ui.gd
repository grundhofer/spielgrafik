extends Node2D
## Oberfläche wie bei den Parser-Adventures: Statuszeile oben (Zeile 0), Eingabezeile mit Prompt unter dem
## Bild (Zeile 22), Meldungsfenster weiß mit rotem Rahmen. Systemschrift 8×8 (eigene Zeichnung, CC0),
## 40 Zeichen je Zeile auf 320 Pixeln. Rahmenlinien senkrecht 2 px, waagerecht 1 px breit, wie im
## 160er-Raster gezeichnet.

const EGA_WHITE := Color8(255, 255, 255)
const EGA_BLACK := Color8(0, 0, 0)
const EGA_RED := Color8(170, 0, 0)
const CGA_MAGENTA := Color8(255, 85, 255)
const MESSAGE := ["Die Laterne flackert im", "Wind. Am Kai wartet ein", "Paket auf dich."]
const PROMPT := "> "

var font: Texture2D = preload("res://fonts/font8.png")
var glyphs := ""

@onready var main: Node2D = get_parent()


func _ready() -> void:
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://fonts/font8.json"))
	glyphs = meta["chars"]


func _text(s: String, x: int, y: int, col: Color) -> void:
	for i in s.length():
		var idx := glyphs.find(s[i])
		if idx < 0:
			idx = glyphs.find("?")
		if s[i] == " ":
			continue
		var src := Rect2((idx % 16) * 8, (idx / 16) * 8, 8, 8)
		draw_texture_rect_region(font, Rect2(x + i * 8, y, 8, 8), src, col)


func _draw() -> void:
	var red := CGA_MAGENTA if main.cga else EGA_RED
	# Statuszeile
	draw_rect(Rect2(0, 0, 320, 8), EGA_WHITE)
	_text("Hafen von Lornholm", 8, 0, EGA_BLACK)
	_text("Punkte: %d von 150" % main.score, 22 * 8, 0, EGA_BLACK)
	# Eingabezeile
	var line: String = PROMPT + main.typed
	_text(line, 0, 176, EGA_WHITE)
	if fmod(main.t, 0.5) < 0.3 or (main.typed != "" and main.typed.length() < 10):
		_text("_", line.length() * 8, 176, EGA_WHITE)
	# Meldungsfenster
	if main.msg_visible:
		var bx := 58
		var by := 11
		var bw := 196
		var bh := 34
		draw_rect(Rect2(bx, by, bw, bh), EGA_WHITE)
		draw_rect(Rect2(bx + 2, by + 1, bw - 4, 1), red)
		draw_rect(Rect2(bx + 2, by + bh - 2, bw - 4, 1), red)
		draw_rect(Rect2(bx + 2, by + 1, 2, bh - 2), red)
		draw_rect(Rect2(bx + bw - 4, by + 1, 2, bh - 2), red)
		for i in MESSAGE.size():
			_text(MESSAGE[i], 64, 16 + i * 8, EGA_BLACK)

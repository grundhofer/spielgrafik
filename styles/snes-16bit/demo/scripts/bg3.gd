extends Node2D
## BG3: Textfenster wie in Rollenspielen der 16-Bit-Konsolen. 2bpp-Ebene: jede 8×8-Kachel hat 3 Farben
## + Durchsichtig aus einer von 4 Paletten (CGRAM 0..15). Jede Palette = [Füllung, Hell, Dunkel]; Hell und
## Dunkel sind in allen vier gleich, die Füllung wird je zwei Kachelzeilen dunkler (Verlauf in Stufen).
## Fenster beginnen auf dem Kachelraster (x, y Vielfache von 8). Rahmen: Dunkel, Hell, Hell, Dunkel mit
## abgerundeten (durchsichtigen) Ecken. Schrift Pixel Operator 8 ohne Kantenglättung, hell mit dunklem Schatten.

const TITLE := Rect2i(56, 8, 144, 16)
const BOX := Rect2i(8, 152, 232, 64)
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const LOCATION := "Hafen von Lornholm"
const TEXT_X := 16
const LINE_Y0 := 158
const LINE_DY := 10
const CHOICE_X := 30
const HAND := [
	"..DDD.....",
	".DLLLDDDD.",
	"DLLLLLLLLD",
	"DLLLLDDDD.",
	"DLLLLD....",
	".DDDD.....",
]
const CORNER := ["..DD", ".DLL", "DLLL", "DLLD"]

var font: FontFile
@onready var main: Node2D = get_parent()


func _ready() -> void:
	font = load("res://fonts/PixelOperator8.ttf")
	font.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	font.hinting = TextServer.HINTING_NONE
	font.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED


func _pal(i: int) -> Color:
	return main.cgram_base[i]


func _window(r: Rect2i, open: float, pal_of_row: Callable) -> Rect2i:
	## Fenster öffnet sich kachelzeilenweise von der Mitte aus; gibt das sichtbare Rechteck zurück.
	var rows := r.size.y / 8
	var vis := clampi(int(ceil(open * rows)), 0, rows)
	if vis < 2:
		return Rect2i()
	var top_row := (rows - vis) / 2
	var rr := Rect2i(r.position.x, r.position.y + top_row * 8, r.size.x, vis * 8)
	var light := _pal(2)
	var dark := _pal(3)
	for k in vis:
		var p: int = pal_of_row.call(top_row + k)
		draw_rect(Rect2(rr.position.x, rr.position.y + k * 8, rr.size.x, 8), _pal(4 * p + 1))
	var x0 := rr.position.x
	var y0 := rr.position.y
	var x1 := rr.end.x - 1
	var y1 := rr.end.y - 1
	# Kanten: Dunkel, Hell, Hell, Dunkel
	var cols := [dark, light, light, dark]
	for i in 4:
		draw_rect(Rect2(x0 + 4, y0 + i, rr.size.x - 8, 1), cols[i])
		draw_rect(Rect2(x0 + 4, y1 - i, rr.size.x - 8, 1), cols[i])
		draw_rect(Rect2(x0 + i, y0 + 4, 1, rr.size.y - 8), cols[i])
		draw_rect(Rect2(x1 - i, y0 + 4, 1, rr.size.y - 8), cols[i])
	# Ecken 4×4 (gespiegelt); '.' bleibt durchsichtig
	for cy in 4:
		for cx in 4:
			var ch: String = CORNER[cy][cx]
			var c: Color = Color(0, 0, 0, 0)
			if ch == ".":
				continue
			c = dark if ch == "D" else light
			draw_rect(Rect2(x0 + cx, y0 + cy, 1, 1), c)
			draw_rect(Rect2(x1 - cx, y0 + cy, 1, 1), c)
			draw_rect(Rect2(x0 + cx, y1 - cy, 1, 1), c)
			draw_rect(Rect2(x1 - cx, y1 - cy, 1, 1), c)
	return rr


func _text(s: String, x: int, top: int) -> void:
	var base := top + roundi(font.get_ascent(8))
	draw_string(font, Vector2(x + 1, base + 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, _pal(3))
	draw_string(font, Vector2(x, base), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, _pal(2))


func _hand(x: int, y: int) -> void:
	for r in HAND.size():
		for c in HAND[r].length():
			var ch: String = HAND[r][c]
			if ch == "D":
				draw_rect(Rect2(x + c, y + r, 1, 1), _pal(3))
			elif ch == "L":
				draw_rect(Rect2(x + c, y + r, 1, 1), _pal(2))


func _draw() -> void:
	var tr := _window(TITLE, main.title_open, func(row): return row)
	if tr.size.y == TITLE.size.y:
		var w := font.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x
		_text(LOCATION, TITLE.position.x + roundi((TITLE.size.x - w) / 2.0), TITLE.position.y + 4)
	var br := _window(BOX, main.box_open, func(row): return mini(3, row / 2))
	if br.size.y < BOX.size.y:
		return
	var left: int = main.chars
	for i in LINES.size():
		var s: String = LINES[i]
		if left <= 0:
			break
		_text(s.substr(0, mini(left, s.length())), TEXT_X, LINE_Y0 + i * LINE_DY)
		left -= s.length()
	if main.choices:
		for i in CHOICES.size():
			_text(CHOICES[i], CHOICE_X, LINE_Y0 + (2 + i) * LINE_DY)
		if main.cursor >= 0 and main.cursor_on:
			_hand(TEXT_X, LINE_Y0 + (2 + main.cursor) * LINE_DY + 1)

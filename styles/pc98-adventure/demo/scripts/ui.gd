extends Node2D
## Oberfläche des Befehlsmenü-Adventures, gezeichnet in Palettenindizes (Rotkanal = Index / 15):
## Bildfenster mit Zierrahmen, rechts Ortsfenster, Befehlsmenü und Objektliste, unten das Textfenster,
## in dem der Text Zeichen für Zeichen erscheint. Bitmapschrift aus DotGothic16 (16-px-Punktraster, Latein
## halbbreit 8 px wie die ANK-Zeichen der Vorbilder), als Atlas vorgerastert (scripts/build_font.py).

const SCENE := Rect2i(12, 12, 416, 256)
const LOC_RECT := Rect2i(440, 12, 188, 48)
const CMD_RECT := Rect2i(440, 72, 188, 120)
const OBJ_RECT := Rect2i(440, 204, 188, 64)
const TEXT_RECT := Rect2i(12, 280, 616, 68)
const FS := 16                       # Schriftgröße = Punktraster der Schrift

const LOCATION := "Hafen von Lornholm"
const TIME_OF_DAY := "Abenddämmerung"
const NAME := "【Dachs-Kurier】"
const LINES := ["「Die Laterne flackert im Wind.", "　Am Kai wartet ein Paket auf dich.」"]
const COMMANDS := ["Ansehen", "Nehmen", "Sprechen", "Gehen"]
const OBJECTS := ["Paket", "Laterne", "Seil"]

# Zeitplan in Bildern (30 Bilder/s), muss zu main.gd passen
const TEXT_FROM := 36
const CHAR_FRAMES := 1               # ein Zeichen je Bild (30 Zeichen/s)
const PAUSE_AFTER := {".": 9, ",": 5}
const CURSOR_MOVE := 129             # Cursor springt von "Ansehen" auf "Nehmen"
const CMD_PICK := 141                # "Nehmen" gewählt: Balken invers, Objektliste aktiv
const OBJ_PICK := 162                # "Paket" gewählt

# Register (aus meta.json über Namen): siehe build_assets.py
var C := {}
var atlas: Texture2D
var glyphs := {}
const CELL_TOP := 4                  # Leerzeilen über der Versalhöhe in der Atlaszelle
var f := 0
var char_frames: Array[int] = []     # Bild, in dem Zeichen i erscheint (über beide Zeilen)
var text_end := 0
var pause_frames := {}               # Bilder, in denen gerade eine Satzpause läuft
var backdrop: ImageTexture

@onready var main: Node = get_parent().get_parent()


func _ready() -> void:
	atlas = load("res://fonts/dotgothic16_atlas.png")
	var fm: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://fonts/dotgothic16_atlas.json"))
	glyphs = fm["glyphs"]
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/meta.json"))
	var pal: Array = meta["palette"]
	C = {
		"black": _near(pal, "000000"), "cream": _near(pal, "eeddbb"), "peach": _near(pal, "ee9977"),
		"steel": _near(pal, "778899"), "indigo": _near(pal, "444488"), "navy": _near(pal, "222266"),
		"plum": _near(pal, "221122"), "violet": _near(pal, "775599"), "red": _near(pal, "993322"),
	}
	backdrop = _make_backdrop()
	var fr := TEXT_FROM
	for line in LINES:
		for ch in line:
			char_frames.append(fr)
			fr += CHAR_FRAMES
			if PAUSE_AFTER.has(ch):
				for p in int(PAUSE_AFTER[ch]):
					pause_frames[fr + p] = true
				fr += int(PAUSE_AFTER[ch])
	text_end = fr


static func _near(pal: Array, hx: String) -> int:
	## Index der Palettenfarbe, die hx am nächsten liegt (die Palette entsteht im Build-Skript)
	var want := Color.html(hx)
	var best := 0
	var bd := 1e9
	for i in pal.size():
		var c := Color.html(String(pal[i]))
		var d := (c.r - want.r) ** 2 + (c.g - want.g) ** 2 + (c.b - want.b) ** 2
		if d < bd:
			bd = d
			best = i
	return best


static func ic(i: int) -> Color:
	return Color(i / 15.0, 0.0, 0.0, 1.0)


func is_typing(fr: int) -> bool:
	return fr >= TEXT_FROM and fr < text_end and not pause_frames.has(fr)


func set_frame(fr: int) -> void:
	f = fr
	queue_redraw()


func _text(x: int, top: int, s: String, col: int) -> void:
	## Zeichen aus dem Atlas in Registerfarbe col; top = obere Kante des 16-px-Zeichenkastens
	var cx := x
	for ch in s:
		var g: Array = glyphs.get(ch, glyphs["?"])
		var w := int(g[2])
		var h := int(g[3])
		draw_texture_rect_region(atlas, Rect2(cx, top - CELL_TOP, w, h), Rect2(g[0], g[1], w, h), ic(col))
		cx += int(g[4])


func _width(s: String) -> int:
	var w := 0
	for ch in s:
		w += int(glyphs.get(ch, glyphs["?"])[4])
	return w


func _rect(r: Rect2i, col: int) -> void:
	draw_rect(Rect2(r), ic(col))


func _frame(inner: Rect2i) -> void:
	## Zierrahmen: schwarze Fuge, helle Doppellinie mit dunklem Zwischenraum, Eckbeschläge.
	var o := inner.grow(4)
	_rect(o, C["black"])
	_rect(o.grow(-1), C["steel"])
	_rect(o.grow(-2), C["indigo"])
	_rect(o.grow(-3), C["steel"])
	_rect(inner, C["black"])
	# Eckbeschläge: 5x5-Raute in Pfirsich mit schwarzem Kern
	for p in [o.position, Vector2i(o.end.x - 1, o.position.y), Vector2i(o.position.x, o.end.y - 1), o.end - Vector2i.ONE]:
		var c: Vector2i = p
		_rect(Rect2i(c.x - 2, c.y, 5, 1), C["peach"])
		_rect(Rect2i(c.x, c.y - 2, 1, 5), C["peach"])
		_rect(Rect2i(c.x - 1, c.y - 1, 3, 3), C["peach"])
		_rect(Rect2i(c.x, c.y, 1, 1), C["black"])


func _cursor(x: int, top: int, col: int) -> void:
	## Dreieck-Cursor (7 px hoch) vor einem Menüeintrag, mittig zur Schrift
	for r in 7:
		var w := 4 - absi(r - 3)
		_rect(Rect2i(x, top + 5 + r, w, 1), col)


func _draw() -> void:
	# Hintergrund: Schachbrett aus zwei dunklen Registern, Loch für das Bildfenster (Textur aus _ready)
	draw_texture(backdrop, Vector2.ZERO)

	# Bildfenster: nur der Rahmen; das Bild selbst liegt als Sprite darunter (BG, Water, Badger)
	_frame_ring(SCENE)

	# Ortsfenster
	_frame(LOC_RECT)
	_text(LOC_RECT.position.x + (LOC_RECT.size.x - _width(LOCATION)) / 2, LOC_RECT.position.y + 6, LOCATION, C["peach"])
	_text(LOC_RECT.position.x + (LOC_RECT.size.x - _width(TIME_OF_DAY)) / 2, LOC_RECT.position.y + 26, TIME_OF_DAY, C["steel"])

	# Befehlsmenü
	_frame(CMD_RECT)
	var row0 := CMD_RECT.position.y + 8
	var cur := 0 if f < CURSOR_MOVE else 1
	for i in COMMANDS.size():
		var top := row0 + i * 28
		var x := CMD_RECT.position.x + 30
		if i == 1 and f >= CMD_PICK:
			_rect(Rect2i(CMD_RECT.position.x + 22, top - 2, CMD_RECT.size.x - 34, FS + 4), C["steel"])
			_text(x, top, COMMANDS[i], C["black"])
		else:
			_text(x, top, COMMANDS[i], C["cream"])
	if f < CMD_PICK:
		_cursor(CMD_RECT.position.x + 12, row0 + cur * 28, C["peach"])

	# Objektliste: vor der Befehlswahl grau, danach aktiv mit Cursor
	_frame(OBJ_RECT)
	var active := f >= CMD_PICK
	for i in OBJECTS.size():
		var top := OBJ_RECT.position.y + 2 + i * 20
		var x := OBJ_RECT.position.x + 30
		if active and i == 0 and f >= OBJ_PICK:
			_rect(Rect2i(OBJ_RECT.position.x + 22, top - 1, CMD_RECT.size.x - 34, FS + 2), C["steel"])
			_text(x, top, OBJECTS[i], C["black"])
		else:
			_text(x, top, OBJECTS[i], C["cream"] if active else C["indigo"])
	if active and f < OBJ_PICK:
		_cursor(OBJ_RECT.position.x + 12, OBJ_RECT.position.y + 2, C["peach"])

	# Textfenster
	_frame(TEXT_RECT)
	var tx := TEXT_RECT.position.x + 12
	var ty := TEXT_RECT.position.y + 4
	if f >= TEXT_FROM - 6:
		_text(tx, ty, NAME, C["peach"])
	var shown := 0
	for fr in char_frames:
		if fr <= f:
			shown += 1
	var k := 0
	var last_end := Vector2i(tx, ty + 20)
	for li in LINES.size():
		var line: String = LINES[li]
		var n := clampi(shown - k, 0, line.length())
		if n > 0:
			var s := line.substr(0, n)
			_text(tx, ty + 20 + li * 20, s, C["cream"])
			last_end = Vector2i(tx + _width(s), ty + 20 + li * 20)
		k += line.length()
	# Weiter-Zeichen blinkt nach dem Satzende
	if f >= text_end + 3 and f < CMD_PICK and ((f - text_end - 3) / 8) % 2 == 0:
		_text(last_end.x + 4, last_end.y, "▼", C["peach"])


func _make_backdrop() -> ImageTexture:
	## 50-%-Raster aus zwei dunklen Registern über den ganzen Schirm, Bildfenster durchsichtig
	var img := Image.create_empty(640, 360, false, Image.FORMAT_RGBA8)
	var a := ic(C["plum"])
	var b := ic(C["navy"])
	for y in 360:
		for x in 640:
			img.set_pixel(x, y, a if (x + y) % 2 == 0 else b)
	img.fill_rect(Rect2i(SCENE.position, SCENE.size), Color(0, 0, 0, 0))
	return ImageTexture.create_from_image(img)


func _frame_ring(inner: Rect2i) -> void:
	## Rahmen ohne Füllung (für das Bildfenster)
	var o := inner.grow(4)
	for ring in [[0, C["black"]], [1, C["steel"]], [2, C["indigo"]], [3, C["steel"]]]:
		var rr := o.grow(-int(ring[0]))
		var col: int = ring[1]
		_rect(Rect2i(rr.position.x, rr.position.y, rr.size.x, 1), col)
		_rect(Rect2i(rr.position.x, rr.end.y - 1, rr.size.x, 1), col)
		_rect(Rect2i(rr.position.x, rr.position.y, 1, rr.size.y), col)
		_rect(Rect2i(rr.end.x - 1, rr.position.y, 1, rr.size.y), col)
	for p in [o.position, Vector2i(o.end.x - 1, o.position.y), Vector2i(o.position.x, o.end.y - 1), o.end - Vector2i.ONE]:
		var c: Vector2i = p
		_rect(Rect2i(c.x - 2, c.y, 5, 1), C["peach"])
		_rect(Rect2i(c.x, c.y - 2, 1, 5), C["peach"])
		_rect(Rect2i(c.x - 1, c.y - 1, 3, 3), C["peach"])
		_rect(Rect2i(c.x, c.y, 1, 1), C["black"])

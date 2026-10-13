extends Node2D
## Oberfläche des Befehlsmenü-Adventures (wie im Katalogeintrag pc98-adventure), gezeichnet in Palettenindizes
## (Rotkanal = Index / 15): Bildfenster mit Zierrahmen, rechts Ortsfenster, Befehlsmenü und Objektliste, unten
## das Textfenster, in dem die Ortszeile Zeichen für Zeichen erscheint. Keine Figur, kein Namensfeld: der Text ist
## Erzähltext. Bitmapschrift aus DotGothic16 (16-px-Punktraster, Latein halbbreit 8 px), als Atlas vorgerastert.

const SCENE := Rect2i(12, 12, 416, 256)
const LOC_RECT := Rect2i(440, 12, 188, 48)
const CMD_RECT := Rect2i(440, 72, 188, 120)
const OBJ_RECT := Rect2i(440, 204, 188, 64)
const TEXT_RECT := Rect2i(12, 280, 616, 68)
const FS := 16                       # Schriftgröße = Punktraster der Schrift
const COMMANDS := ["Ansehen", "Nehmen", "Sprechen", "Gehen"]

# Zeitplan in Bildern (30 Bilder/s)
const TEXT_FROM := 15                # Bild, ab dem die Ortszeile läuft
const CHAR_FRAMES := 1               # ein Zeichen je Bild (30 Zeichen/s)
const PAUSE_AFTER := {".": 9, ",": 5}
const CELL_TOP := 4                  # Leerzeilen über der Versalhöhe in der Atlaszelle

var location := ""
var time_of_day := ""
var lines: Array = []
var objects: Array = []
var C := {}                          # Register der Oberfläche (aus meta.json, im Build-Skript bestimmt)
var atlas: Texture2D
var glyphs := {}
var f := 0
var char_frames: Array[int] = []
var text_end := 0
var backdrop: ImageTexture


func setup(meta: Dictionary, font_dir: String) -> void:
	atlas = load(font_dir + "/dotgothic16_atlas.png")
	var fm: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(font_dir + "/dotgothic16_atlas.json"))
	glyphs = fm["glyphs"]
	location = String(meta["name"])
	time_of_day = String(meta["time"])
	lines = meta["text"]
	objects = meta["objects"]
	for k in meta["ui"]:
		C[k] = int(meta["ui"][k])
	backdrop = _make_backdrop()
	var fr := TEXT_FROM
	for line in lines:
		for ch in String(line):
			char_frames.append(fr)
			fr += CHAR_FRAMES
			if PAUSE_AFTER.has(ch):
				fr += int(PAUSE_AFTER[ch])
	text_end = fr


static func ic(i: int) -> Color:
	return Color(i / 15.0, 0.0, 0.0, 1.0)


func set_frame(fr: int) -> void:
	f = fr
	queue_redraw()


func _text(x: int, top: int, s: String, col: int) -> void:
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


func _corners(o: Rect2i) -> void:
	## Eckbeschläge: 5x5-Raute in Pfirsich mit schwarzem Kern
	for p in [o.position, Vector2i(o.end.x - 1, o.position.y), Vector2i(o.position.x, o.end.y - 1), o.end - Vector2i.ONE]:
		var c: Vector2i = p
		_rect(Rect2i(c.x - 2, c.y, 5, 1), C["peach"])
		_rect(Rect2i(c.x, c.y - 2, 1, 5), C["peach"])
		_rect(Rect2i(c.x - 1, c.y - 1, 3, 3), C["peach"])
		_rect(Rect2i(c.x, c.y, 1, 1), C["black"])


func _frame(inner: Rect2i) -> void:
	## Zierrahmen: schwarze Fuge, helle Doppellinie mit dunklem Zwischenraum, Eckbeschläge
	var o := inner.grow(4)
	_rect(o, C["black"])
	_rect(o.grow(-1), C["steel"])
	_rect(o.grow(-2), C["indigo"])
	_rect(o.grow(-3), C["steel"])
	_rect(inner, C["black"])
	_corners(o)


func _frame_ring(inner: Rect2i) -> void:
	## Rahmen ohne Füllung (Bildfenster)
	var o := inner.grow(4)
	for ring in [[0, C["black"]], [1, C["steel"]], [2, C["indigo"]], [3, C["steel"]]]:
		var rr := o.grow(-int(ring[0]))
		var col: int = ring[1]
		_rect(Rect2i(rr.position.x, rr.position.y, rr.size.x, 1), col)
		_rect(Rect2i(rr.position.x, rr.end.y - 1, rr.size.x, 1), col)
		_rect(Rect2i(rr.position.x, rr.position.y, 1, rr.size.y), col)
		_rect(Rect2i(rr.end.x - 1, rr.position.y, 1, rr.size.y), col)
	_corners(o)


func _cursor(x: int, top: int, col: int) -> void:
	## Dreieck-Cursor (7 px hoch) vor einem Menüeintrag
	for r in 7:
		var w := 4 - absi(r - 3)
		_rect(Rect2i(x, top + 5 + r, w, 1), col)


func _draw() -> void:
	draw_texture(backdrop, Vector2.ZERO)
	_frame_ring(SCENE)

	# Ortsfenster: Ortsname und Tageszeit
	_frame(LOC_RECT)
	_text(LOC_RECT.position.x + (LOC_RECT.size.x - _width(location)) / 2, LOC_RECT.position.y + 6, location, C["peach"])
	_text(LOC_RECT.position.x + (LOC_RECT.size.x - _width(time_of_day)) / 2, LOC_RECT.position.y + 26, time_of_day, C["steel"])

	# Befehlsmenü: Cursor steht auf „Ansehen“ und blinkt, sobald der Text fertig ist
	_frame(CMD_RECT)
	var row0 := CMD_RECT.position.y + 8
	for i in COMMANDS.size():
		_text(CMD_RECT.position.x + 30, row0 + i * 28, COMMANDS[i], C["cream"])
	if f < text_end or ((f - text_end) / 15) % 2 == 0:
		_cursor(CMD_RECT.position.x + 12, row0, C["peach"])

	# Objektliste des Ortes: grau, bis ein Befehl gewählt ist (hier nie)
	_frame(OBJ_RECT)
	for i in objects.size():
		_text(OBJ_RECT.position.x + 30, OBJ_RECT.position.y + 2 + i * 20, String(objects[i]), C["indigo"])

	# Textfenster: Ortszeile Zeichen für Zeichen, danach blinkendes Weiter-Zeichen
	_frame(TEXT_RECT)
	var tx := TEXT_RECT.position.x + 12
	var ty := TEXT_RECT.position.y + 12
	var shown := 0
	for fr in char_frames:
		if fr <= f:
			shown += 1
	var k := 0
	var last_end := Vector2i(tx, ty)
	for li in lines.size():
		var line := String(lines[li])
		var n := clampi(shown - k, 0, line.length())
		if n > 0:
			var s := line.substr(0, n)
			_text(tx, ty + li * 24, s, C["cream"])
			last_end = Vector2i(tx + _width(s), ty + li * 24)
		k += line.length()
	if f >= text_end + 3 and ((f - text_end - 3) / 8) % 2 == 0:
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

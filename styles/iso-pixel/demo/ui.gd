extends Control
# Seitenleiste wie in isometrischen Strategie- und Rollenspielen: Porträt, Ort mit Minikarte, Text, Auswahl,
# Parserzeile. Gezeichnet in _draw auf dem 426×240-Raster, Pixelschriften ohne Glättung.

var main: Node
var t := 0.0
var body: FontVariation
var title: FontVariation
var portrait: Texture2D
var portrait_blink: Texture2D
var pbg: ImageTexture
var minimap: ImageTexture

const X0 := 302
const PW := 124
const TEXT := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const LOCATION := ["Hafen von", "Lornholm"]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const C_OUT := Color("120f1c")
const C_BG := Color("1a1630")
const C_BG2 := Color("221c3d")
const C_LINE := Color("3b3262")
const C_HI := Color("6f6198")
const C_GOLD := Color("e9c372")
const C_BRASS := Color("a8823c")
const C_TEXT := Color("e8dfcb")
const C_DIM := Color("9a8fb2")
const C_SEL := Color("f4dc8a")
const C_SELBG := Color("2e2756")
const C_RED := Color("de5d48")


func _ready() -> void:
	size = Vector2(426, 240)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	body = _font("res://fonts/Micro5-Regular.ttf")
	title = _font("res://fonts/Jersey10-Regular.ttf")
	portrait = load("res://art/portrait.png")
	portrait_blink = load("res://art/portrait_blink.png")
	pbg = _portrait_bg()
	minimap = _minimap()


func _font(path: String) -> FontVariation:
	var f: FontFile = load(path)
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.oversampling = 1.0          # sonst rastert Godot bei ×3-Fenster dreifach und tastet ohne Glättung ab
	var v := FontVariation.new()
	v.base_font = f
	var ts := TextServerManager.get_primary_interface()
	v.opentype_features = {ts.name_to_tag("liga"): 0, ts.name_to_tag("clig"): 0, ts.name_to_tag("kern"): 0}
	return v


const BAYER := [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]


func _portrait_bg() -> ImageTexture:
	var img := Image.create(64, 64, false, Image.FORMAT_RGBA8)
	var a := Color("1d1838")
	var b := Color("4b2d5a")
	var c := Color("b45a62")
	for y in 64:
		for x in 64:
			var th: float = (BAYER[(y % 4) * 4 + x % 4] + 0.5) / 16.0
			var col := a
			if y < 44:
				col = b if float(y) / 44.0 > th + 0.15 else a
			else:
				col = c if float(y - 44) / 20.0 > th * 1.4 else b
			img.set_pixel(x, y, col)
	return ImageTexture.create_from_image(img)


func _minimap() -> ImageTexture:
	# 4×2-Rauten je Zelle, Farben nach Gelände; die Karte selbst ist ein kleines Iso-Bild
	var cols := {"Q": Color("7d7684"), "G": Color("4a6a3f"), "H": Color("5b7f48"), "R": Color("55744a"),
			"r": Color("625b62"), "S": Color("c8ab88"), "W": Color("264d68"), "J": Color("835839")}
	var img := Image.create(40, 22, false, Image.FORMAT_RGBA8)
	var cells: Dictionary = main.map.cells
	for key in cells.keys():
		var xy: PackedStringArray = key.split(",")
		var cx := int(xy[0])
		var cy := int(xy[1])
		var code: String = cells[key][0]
		var ox := 2 * (cx - cy) + 16
		var oy := cx + cy + 1
		for p in [Vector2i(1, 0), Vector2i(2, 0), Vector2i(0, 1), Vector2i(1, 1), Vector2i(2, 1), Vector2i(3, 1)]:
			var px: int = ox + p.x
			var py: int = oy + p.y
			if px >= 0 and px < 40 and py >= 0 and py < 22:
				var c: Color = cols.get(code, Color.BLACK)
				if code in ["G", "H", "R"] and int(cells[key][1]) >= 1:
					c = c.lightened(0.12)
				img.set_pixel(px, py, c)
	return ImageTexture.create_from_image(img)


func _rect(x: float, y: float, w: float, h: float, c: Color) -> void:
	draw_rect(Rect2(x, y, w, h), c)


func _frame(x: int, y: int, w: int, h: int, fill: Color) -> void:
	_rect(x, y, w, h, C_OUT)
	_rect(x + 1, y + 1, w - 2, h - 2, C_LINE)
	_rect(x + 2, y + 2, w - 4, h - 4, fill)
	_rect(x + 1, y + 1, w - 2, 1, C_HI)
	_rect(x + 1, y + 1, 1, h - 2, C_HI)


const FS := 10                     # Micro 5 auf seinem Raster (1 Schriftpixel = 1 px)
const FT := 13                     # Jersey 10 für den Ortsnamen


func _text(x: float, y: float, s: String, c: Color, f: Font = null, fs: int = FS) -> void:
	# Zeichen einzeln setzen: Micro 5 verschmilzt "fl" beim Formen der ganzen Zeile zu einem Zeichen, das wie
	# "A" aussieht (Abschalten von liga/clig/kern und ein Nullbreiten-Nichtverbinder halfen nicht).
	if f == null:
		f = body
	var px := x
	for ch in s:
		draw_char(f, Vector2(px, y), ch, fs, c)
		px += f.get_char_size(ch.unicode_at(0), fs).x


func _width(s: String, f: Font = null, fs: int = FS) -> float:
	if f == null:
		f = body
	var w := 0.0
	for ch in s:
		w += f.get_char_size(ch.unicode_at(0), fs).x
	return w


func _wrap(s: String, width: float, f: Font, fs: int) -> Array:
	var lines := []
	var cur := ""
	for w in s.split(" "):
		var test := w if cur == "" else cur + " " + w
		if _width(test, f, fs) > width and cur != "":
			lines.append(cur)
			cur = w
		else:
			cur = test
	if cur != "":
		lines.append(cur)
	return lines


func _draw() -> void:
	var n := int(floor(t * 30.0 + 0.5))
	# Leiste
	_rect(X0, 0, PW, 240, C_OUT)
	_rect(X0 + 1, 0, PW - 1, 240, C_BG)
	_rect(X0 + 2, 0, 1, 240, C_LINE)
	for cy in [3, 236]:
		for cx in [X0 + 4, X0 + PW - 6]:
			_rect(cx, cy, 2, 2, C_BRASS)
			_rect(cx, cy, 1, 1, C_GOLD)
	# Porträt
	_frame(X0 + 5, 5, 68, 68, C_BG2)
	draw_texture(pbg, Vector2(X0 + 7, 7))
	var blink := (n % 96) >= 90 or (n % 157) >= 153
	draw_texture(portrait_blink if blink else portrait, Vector2(X0 + 7, 7))
	# Ort und Minikarte
	_text(X0 + 77, 15, LOCATION[0], C_DIM)
	_text(X0 + 77, 27, LOCATION[1], C_GOLD, title, FT)
	_rect(X0 + 77, 29, 42, 1, C_LINE)
	_frame(X0 + 77, 36, 44, 26, Color("15122a"))
	draw_texture(minimap, Vector2(X0 + 79, 38))
	if main.badger_root:
		var bp: Vector2 = main.badger_root.position
		var cell := _screen_to_cell(bp)
		var mx := X0 + 79 + 2 * (cell.x - cell.y) + 18
		var my := 38 + (cell.x + cell.y) + 1
		if (n / 8) % 2 == 0:
			_rect(round(mx), round(my), 2, 1, C_RED)
	# Text (Schreibmaschine), größere Schrift
	_rect(X0 + 6, 79, PW - 12, 1, C_LINE)
	var shown := int(clamp((t - 0.25) * 36.0, 0.0, float(TEXT.length())))
	var lines := _wrap(TEXT, PW - 14, title, FT)
	var left := shown
	var y := 93
	for ln in lines:
		var part: String = ln.substr(0, max(0, left))
		_text(X0 + 7, y, part, C_TEXT, title, FT)
		left -= ln.length() + 1
		y += 12
	# Auswahl
	var sep_y := 138
	_rect(X0 + 6, sep_y, PW - 12, 1, C_LINE)
	var sel := 0 if t < 3.6 else 1
	for i in CHOICES.size():
		if t < 2.0 + i * 0.15:
			continue
		var cy := sep_y + 6 + i * 14
		if i == sel:
			_rect(X0 + 5, cy - 1, PW - 10, 12, C_SELBG)
			var ax := X0 + 7 + (1 if (n / 10) % 2 == 0 else 0)
			for k in 5:
				_rect(ax, cy + 2 + k, 1 + min(k, 4 - k), 1, C_SEL)
		_text(X0 + 13, cy + 8, CHOICES[i], C_SEL if i == sel else C_DIM)
	# Tasche: vier Fächer
	_rect(X0 + 6, 186, PW - 12, 1, C_LINE)
	for i in 4:
		var sx := X0 + 7 + i * 28
		_frame(sx, 190, 24, 18, Color("15122a"))
		_item(i, sx + 2, 190)
	# Parserzeile
	_frame(X0 + 5, 214, PW - 10, 18, Color("120f24"))
	var typed := int(clamp((t - 3.2) * 12.0, 0.0, float(PARSER.length())))
	var ptxt := PARSER.substr(0, typed) if t >= 3.2 else ">"
	_text(X0 + 9, 226, ptxt, C_GOLD)
	var cw := _width(ptxt)
	if (n / 12) % 2 == 0:
		_rect(X0 + 10 + cw, 218, 4, 9, C_TEXT)


func _item(i: int, x: int, y: int) -> void:
	# kleine Pixel-Symbole aus Rechtecken: Brief, Schlüssel, Münzen, leer
	if i == 0:
		_rect(x + 3, y + 3, 14, 10, C_OUT)
		_rect(x + 4, y + 4, 12, 8, Color("dccdb0"))
		for k in 6:
			_rect(x + 4 + k, y + 4 + k / 2, 1, 1, Color("8b7e86"))
			_rect(x + 15 - k, y + 4 + k / 2, 1, 1, Color("8b7e86"))
		_rect(x + 9, y + 7, 2, 2, Color("bb3339"))
	elif i == 1:
		var g := Color("d8ad48")
		var gd := Color("8a6526")
		_rect(x + 2, y + 5, 6, 6, gd)
		_rect(x + 3, y + 6, 4, 4, g)
		_rect(x + 4, y + 7, 2, 2, Color("15122a"))
		_rect(x + 8, y + 7, 9, 2, g)
		_rect(x + 8, y + 9, 9, 1, gd)
		_rect(x + 13, y + 9, 2, 3, g)
		_rect(x + 16, y + 9, 1, 2, g)
	elif i == 2:
		for c in [Vector2i(4, 8), Vector2i(9, 8), Vector2i(7, 4)]:
			_rect(x + c.x, y + c.y, 6, 5, Color("8a6526"))
			_rect(x + c.x + 1, y + c.y, 4, 4, Color("e9c372"))
			_rect(x + c.x + 1, y + c.y, 2, 1, Color("fff0b0"))


func _screen_to_cell(p: Vector2) -> Vector2:
	var d: Vector2 = p - main.ORIGIN + Vector2(0, 8)
	var a := d.x / 16.0
	var b := d.y / 8.0
	return Vector2((a + b) * 0.5, (b - a) * 0.5)

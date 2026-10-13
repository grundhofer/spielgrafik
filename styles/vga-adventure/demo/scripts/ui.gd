extends Node2D
## Oberfläche im Stil der Point-and-Click-Adventures: Satzzeile, 3x3-Verben, Inventar mit Symbolen,
## Sprechtext über der Figur, Fadenkreuz-Cursor. Alles in Palettenfarben, Pixelschrift ohne Kantenglättung.

const PANEL_Y := 152
const VERBS := [["Gib", "Nimm", "Benutze"], ["Öffne", "Schau an", "Drücke"], ["Schließe", "Rede mit", "Ziehe"]]
# Spalten an der gerenderten Tinte gemessen (scripts/measure_ui.py): Pixel Operator 8 setzt ein Wortleerzeichen
# 6 px breit, deshalb müssen Spalten mindestens 8 px auseinander liegen, sonst liest sich "Schau an Rede mit" als
# eine Zeile. Erste Fassung 3/56/112 mit 35-px-Inventarfeldern ließ nur 5 px. Jetzt Inventarfelder 32 px
# (Symbol 26 px, 2 px Luft je Seite) und Pfeile 5x3 statt 7x4: Verben 4-49 | 60-110 | 121-170 (10 px Abstand),
# Pfeil 178-182 (7 px nach "Schließe"), Inventar 188-315 (4 px Rand wie links).
const COL_X := [3, 59, 120]
const ROW_Y := [163, 175, 187]
const ARROW_X := 180
const SLOT_X := 188
const SLOT_W := 32
const SLOT_H := 19
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const LOCATION := "Hafen von Lornholm"
const LOCATION_UNTIL := 2.6       # Ortsname wird beim Betreten kurz eingeblendet
# In Pixel Operator 8 hat das große Ö nur x-Höhe (sieht aus wie "ö"). Deshalb wird "O" gezeichnet und die
# beiden Umlautpunkte setzt _umlaut_text mit einer Leerzeile Abstand über die Versalhöhe.
const CAP_TOP := 0                # erste Zeile der Großbuchstaben unter der Textoberkante (gemessen)

@onready var main: Node = get_parent()
var font_r: FontFile
var font_b: FontFile
var items: Texture2D = preload("res://art/items.png")


func _ready() -> void:
	font_r = _pixel_font("res://fonts/PixelOperator8.ttf")
	font_b = _pixel_font("res://fonts/PixelOperatorHB8.ttf")


func _pixel_font(path: String) -> FontFile:
	var f: FontFile = load(path)
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.generate_mipmaps = false
	f.multichannel_signed_distance_field = false
	return f


func _c(name: String) -> Color:
	return main.color(int(main.meta["ui_colors"][name]))


func _text(f: Font, x: int, top: int, s: String, col: Color) -> void:
	draw_string(f, Vector2(x, top + roundi(f.get_ascent(8))), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, col)


func _width(f: Font, s: String) -> int:
	return roundi(f.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x)


func _outlined(f: Font, x: int, top: int, s: String, col: Color, outline: Color) -> void:
	for o in [Vector2i(-1, 0), Vector2i(1, 0), Vector2i(0, -1), Vector2i(0, 1),
			Vector2i(-1, -1), Vector2i(1, -1), Vector2i(-1, 1), Vector2i(1, 1)]:
		_text(f, x + o.x, top + o.y, s, outline)
	_text(f, x, top, s, col)


func _umlaut_text(f: Font, x: int, top: int, s: String, col: Color) -> void:
	## Text mit großem Ö/Ä/Ü am Wortanfang: Grundbuchstabe in Versalhöhe + zwei 1-px-Punkte darüber
	var map := {"Ö": "O", "Ä": "A", "Ü": "U"}
	var first := s.substr(0, 1)
	if not map.has(first):
		_text(f, x, top, s, col)
		return
	var base: String = map[first]
	_text(f, x, top, base + s.substr(1), col)
	var w := _width(f, base)
	var y := top + CAP_TOP - 2
	draw_rect(Rect2(x + 2, y, 1, 1), col)      # O ist 5 px breit (x+1..x+5): Punkte über Spalte 2 und 4
	draw_rect(Rect2(x + w - 3, y, 1, 1), col)


func _draw() -> void:
	var black := _c("schwarz")
	# Ortsname beim Betreten der Szene
	if main.t < LOCATION_UNTIL:
		var lw := _width(font_b, LOCATION)
		_outlined(font_b, 160 - lw / 2, 6, LOCATION, _c("weiss"), black)
	# Sprechtext über dem Kopf, zentriert, am Bildrand eingerückt
	if main.talking:
		var head_top := 147 - 40
		for k in LINES.size():
			var s: String = LINES[k]
			var w := _width(font_b, s)
			var x := clampi(roundi(main.badger_x - w / 2.0), 3, 317 - w)
			_outlined(font_b, x, head_top - 22 + k * 10, s, _c("sprechtext"), black)
	# Leiste
	draw_rect(Rect2(0, PANEL_Y, 320, 48), black)
	var sc := _c("satz_klick") if main.sentence_flash else _c("satz")
	var sw := _width(font_r, main.sentence)
	_text(font_r, 160 - sw / 2, PANEL_Y + 1, main.sentence, sc)
	for c in 3:
		for r in 3:
			var v: String = VERBS[c][r]
			_umlaut_text(font_r, COL_X[c], ROW_Y[r], v, _c("verb_hell") if v == main.verb_hi else _c("verb"))
	# Pfeile
	_arrow(ARROW_X, 166, true)
	_arrow(ARROW_X, 189, false)
	# Inventar: 4x2 Felder, obere Reihe mit Seekarte, Schlüssel, Brief, Kompass
	for r in 2:
		for c in 4:
			var x := SLOT_X + c * SLOT_W
			var y := 161 + r * SLOT_H
			draw_rect(Rect2(x, y, SLOT_W - 1, SLOT_H - 1), _c("feld"))
			draw_rect(Rect2(x, y, SLOT_W - 1, SLOT_H - 1), _c("rahmen"), false, 1.0)
			if r == 0:
				draw_texture_rect_region(items, Rect2(x + 3, y + 0, 26, 17), Rect2(c * 26, 0, 26, 17))
	# Cursor: Fadenkreuz mit Lücke, Farbe wechselt wie bei den Vorbildern
	var cp: Vector2 = main.cursor
	var cc := _c("weiss") if int(floor(main.t * 7.5)) % 2 == 0 else _c("grau")   # 7,5 Hz: je 4 Bilder bei 30 fps
	for d in range(2, 6):
		for v in [Vector2(d, 0), Vector2(-d, 0), Vector2(0, d), Vector2(0, -d)]:
			draw_rect(Rect2(cp.x + v.x, cp.y + v.y, 1, 1), cc)


func _arrow(x: int, y: int, up: bool) -> void:
	var col := _c("rahmen")
	for i in 3:
		var yy := y + (i if up else 2 - i)
		draw_rect(Rect2(x - i, yy, 2 * i + 1, 1), col)

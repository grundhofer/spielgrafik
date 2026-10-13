extends Control
## Oberfläche im Voxel-Stil: Tafeln wie Blöcke (Rahmen mit heller Ober- und Kante links, dunkler Kante
## unten und rechts, abgeschnittene Ecken in 4-px-Stufen), Pixelschrift Pixelify Sans ohne Kantenglättung.
## Rahmen und Blöcke liegen auf einem 4-px-Raster. Die Schrift wird in ihrer Rastergröße gesetzt: Pixelify
## Sans (Regular) hat Schriftpixel von etwa 0,09 em mit 0,10 em breiten Strichen; bei 11 px ergibt das genau
## 1 px je Schriftpixel. Diese 11-px-Schrift wird ganzzahlig vergrößert (draw_set_transform, Filter Nearest):
## Ortsschild 4-fach (4 px je Schriftpixel wie die Rahmen), Dialog 2-fach; Positionen auf ganze Schriftpixel
## gerundet (geprüft mit scripts/check_font.py). Direkt in 20 oder 30 px gesetzt mischten sich 2- und 3-px-
## bzw. 3- und 4-px-Striche („Z“ las sich wie „2“), und keine direkte Größe ergab in beiden Richtungen gleiche
## Striche (22 px: 3 px breit, 2 px hoch). Die fette Fassung (wght 700) hat kein gleichmäßiges Raster.
## Ortsschild als Holzblock oben links, Dialog unten rechts mit Text (Zeichen für Zeichen), drei
## Auswahlblöcken (der gewählte golden) und Parserzeile mit Blockcursor. Der Dialog klappt erst nach dem
## Lauf durch die Totale auf (BOX_T), sonst verdeckt er den Dachs.
## main.gd ruft set_time(t) in jedem Bild auf (aufsummierte Zeit, deterministisch).

const FONT_PATH := "res://fonts/PixelifySans-wght.ttf"
const U := 4                      # Rastermaß der Oberfläche in Pixeln
const FONT_PX := 11               # Schriftgröße mit genau 1 px je Schriftpixel
const TAG_SCALE := 4              # Ortsschild: 4 px je Schriftpixel (wie das Raster der Rahmen)
const TEXT_SCALE := 2             # Dialog: 2 px je Schriftpixel

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const BOX := Rect2(500, 532, 752, 164)
const TAG := Rect2(28, 24, 0, 56)          # Breite aus der Schrift
# Der Dialog klappt erst nach der Totale auf: In der Totale läuft der Dachs bis 2,9 s durch das Rechteck des
# Kastens (mit --mask gemessen, bis 22 % der Figur verdeckt); ab 3,0 s steht er links davon.
const BOX_T := 3.0                          # Dialog klappt auf
const TYPE_T := 3.3                         # Text beginnt
const CHARS_PER_S := 45.0
const CHOICE_T := 4.3                       # Auswahl erscheint
const CHOICE_W := 324                       # Breite der Auswahlblöcke (längste Auswahl 22 Zeichen)

# Farben: Stein-Block (Dialog), Holz-Block (Ortsschild), Gold (gewählte Auswahl)
const STONE := [Color("2a3044"), Color("475273"), Color("171b27"), Color("0d0f16")]   # Fläche, Licht, Schatten, Rand
const WOOD := [Color("7a5233"), Color("a0703f"), Color("4f341f"), Color("1e140c")]
const GOLD := [Color("e8b04c"), Color("ffd98a"), Color("a8722a"), Color("2a1a08")]
const SLOT := [Color("3a4260"), Color("56618a"), Color("232838"), Color("0d0f16")]
const TEXT := Color("f4ead2")
const TEXT_DIM := Color("b9bfd6")
const SHADOW := Color("0b0d14")

var t := 0.0
var font: FontVariation


func _ready() -> void:
	var ff := load(FONT_PATH) as FontFile
	ff.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	ff.hinting = TextServer.HINTING_NONE
	ff.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	ff.generate_mipmaps = false
	# Ligaturen aus: Pixelify Sans setzt "fl" sonst als eigenes Zeichen, das wie "A" aussieht ("Aackert")
	var no_liga := {"liga": 0, "clig": 0}
	font = FontVariation.new()
	font.base_font = ff
	font.variation_opentype = {"wght": 400}
	font.opentype_features = no_liga
	# vergrößerte 11-px-Schrift ohne Glättung
	texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST


func set_time(time_s: float) -> void:
	t = time_s
	queue_redraw()


func _draw() -> void:
	_draw_tag()
	_draw_dialog()


func _snap(v: float) -> float:
	return floorf(v / U) * U


## Block mit 4-px-Rand: Außenrand dunkel, innen oben/links Licht, unten/rechts Schatten, Ecken gestuft.
func _block(r: Rect2, c: Array, alpha := 1.0) -> void:
	var fill: Color = c[0]; var hi: Color = c[1]; var lo: Color = c[2]; var edge: Color = c[3]
	fill.a *= alpha
	var x := r.position.x; var y := r.position.y; var w := r.size.x; var h := r.size.y
	# Außenrand ohne Eckpixel
	draw_rect(Rect2(x + U, y, w - 2 * U, h), edge)
	draw_rect(Rect2(x, y + U, w, h - 2 * U), edge)
	# Fläche
	draw_rect(Rect2(x + U, y + U, w - 2 * U, h - 2 * U), fill)
	# Licht oben und links, Schatten unten und rechts (je ein Rastermaß)
	draw_rect(Rect2(x + U, y + U, w - 2 * U, U), hi)
	draw_rect(Rect2(x + U, y + 2 * U, U, h - 4 * U), hi)
	draw_rect(Rect2(x + U, y + h - 2 * U, w - 2 * U, U), lo)
	draw_rect(Rect2(x + w - 2 * U, y + 2 * U, U, h - 4 * U), lo)


## Text als 11-px-Schrift, k-fach vergrößert, auf ganzen Schriftpixeln; Schatten ein Schriftpixel versetzt.
func _text(pos: Vector2, s: String, k: int, col: Color, shadow := true) -> void:
	var p := Vector2(roundf(pos.x / k) * k, roundf(pos.y / k) * k)
	if shadow:
		draw_set_transform(p + Vector2(k, k), 0.0, Vector2(k, k))
		draw_string(font, Vector2.ZERO, s, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_PX, SHADOW)
	draw_set_transform(p, 0.0, Vector2(k, k))
	draw_string(font, Vector2.ZERO, s, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_PX, col)
	draw_set_transform(Vector2.ZERO)


func _text_width(s: String, k: int) -> float:
	return font.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_PX).x * k


func _draw_tag() -> void:
	var w := _text_width(LOCATION, TAG_SCALE)
	var r := Rect2(TAG.position, Vector2(_snap(w + 13 * U) + U * 2, TAG.size.y))
	# Schatten des Blocks (harte Kante, ein Rastermaß versetzt)
	draw_rect(Rect2(r.position + Vector2(U * 2, U * 2), r.size), Color(0, 0, 0, 0.35))
	_block(r, WOOD)
	# zwei Nägel als Voxel
	for nx in [r.position.x + 3 * U, r.end.x - 4 * U]:
		draw_rect(Rect2(nx, r.position.y + r.size.y / 2 - U / 2, U, U), Color("2b1d12"))
	_text(Vector2(r.position.x + 6 * U, r.position.y + 42), LOCATION, TAG_SCALE, TEXT)


func _draw_dialog() -> void:
	if t < BOX_T:
		return
	# Aufklappen in Rasterstufen: Höhe wächst von unten in 4-px-Schritten
	var k := clampf((t - BOX_T) / 0.25, 0.0, 1.0)
	k = 1.0 - pow(1.0 - k, 3.0)
	var h := _snap(BOX.size.y * k)
	if h < 3 * U:
		return
	var r := Rect2(BOX.position.x, BOX.end.y - h, BOX.size.x, h)
	draw_rect(Rect2(r.position + Vector2(U * 2, U * 2), r.size), Color(0, 0, 0, 0.35))
	_block(r, STONE, 0.94)
	if k < 1.0:
		return
	var x0 := BOX.position.x + 6 * U
	var y0 := BOX.position.y + 13 * U
	# Text Zeichen für Zeichen (ganze Zeichen, kein Ausblenden)
	var n := int(maxf(t - TYPE_T, 0.0) * CHARS_PER_S)
	var y := y0
	for line in LINES:
		var shown: String = line.substr(0, clampi(n, 0, line.length()))
		_text(Vector2(x0, y), shown, TEXT_SCALE, TEXT)
		n -= line.length()
		y += 8 * U
	# Parserzeile mit blinkendem Blockcursor (Takt 0,5 s)
	if t >= CHOICE_T:
		var py := BOX.end.y - 7 * U
		_text(Vector2(x0, py), PARSER, TEXT_SCALE, Color("9fe0a8"))
		var cw := _text_width(PARSER, TEXT_SCALE)
		if fmod(t - CHOICE_T, 1.0) < 0.5:
			draw_rect(Rect2(_snap(x0 + cw + 2 * U), py - 4 * U, 2 * U, 4 * U), Color("9fe0a8"))
	# Auswahl: drei Blöcke rechts, der erste gewählt (gold, mit Pfeil aus Voxeln)
	if t >= CHOICE_T:
		var bx := BOX.end.x - 5 * U - CHOICE_W
		var by := BOX.position.y + 5 * U
		for i in CHOICES.size():
			var appear := clampf((t - CHOICE_T - 0.12 * i) / 0.12, 0.0, 1.0)
			if appear <= 0.0:
				continue
			var br := Rect2(bx + _snap((1.0 - appear) * 40.0), by + i * 12 * U, CHOICE_W, 10 * U)
			var sel := i == 0
			_block(br, GOLD if sel else SLOT)
			var col: Color = Color("2a1a08") if sel else TEXT
			_text(Vector2(br.position.x + 8 * U, br.position.y + 26), CHOICES[i], TEXT_SCALE, col, not sel)
			if sel:
				# Pfeil aus drei Voxelstufen, hüpft im 1/3-s-Takt um ein Rastermaß
				var ax: float = br.position.x + 3 * U + (U if fmod(t, 0.66) < 0.33 else 0.0)
				var ay: float = br.position.y + 3 * U
				draw_rect(Rect2(ax, ay, U / 2.0, 4 * U), Color("2a1a08"))
				draw_rect(Rect2(ax, ay, U, 4 * U), Color("2a1a08"))
				draw_rect(Rect2(ax + U, ay + U, U, 2 * U), Color("2a1a08"))

extends Control
## Oberfläche im Stil der Rollenspiel-Fenster der Zeit, gezeichnet in 320×240:
## Fenster mit Verlauf aus vier Eckfarben (ein Gouraud-Viereck, das Dithering macht shaders/dither.gdshader),
## heller Doppelrahmen mit abgeschnittenen Ecken, weiße, geglättete Schrift (Nunito) mit Schatten, Text erscheint
## Zeichen für Zeichen, danach die Auswahl: alle Optionen weiß (grau hieße "nicht wählbar"), die Auswahl zeigt
## nur der hüpfende Handzeiger. Ortsname oben links in eigenem Fenster.

const FONT_PATH := "res://fonts/Nunito.ttf"
const FONT_WEIGHT := 750
const FONT_SIZE := 12
const LINE_H := 11
const SPACE_EXTRA := 2                      # Wortabstand +2 px: bei 12 px und ganzen Pixelpositionen lasen sich
                                            # "Mit dem" und "auf dich" sonst wie ein Wort
const CHOICE_INDENT := 19                   # Platz für den Handzeiger (15 px breit)

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]

const BOX := Rect2i(10, 168, 300, 68)      # Dialogfenster (26,6 % des Bildes)
const LOC_POS := Vector2i(8, 8)             # Ortsfenster oben links (ca. 3 %)
const LOC_H := 18

const TEXT_START := 0.1                     # s
const CHARS_PER_S := 30.0                   # bei 30 fps genau ein Zeichen je Bild
const CHOICES_T := 2.583                    # 77,5/30 s: Auswahl ab Bild 77 (2,6 s), zwischen zwei Bildern gelegt
const FPS := 30.0                           # Bildrate der Aufnahme: Zeiten werden in ganze Bilder umgerechnet
const HAND_HOLD := 9                        # Handzeiger: 9 Bilder oben, 9 Bilder unten (0,3 s, geht in 30 fps auf)
const LOC_IN := 0.0

# Fensterfarben (sRGB): oben links hell, unten rechts dunkel
const C_TL := Color(0.16, 0.25, 0.62)
const C_TR := Color(0.09, 0.14, 0.46)
const C_BL := Color(0.07, 0.11, 0.38)
const C_BR := Color(0.02, 0.04, 0.20)
const C_RIM := Color(0.86, 0.87, 0.92)
const C_RIM2 := Color(0.45, 0.47, 0.58)
const C_TEXT := Color(0.96, 0.96, 0.96)
const C_SHADOW := Color(0.02, 0.02, 0.08)
const C_HAND_SHADE := Color(0.70, 0.72, 0.80)

## Handzeiger 15×9 (zeigt nach rechts): # = dunkler Rand, W = weiß, g = Schattierung
const HAND := [
	"...#######.....",
	"..#WWWWWWW#####",
	".#WWWWWWWWWWWW#",
	"#WWWWWWW######.",
	"#WWWWWWWW#.....",
	"#gWWWWWW#......",
	"#ggWWWWWW#.....",
	".#gggggg#......",
	"..######.......",
]

var t := 0.0
var font: FontVariation


func _ready() -> void:
	# Geglättete Schrift wie in den Rollenspielen der Zeit (Glyphen als 4-Bit-Graustufen-Textur):
	# Graustufen-Glättung an, aber ganze Pixelpositionen; gezeichnet in 320×240.
	var base := load(FONT_PATH) as FontFile
	base.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
	base.hinting = TextServer.HINTING_LIGHT
	base.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	base.generate_mipmaps = false
	font = FontVariation.new()
	font.base_font = base
	font.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): FONT_WEIGHT}
	font.spacing_space = SPACE_EXTRA


func _process(delta: float) -> void:
	t += delta
	queue_redraw()


func _draw() -> void:
	# Ortsfenster
	if t >= LOC_IN:
		var w := int(font.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE).x) + 14
		_window(Rect2i(LOC_POS, Vector2i(w, LOC_H)))
		_text(Vector2(LOC_POS.x + 7, LOC_POS.y + 13), LOCATION, C_TEXT)

	# Dialogfenster mit Schreibmaschinen-Text (Positionen = Grundlinien)
	_window(BOX)
	# Bildzähler statt floor(t · Rate): Die aufsummierte Zeit liegt um Rundungsfehler neben k/30
	var shown := maxi(0, int(roundf((t - TEXT_START) * CHARS_PER_S)))
	var x0 := BOX.position.x + 8
	var y := BOX.position.y + 14
	for line: String in LINES:
		if shown > 0:
			_text(Vector2(x0, y), line.substr(0, shown), C_TEXT)
		shown -= line.length()
		y += LINE_H
	if t >= CHOICES_T:
		y += 3
		var sel := 0
		for i in CHOICES.size():
			_text(Vector2(x0 + CHOICE_INDENT, y), CHOICES[i], C_TEXT)
			if i == sel:
				var frame := int(floorf((t - CHOICES_T) * FPS))    # 0, 1, 2 … ab dem ersten Bild der Auswahl
				var bob := 1 if (frame / HAND_HOLD) % 2 == 0 else 0
				_cursor(Vector2i(x0 + bob, y - 8))
			y += LINE_H


func _window(r: Rect2i) -> void:
	var p := Vector2(r.position)
	var s := Vector2(r.size)
	# Füllung: ein Viereck mit vier Eckfarben (Gouraud)
	draw_polygon(PackedVector2Array([p + Vector2(2, 2), p + Vector2(s.x - 2, 2), p + s - Vector2(2, 2), p + Vector2(2, s.y - 2)]),
		PackedColorArray([C_TL, C_TR, C_BR, C_BL]))
	# Rahmen: außen hell, innen dunkler; Ecken um 1 px abgeschnitten
	var x0 := r.position.x
	var y0 := r.position.y
	var x1 := r.position.x + r.size.x - 1
	var y1 := r.position.y + r.size.y - 1
	_hline(x0 + 1, x1 - 1, y0, C_RIM)
	_hline(x0 + 1, x1 - 1, y1, C_RIM2)
	_vline(x0, y0 + 1, y1 - 1, C_RIM)
	_vline(x1, y0 + 1, y1 - 1, C_RIM2)
	_hline(x0 + 1, x1 - 1, y0 + 1, C_RIM2)
	_hline(x0 + 1, x1 - 1, y1 - 1, C_RIM)
	_vline(x0 + 1, y0 + 1, y1 - 1, C_RIM2)
	_vline(x1 - 1, y0 + 1, y1 - 1, C_RIM)


func _hline(xa: int, xb: int, y: int, c: Color) -> void:
	draw_rect(Rect2(xa, y, xb - xa + 1, 1), c)


func _vline(x: int, ya: int, yb: int, c: Color) -> void:
	draw_rect(Rect2(x, ya, 1, yb - ya + 1), c)


func _text(base: Vector2, s: String, c: Color) -> void:
	draw_string(font, base + Vector2(1, 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, C_SHADOW)
	draw_string(font, base, s, HORIZONTAL_ALIGNMENT_LEFT, -1, FONT_SIZE, c)


func _cursor(p: Vector2i) -> void:
	# Handzeiger pixelweise aus HAND
	for row in HAND.size():
		var line: String = HAND[row]
		for col in line.length():
			var ch := line[col]
			if ch == "#":
				draw_rect(Rect2(p.x + col, p.y + row, 1, 1), C_SHADOW)
			elif ch == "W":
				draw_rect(Rect2(p.x + col, p.y + row, 1, 1), C_TEXT)
			elif ch == "g":
				draw_rect(Rect2(p.x + col, p.y + row, 1, 1), C_HAND_SHADE)

extends Control
## Oberfläche in Renderauflösung (427×240, main.gd vergrößert ×3 mit Nearest): Ortsschild oben links,
## Dialogkasten unten (links Text mit Schreibmaschine und Parserzeile, rechts drei Auswahlen).
## Alles wird in _draw() auf ganze Pixel gezeichnet; Schrift Pixel Operator 8 / HB 8 ohne
## Kantenglättung (CC0).

const FONT := preload("res://fonts/PixelOperator8.ttf")
const FONT_B := preload("res://fonts/PixelOperatorHB8.ttf")
const FS := 8

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const BOX := Rect2i(4, 192, 419, 45)   # Dialogkasten (17,7 % des Bildes)
const COL2_X := 258                    # Auswahlspalte
const ROW0 := 204                      # erste Grundlinie
const ROW_H := 11

const BOX_T := 3.2          # Dialogkasten klappt auf
const OPEN_FRAMES := 5      # Bilder für das Aufklappen
const TYPE_T := 3.35        # Text beginnt
const CPS := 60.0           # Zeichen pro Sekunde
const CHOICE_T := 4.45      # Auswahl erscheint (Zeile für Zeile)
const PARSER_T := 4.6

# Farben (sRGB, alle in palette.png)
const INK := Color("120c1e")
const FILL := Color("231a38")
const EDGE := Color("f2dcae")
const EDGE2 := Color("5c4170")
const TEXT := Color("f6ead2")
const DIM := Color("b4a3c4")
const HOT := Color("ffb357")

var t := 0.0


func set_time(tt: float) -> void:
	t = tt
	queue_redraw()


func _text(font: Font, pos: Vector2, s: String, col: Color) -> void:
	draw_string(font, pos + Vector2(0, 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, INK)
	draw_string(font, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, FS, col)


## Kasten mit abgeschrägten Ecken: dunkle Außenlinie, helle Kante, dunkle Innenkante, Füllung
func _box(r: Rect2i) -> void:
	var x0 := r.position.x
	var y0 := r.position.y
	var w := r.size.x
	var h := r.size.y
	draw_rect(Rect2(x0 + 2, y0, w - 4, h), INK)
	draw_rect(Rect2(x0, y0 + 2, w, h - 4), INK)
	draw_rect(Rect2(x0 + 1, y0 + 1, w - 2, h - 2), INK)
	draw_rect(Rect2(x0 + 2, y0 + 1, w - 4, h - 2), EDGE)
	draw_rect(Rect2(x0 + 1, y0 + 2, w - 2, h - 4), EDGE)
	draw_rect(Rect2(x0 + 2, y0 + 2, w - 4, h - 4), EDGE2)
	draw_rect(Rect2(x0 + 3, y0 + 3, w - 6, h - 6), FILL)


func _arrow(x: int, y: int, col: Color) -> void:
	for r in 5:
		draw_rect(Rect2(x, y + r, 3 - absi(r - 2), 1), col)


func _draw() -> void:
	# Ortsschild
	var w := int(FONT_B.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, FS).x)
	_box(Rect2i(5, 5, w + 14, 17))
	_text(FONT_B, Vector2(12, 17), LOCATION, HOT)

	# Dialogkasten: klappt von der Mitte aus auf (ganze Pixel je Bild)
	if t < BOX_T:
		return
	var k := clampf((t - BOX_T) * 30.0 / OPEN_FRAMES, 0.0, 1.0)
	var h := maxi(8, int(roundf(BOX.size.y * k)))
	var cy := BOX.position.y + BOX.size.y / 2
	_box(Rect2i(BOX.position.x, cy - h / 2, BOX.size.x, h))
	if k < 1.0:
		return
	# Trennlinie zwischen Text und Auswahl
	draw_rect(Rect2(COL2_X - 10, BOX.position.y + 6, 1, BOX.size.y - 12), EDGE2)

	var n := int(floorf((t - TYPE_T) * CPS))
	var x0 := 13
	var y := ROW0
	for line in LINES:
		if n <= 0:
			break
		var s: String = line.substr(0, mini(n, line.length()))
		_text(FONT, Vector2(x0, y), s, TEXT)
		n -= line.length()
		y += ROW_H

	# Parserzeile mit blinkender Schreibmarke
	if t >= PARSER_T:
		var y3 := ROW0 + 2 * ROW_H
		_text(FONT, Vector2(x0, y3), PARSER, DIM)
		if fmod(t - PARSER_T, 0.5) < 0.3:
			var pw := int(FONT.get_string_size(PARSER, HORIZONTAL_ALIGNMENT_LEFT, -1, FS).x)
			draw_rect(Rect2(x0 + pw + 2, y3 - 7, 4, 8), DIM)

	# Auswahl: erscheint Zeile für Zeile, erste markiert, Pfeil blinkt
	for i in CHOICES.size():
		if t < CHOICE_T + 0.1 * i:
			break
		var col := HOT if i == 0 else TEXT
		_text(FONT, Vector2(COL2_X + 8, ROW0 + i * ROW_H), CHOICES[i], col)
	if t >= CHOICE_T and fmod(t - CHOICE_T, 0.6) < 0.4:
		_arrow(COL2_X, ROW0 - 6, HOT)

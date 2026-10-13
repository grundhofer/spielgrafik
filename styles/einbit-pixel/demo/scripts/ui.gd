extends Control
## Textfenster im Stil früher 1-Bit-Fensteroberflächen: Titelleiste mit Nadelstreifen und Schließfeld,
## links Erzähltext (Schreibmaschine) und Eingabezeile, rechts die Auswahl mit invertiertem Balken.
## Gezeichnet nur in Schwarz und Weiß auf ganzen Pixeln; die Palettenebene macht daraus Tinte und Papier.

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "nimm paket"
const WIN := Rect2i(4, 180, 392, 57)      # Fenster x 4–395, y 180–236
const BAR_H := 13
const BASE := [207, 219, 231]             # Grundlinien der drei Textzeilen
const COL_X := 10
const DIV_X := 229
const CHOICE_X := 241
const INK := Color(0, 0, 0)
const PAPER := Color(1, 1, 1)

var t := 0.0
var font: FontFile
var bold: FontFile


func _ready() -> void:
	font = _pixel_font("res://fonts/PixelOperator.ttf")
	bold = _pixel_font("res://fonts/PixelOperator-Bold.ttf")


func _pixel_font(path: String) -> FontFile:
	var f := FontFile.new()
	f.load_dynamic_font(path)
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.generate_mipmaps = false
	f.oversampling = 1.0
	return f


func _rect(x0: int, y0: int, x1: int, y1: int, c: Color) -> void:
	draw_rect(Rect2(x0, y0, x1 - x0 + 1, y1 - y0 + 1), c)


func _text(fnt: FontFile, x: int, base: int, s: String, c: Color) -> void:
	draw_string(fnt, Vector2(x, base), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 16, c)


func _draw() -> void:
	var x0 := WIN.position.x
	var y0 := WIN.position.y
	var x1 := x0 + WIN.size.x - 1
	var y1 := y0 + WIN.size.y - 1
	# Papierrand außen, Schatten rechts unten, Rahmen
	_rect(x0 - 1, y0 - 1, x1 + 2, y1 + 2, PAPER)
	_rect(x0 + 1, y1 + 1, x1 + 1, y1 + 1, INK)
	_rect(x1 + 1, y0 + 1, x1 + 1, y1 + 1, INK)
	_rect(x0, y0, x1, y1, INK)
	_rect(x0 + 1, y0 + 1, x1 - 1, y1 - 1, PAPER)
	# Titelleiste: Nadelstreifen, Schließfeld, Titel in einer Lücke
	var by0 := y0 + 1
	var by1 := y0 + BAR_H
	for y in range(by0 + 2, by1 - 1, 2):
		_rect(x0 + 2, y, x1 - 2, y, INK)
	_rect(x0 + 6, by0 + 1, x0 + 18, by1 - 1, PAPER)
	_rect(x0 + 8, by0 + 2, x0 + 16, by1 - 2, INK)
	_rect(x0 + 9, by0 + 3, x0 + 15, by1 - 3, PAPER)
	var tw := int(bold.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x)
	var tx := 200 - tw / 2
	_rect(tx - 6, by0 + 1, tx + tw + 5, by1 - 1, PAPER)
	_text(bold, tx, by1 - 1, LOCATION, INK)
	_rect(x0 + 1, by1 + 1, x1 - 1, by1 + 1, INK)
	# Trennlinie zwischen Text und Auswahl (gepunktet)
	for y in range(by1 + 3, y1 - 1, 2):
		_rect(DIV_X, y, DIV_X, y, INK)
	# Erzähltext mit Schreibmaschine (32 Zeichen/s ab 0,3 s)
	var shown := int(floor((t - 0.3) * 32.0))
	for i in 2:
		var s: String = LINES[i]
		var n := clampi(shown, 0, s.length())
		if n > 0:
			_text(font, COL_X, BASE[i], s.substr(0, n), INK)
		shown -= s.length() + 4
	# Eingabezeile: "> " und ab 3,0 s getippt (10 Zeichen/s), Blockcursor blinkt (0,4 s)
	var typed := clampi(int(floor((t - 3.0) * 10.0)), 0, PARSER.length())
	var line := "> " + PARSER.substr(0, typed)
	_text(font, COL_X, BASE[2], line, INK)
	var cw := int(font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x)
	if fposmod(t, 0.4) < 0.24:
		_rect(COL_X + cw + 1, BASE[2] - 9, COL_X + cw + 6, BASE[2] - 1, INK)
	# Auswahl: Markierung wandert (2,6 s, 3,6 s, 4,4 s), markierter Eintrag invertiert
	var sel := -1
	if t >= 4.4:
		sel = 2
	elif t >= 3.6:
		sel = 1
	elif t >= 2.6:
		sel = 0
	for i in 3:
		var b: int = BASE[i]
		var fg := INK
		if i == sel:
			_rect(DIV_X + 3, b - 11, x1 - 3, b + 2, INK)
			fg = PAPER
		# Pfeilspitze ▸ (3×5)
		var ax := CHOICE_X - 7
		_rect(ax, b - 7, ax, b - 3, fg)
		_rect(ax + 1, b - 6, ax + 1, b - 4, fg)
		_rect(ax + 2, b - 5, ax + 2, b - 5, fg)
		_text(font, CHOICE_X, b, CHOICES[i], fg)

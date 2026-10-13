extends Control
## 1-Bit-Oberfläche (640×360): Ortsschild oben links, Dialogkasten unten rechts.
##
## Gezeichnet wird nur in Weiß (= Papier) und Schwarz (= Tinte); die Ebene "Palette" setzt danach die zwei
## Farben. Zwei Rasterschriften des Soft-Type-Projekts, beide in ihrer nativen Größe (ein Schriftpixel = ein
## Bildpixel) und ohne Kantenglättung: Jacquard 12 (Pixel-Fraktur, 12 px Versalhöhe) für den Ort, Jersey 10
## (10 px Versalhöhe, 2 px breite Stämme) für Text, Auswahl und Parser. Kästen mit doppelter Linie und Schatten
## aus einem 50-%-Schachbrettmuster. Der Dialog öffnet sich bei OPEN_T mit "Zoom-Rechtecken" vom Dachs zum
## Kasten (wie Fenster früher Schreibtischoberflächen), dann läuft der Text Zeichen für Zeichen.

const PAPER := Color.WHITE
const INK := Color.BLACK
const OPEN_T := 3.9              # Zoom-Rechtecke
const OPEN_LEN := 0.25
const TEXT_T := 4.12             # Text beginnt
const CPS := 75.0                # Zeichen je Sekunde
const CHOICE_T := 5.3            # Auswahl springt von 1 auf 2
const ZOOM_FROM := Rect2(150, 196, 44, 30)

const PLATE := Rect2i(8, 8, 182, 30)
const BOX := Rect2i(300, 261, 332, 91)
const TITLE_SIZE := 21           # Jacquard 12: Raster 60 Einheiten bei 1260 je Geviert -> 21 px
## Jersey 10: Raster 75 Einheiten bei 1400 je Geviert, nativ also 18 2/3 px. Godot kennt nur ganzzahlige
## Schriftgrößen. Deshalb Größe 14 und die Umrisse über FontVariation.variation_transform um 4/3 vergrößert:
## FreeType skaliert die Umrisse vor dem Rastern, jedes Schriftpixel fällt genau auf ein Bildpixel. Den
## Vorschub skaliert die Transformation nicht mit; _body() setzt die Zeichen deshalb einzeln und nimmt den
## Vorschub aus Größe 56 (3 px je Schriftpixel, ganzzahlig) geteilt durch 3. Jersey 10 hat keine Unterschneidung.
const BODY_SIZE := 14
const BODY_SCALE := 4.0 / 3.0
const LINE := 14                 # Zeilenabstand

var t := 0.0                     # Zeit aus main.gd (feste Schritte von 1/30 s)
var line1 := "Die Laterne flackert im Wind."
var line2 := "Am Kai wartet ein Paket auf dich."
var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
var prompt := "> nimm paket"
var title_font: FontFile
var body_base: FontFile
var body_font: FontVariation
var advance := {}                # Zeichen -> Vorschub in px (native Größe)
var checker: ImageTexture


@onready var owner_main: Node = get_tree().current_scene


## Schriften hier einrichten, nicht erst in _draw(): Eine Schrift, die im ersten _draw() geladen und umgestellt
## wurde, zeichnete in einem Versuch jedes Zeichen als volles Rechteck.
func _ready() -> void:
	title_font = _pixel_font("res://fonts/Jacquard12-Regular.ttf")
	body_base = _pixel_font("res://fonts/Jersey10-Regular.ttf")
	body_font = FontVariation.new()
	body_font.base_font = body_base
	body_font.variation_transform = Transform2D(Vector2(BODY_SCALE, 0.0), Vector2(0.0, BODY_SCALE), Vector2.ZERO)
	var img := Image.create(2, 2, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	img.set_pixel(0, 0, INK)
	img.set_pixel(1, 1, INK)
	checker = ImageTexture.create_from_image(img)


func _pixel_font(path: String) -> FontFile:
	var f := load(path) as FontFile
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	f.generate_mipmaps = false
	f.opentype_feature_overrides = {"liga": 0, "clig": 0, "dlig": 0}   # keine fl-Ligatur
	return f


func _process(_delta: float) -> void:
	t = owner_main.t
	queue_redraw()


func _draw() -> void:
	_panel(PLATE)
	draw_string(title_font, Vector2(PLATE.position.x + 10, PLATE.position.y + 20), "Hafen von Lornholm",
		HORIZONTAL_ALIGNMENT_LEFT, -1, TITLE_SIZE, INK)

	if t < OPEN_T:
		return
	if t < OPEN_T + OPEN_LEN:
		# Zoom-Rechtecke: vier Rahmen wandern vom Dachs zum Kasten
		var k := (t - OPEN_T) / OPEN_LEN
		for i in 4:
			var u := clampf(k * 1.4 - 0.12 * i, 0.0, 1.0)
			if u <= 0.0:
				continue
			var r := Rect2(ZOOM_FROM.position.lerp(Vector2(BOX.position), u), ZOOM_FROM.size.lerp(Vector2(BOX.size), u))
			_zoom_rect(Rect2i(r))
		return

	_panel(BOX)
	var x0 := BOX.position.x + 10
	var y := BOX.position.y + 19                # Grundlinie der ersten Zeile (Versalhöhe 10 px)
	var shown := int(floor((t - TEXT_T) * CPS))
	if shown > 0:
		_body(Vector2i(x0, y), line1.substr(0, mini(shown, line1.length())), INK)
		_body(Vector2i(x0, y + LINE), line2.substr(0, clampi(shown - line1.length(), 0, line2.length())), INK)
	var done := shown >= line1.length() + line2.length()
	if not done:
		return
	# punktierte Trennlinie
	var ys := y + LINE + 5
	for xx in range(x0, BOX.end.x - 10, 2):
		draw_rect(Rect2(xx, ys, 1, 1), INK)
	var sel := 0 if t < CHOICE_T else 1
	for i in choices.size():
		var cy := ys + 14 + i * LINE
		if i == sel:
			draw_rect(Rect2(x0 - 3, cy - 11, 210, LINE), INK)
			_pointer(Vector2i(x0 - 1, cy - 9))
			_body(Vector2i(x0 + 12, cy), choices[i], PAPER)
		else:
			_body(Vector2i(x0 + 12, cy), choices[i], INK)
	# Parserzeile unten rechts (Grundlinie wie die letzte Auswahl) mit blinkendem Block (15 Bilder an, 15 aus)
	var py := ys + 14 + 2 * LINE
	var w := _body_width(prompt)
	var px := BOX.end.x - 12 - 7 - w
	_body(Vector2i(px, py), prompt, INK)
	if int(floor(t * 2.0)) % 2 == 0:
		draw_rect(Rect2(px + w + 2, py - 10, 6, 10), INK)


## Jersey 10 in nativer Größe: Zeichen einzeln setzen (siehe BODY_SCALE)
func _body(pos: Vector2i, s: String, color: Color) -> void:
	var x := pos.x
	for c in s:
		draw_char(body_font, Vector2(x, pos.y), c, BODY_SIZE, color)
		x += _advance(c)


func _body_width(s: String) -> int:
	var w := 0
	for c in s:
		w += _advance(c)
	return w


func _advance(c: String) -> int:
	if not advance.has(c):
		advance[c] = int(roundf(body_base.get_char_size(c.unicode_at(0), BODY_SIZE * 4).x / 3.0))
	return advance[c]


## Kasten: Papierfläche, doppelte Tintenlinie, Schatten als Schachbrettmuster rechts und unten
func _panel(r: Rect2i) -> void:
	draw_texture_rect(checker, Rect2(r.position.x + 4, r.end.y, r.size.x, 4), true)
	draw_texture_rect(checker, Rect2(r.end.x, r.position.y + 4, 4, r.size.y - 4), true)
	draw_rect(Rect2(r), INK)
	draw_rect(Rect2(r.grow(-1)), PAPER)
	draw_rect(Rect2(r.grow(-2)), INK)
	draw_rect(Rect2(r.grow(-3)), PAPER)


## Zoom-Rechteck: durchgehende 1-px-Tintenlinie mit einer Papierlinie innen daneben. Auf hellem Grund trägt die
## Tinte, auf dunklem das Papier, auf Rastern beide (punktierte Rahmen gingen im Pflaster- und Wasserraster unter).
func _zoom_rect(r: Rect2i) -> void:
	_frame(r, INK)
	_frame(r.grow(-1), PAPER)


func _frame(r: Rect2i, c: Color) -> void:
	draw_rect(Rect2(r.position.x, r.position.y, r.size.x, 1), c)
	draw_rect(Rect2(r.position.x, r.end.y - 1, r.size.x, 1), c)
	draw_rect(Rect2(r.position.x, r.position.y, 1, r.size.y), c)
	draw_rect(Rect2(r.end.x - 1, r.position.y, 1, r.size.y), c)


## Zeiger: kleiner Pfeil nach rechts, 7 px hoch, Papier auf der Tintenleiste
func _pointer(p: Vector2i) -> void:
	for i in 4:
		draw_rect(Rect2(p.x + i, p.y + i, 1, 7 - 2 * i), PAPER)
	draw_rect(Rect2(p.x - 3, p.y + 3, 3, 1), PAPER)

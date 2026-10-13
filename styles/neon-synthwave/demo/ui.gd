extends Control
## Oberfläche im Neonstil, in _draw() gezeichnet (Text aus data/motif.json → ui_text):
##   - Ortsschild oben links in Monoton, zündet wie eine Neonröhre (Flackern mit festen Zeiten)
##   - Textfeld unten: dunkle Glasfläche, Rahmen als Cyan-Röhre, innen eine dünne Magentalinie
##   - links die Zeile (Tilt Neon, getippt), darunter die Eingabe "> nimm paket" mit Blockcursor
##   - rechts drei Handlungen; die gewählte bekommt einen Pfeil und leuchtet
## Die Oberfläche liegt in CanvasLayer 1 und damit noch im Glow (background_canvas_max_layer = 1):
## Werte über 0,9 (linear) leuchten, der Fließtext bleibt darunter und scharf.

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const SIGN_ON := [0.25, 0.32, 0.42, 0.47, 0.55]   # Zündflackern: an/aus im Wechsel, ab dem letzten Wert an
const BOX_ON := [0.05, 0.1, 0.17, 0.21, 0.26]   # ungerade Anzahl: endet an
const TYPE_T := 0.6          # Beginn der Zeile
const TYPE_CPS := 30.0       # Zeichen je Sekunde (eins je Bild)
const CHOICE_T := 3.1        # Handlungen erscheinen
const SELECT_T := 4.6        # Auswahl springt von 1 auf 2
const PARSER_T := 3.7        # Eingabe beginnt
const PARSER_CPS := 10.0     # ein Zeichen je 3 Bilder

const BOX := Rect2(28, 556, 1224, 144)

var t := 0.0
var f_title: Font
var f_text: Font
var f_mono: Font


var plate := StyleBoxFlat.new()


func _ready() -> void:
	plate.bg_color = Color(0.012, 0.004, 0.03, 0.62)
	plate.set_corner_radius_all(10)
	plate.shadow_color = Color(0.012, 0.004, 0.03, 0.5)
	plate.shadow_size = 16
	f_title = load("res://fonts/Monoton-Regular.ttf")
	var tilt := load("res://fonts/TiltNeon.ttf") as FontFile
	f_text = tilt
	f_mono = tilt


static func _lin(c: Color, k: float) -> Color:
	var l := c.srgb_to_linear()
	return Color(l.r * k, l.g * k, l.b * k, c.a)


func _flicker(times: Array) -> float:
	var on := false
	for i in times.size():
		if t >= times[i]:
			on = (i % 2) == 0
	return 1.0 if on else 0.08


func _draw() -> void:
	# --- Ortsschild ---------------------------------------------------------------------------
	var lv := _flicker(SIGN_ON)
	var pink := Color("ff3cac")
	var title_pos := Vector2(42, 78)
	# dunkle, weich auslaufende Platte hinter dem Schild (Strahl, Möwen und Rauch ziehen dahinter durch)
	draw_style_box(plate, Rect2(30, 38, 488, 54))
	# Röhre: breiter, farbiger Zug unten, heller Kern darüber
	draw_string(f_title, title_pos, LOCATION.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 34, _lin(pink, 1.6 * lv))

	# --- Textfeld (Rahmen zündet ebenfalls) -----------------------------------------------------
	var bl := _flicker(BOX_ON)
	draw_rect(BOX, Color(0.010, 0.003, 0.026, 0.93))
	_neon_rect(BOX, Color("1fe4ff"), 1.5 * bl, 2.0)
	_neon_rect(BOX.grow(-6), Color("ff2a9e"), 0.55 * bl, 1.0)
	# Trennlinie zwischen Zeile und Handlungen
	draw_line(Vector2(812, BOX.position.y + 18), Vector2(812, BOX.end.y - 18), _lin(Color("ff2a9e"), 0.8 * bl), 1.0)

	var n := clampi(int(floor((t - TYPE_T) * TYPE_CPS + 0.5)), 0, LINE.length())
	var shown := LINE.substr(0, n)
	# Zeilenumbruch von Hand an fester Stelle (nach "Wind."), damit nichts beim Tippen springt
	var l1 := LINE.substr(0, LINE.find("Am "))
	var y0 := BOX.position.y + 44
	var text_col := _lin(Color("ffe6f6"), 0.85)
	draw_string(f_text, Vector2(56, y0), shown.substr(0, mini(n, l1.length())), HORIZONTAL_ALIGNMENT_LEFT, -1, 25, text_col)
	if n > l1.length():
		draw_string(f_text, Vector2(56, y0 + 32), shown.substr(l1.length()), HORIZONTAL_ALIGNMENT_LEFT, -1, 25, text_col)

	# Eingabe
	var pn := clampi(int(floor((t - PARSER_T) * PARSER_CPS + 0.5)), 0, PARSER.length())
	var py := BOX.end.y - 22
	var cyan := Color("1fe4ff")
	var ptxt := PARSER.substr(0, maxi(pn, 2)) if t >= PARSER_T - 0.6 else ">"
	draw_string(f_mono, Vector2(56, py), ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 22, _lin(cyan, 1.05))
	var w := f_mono.get_string_size(ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 22).x
	var blink := fmod(t, 0.8) < 0.45
	if blink:
		draw_rect(Rect2(60 + w, py - 17, 11, 20), _lin(cyan, 1.3))

	# Handlungen
	if t >= CHOICE_T:
		var sel := 1 if t >= SELECT_T else 0
		for i in CHOICES.size():
			var appear := clampf((t - CHOICE_T - 0.12 * i) / 0.15, 0.0, 1.0)
			if appear <= 0.0:
				continue
			var yy := BOX.position.y + 38 + 38 * i
			var is_sel := i == sel
			var col := _lin(Color("ff5ec0") if is_sel else Color("d9ceff"), (1.45 if is_sel else 0.85) * appear)
			draw_string(f_text, Vector2(880, yy), "%d" % (i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 20,
				_lin(Color("1fe4ff"), 0.9 * appear))
			draw_string(f_text, Vector2(910, yy), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 23, col)
			if is_sel:
				var ax := 846.0 + 3.0 * sin(t * 6.0)
				draw_colored_polygon(PackedVector2Array([Vector2(ax, yy - 16), Vector2(ax + 14, yy - 8),
					Vector2(ax, yy)]), _lin(Color("ff2a9e"), 1.8 * appear))


func _neon_rect(r: Rect2, c: Color, k: float, width: float) -> void:
	draw_rect(r, _lin(c, k), false, width)

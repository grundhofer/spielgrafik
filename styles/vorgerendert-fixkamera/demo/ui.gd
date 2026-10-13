extends Control
## Oberfläche in 320×240 (wird mit dem Bild ganzzahlig ×3 vergrößert).
## Totale: Ortstitel als Einblendung oben links (wie Ortskarten beim Betreten eines Schauplatzes).
## Nahaufnahme: Dialogfenster unten, halbtransparent dunkel mit dünnem Metallrahmen, Text erscheint
## Zeichen für Zeichen, danach die Auswahl mit Zeiger. Schriften: Cinzel (Titel), Fira Sans (Text), beide OFL.

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const TITLE_IN := 0.25
const CUT_TIME := 2.1           # wie main.gd
const TEXT_T := 2.45             # Beginn des Textes (kurz nach dem Schnitt)
const CPS := 38.0                # Zeichen je Sekunde
const BOX := Rect2i(10, 170, 300, 66)
const LINE_H := 11

var t := 0.0
var shot := "totale"
var title_font := FontFile.new()
var text_font := FontFile.new()


func _ready() -> void:
	for pair in [[title_font, "res://fonts/Cinzel-wght.ttf"], [text_font, "res://fonts/FiraSans-Medium.ttf"]]:
		var f: FontFile = pair[0]
		f.load_dynamic_font(pair[1])
		f.antialiasing = TextServer.FONT_ANTIALIASING_GRAY
		f.hinting = TextServer.HINTING_LIGHT
		f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
		f.generate_mipmaps = false
	var ts := TextServerManager.get_primary_interface()
	title_font.set_variation_coordinates(0, {ts.name_to_tag("wght"): 600})


func _draw() -> void:
	if shot == "totale":
		_draw_title()
	else:
		_draw_dialog()


func _draw_title() -> void:
	# unten rechts auf dem leeren Pflaster, rechtsbündig, wie eine Ortseinblendung im Film
	var a := smoothstep(TITLE_IN, TITLE_IN + 0.5, t) * (1.0 - smoothstep(CUT_TIME - 0.25, CUT_TIME - 0.05, t))
	if a <= 0.0:
		return
	var size := 12
	var up := LOCATION.to_upper()
	var widths := []
	var w := 0
	for ch in up:
		var cw := int(title_font.get_string_size(ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x) + 1
		widths.append(cw)
		w += cw
	var x := 308 - w
	var y := 226
	# feine Linie über dem Titel, nach links auslaufend
	for i in w + 30:
		var fade := float(i) / float(w + 30)
		draw_rect(Rect2(x - 30 + i, y - 13, 1, 1), Color(0.95, 0.78, 0.5, 0.85 * a * fade))
	var pen := x
	for k in up.length():
		var ch := up[k]
		draw_string(title_font, Vector2(pen + 1, y + 1), ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(0, 0, 0, 0.8 * a))
		draw_string(title_font, Vector2(pen, y), ch, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(0.97, 0.93, 0.84, a))
		pen += int(widths[k])


func _draw_dialog() -> void:
	var a := smoothstep(CUT_TIME + 0.05, CUT_TIME + 0.3, t)
	if a <= 0.0:
		return
	var r := BOX
	# Fläche: schwarz-blau, halbtransparent, oben etwas heller (Verlauf in 4 Stufen)
	for k in 4:
		var hh := r.size.y / 4
		draw_rect(Rect2(r.position.x, r.position.y + k * hh, r.size.x, hh + (r.size.y - 4 * hh if k == 3 else 0)),
			Color(0.05 + 0.012 * (3 - k), 0.06 + 0.012 * (3 - k), 0.1 + 0.015 * (3 - k), 0.74 * a))
	# Rahmen: außen hell (Metall), innen dunkel; Ecken 1 px abgeschrägt
	var hi := Color(0.72, 0.74, 0.8, a)
	var lo := Color(0.0, 0.0, 0.0, 0.8 * a)
	var x0 := r.position.x
	var y0 := r.position.y
	var x1 := r.position.x + r.size.x - 1
	var y1 := r.position.y + r.size.y - 1
	draw_rect(Rect2(x0 + 1, y0, r.size.x - 2, 1), hi)
	draw_rect(Rect2(x0 + 1, y1, r.size.x - 2, 1), Color(0.45, 0.47, 0.53, a))
	draw_rect(Rect2(x0, y0 + 1, 1, r.size.y - 2), hi)
	draw_rect(Rect2(x1, y0 + 1, 1, r.size.y - 2), Color(0.45, 0.47, 0.53, a))
	draw_rect(Rect2(x0 + 1, y0 + 1, r.size.x - 2, 1), lo)
	draw_rect(Rect2(x0 + 1, y0 + 1, 1, r.size.y - 2), lo)
	# Text Zeichen für Zeichen
	var shown := int(maxf(0.0, t - TEXT_T) * CPS)
	var size := 11
	var tx := x0 + 9
	var ty := y0 + 13
	for li in LINES.size():
		var line: String = LINES[li]
		var n := clampi(shown, 0, line.length())
		shown -= line.length()
		if n > 0:
			_text(line.substr(0, n), tx, ty + li * LINE_H, size, Color(0.96, 0.95, 0.9, a))
	# Auswahl, sobald der Text steht
	var done_t := TEXT_T + float(LINES[0].length() + LINES[1].length()) / CPS
	var ca := smoothstep(done_t + 0.15, done_t + 0.4, t) * a
	if ca > 0.0:
		var cy := ty + 2 * LINE_H + 3
		for ci in CHOICES.size():
			var sel := ci == 0
			var col := Color(1.0, 0.86, 0.55, ca) if sel else Color(0.78, 0.8, 0.86, ca)
			_text(CHOICES[ci], tx + 12, cy + ci * LINE_H, size, col)
		# Zeiger: kleines Dreieck, pulsiert in ganzen Pixeln
		var px := tx + 2 + (1 if fmod(t, 0.6) < 0.3 else 0)
		var py := cy - 7
		for k in 5:
			var hw := 2 - absi(k - 2)
			draw_rect(Rect2(px, py + k, hw + 1, 1), Color(1.0, 0.86, 0.55, ca))


func _text(s: String, x: int, y: int, size: int, col: Color) -> void:
	draw_string(text_font, Vector2(x + 1, y + 1), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(0, 0, 0, 0.8 * col.a))
	draw_string(text_font, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, col)


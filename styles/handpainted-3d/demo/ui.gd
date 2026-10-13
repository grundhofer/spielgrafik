extends Control
## Oberfläche im Stil stilisierter Online-Rollenspiele:
##  - Gebietsname oben in der Mitte (Cinzel, Gold mit dunkler Kontur), blendet zu Beginn ein
##  - Dialogfenster unten rechts: Rahmen in dunklem Holzbraun (flache Farbe) mit Goldkante,
##    Pergament aus der gemalten Putztextur (plaster.png) getönt, Text Zeichen für Zeichen (Alegreya),
##    drei Auswahlzeilen mit Symbolen (Pfeil, goldenes Ausrufezeichen, Sprechblase), die zweite wird hervorgehoben,
##    darunter eine Eingabezeile für den Parser mit blinkender Schreibmarke.
## Zeit über aufsummiertes delta, keine Zufälle.

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "nimm paket"

const PANEL := Rect2(822, 462, 436, 238)
const ZONE_T0 := 0.25
const ZONE_T1 := 1.35
const PANEL_T0 := 1.8
const PANEL_T1 := 2.2
const TEXT_T0 := 2.2
const TEXT_CPS := 46.0
const CHOICE_T0 := 3.45
const PARSER_T0 := 4.1
const PARSER_CPS := 9.0
const HILITE_T := 4.4

const GOLD := Color(1.0, 0.82, 0.38)
const GOLD_DARK := Color(0.62, 0.44, 0.16)
const FRAME := Color(0.20, 0.13, 0.10)
const INK := Color(0.23, 0.13, 0.07)
const CHOICE_INK := Color(0.36, 0.14, 0.06)

var t := 0.0
var cinzel := FontVariation.new()
var cinzel_bold := FontVariation.new()
var body := FontVariation.new()
var body_bold := FontVariation.new()
var parchment: Texture2D


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--t0="):
			t = float(arg.trim_prefix("--t0="))   # gleiche Startzeit wie main.gd
	var cz: FontFile = load("res://fonts/Cinzel-wght.ttf")
	var al: FontFile = load("res://fonts/Alegreya-wght.ttf")
	cinzel.base_font = cz
	cinzel.variation_opentype = {"wght": 600}
	cinzel_bold.base_font = cz
	cinzel_bold.variation_opentype = {"wght": 800}
	body.base_font = al
	body.variation_opentype = {"wght": 480}
	body_bold.base_font = al
	body_bold.variation_opentype = {"wght": 650}
	parchment = load("res://textures/plaster.png")


func _process(delta: float) -> void:
	t += delta
	queue_redraw()


func _draw() -> void:
	_draw_zone()
	_draw_panel()


# --- Gebietsname ---------------------------------------------------------------------------------
func _draw_zone() -> void:
	var a := smoothstep(ZONE_T0, ZONE_T1, t)
	if a <= 0.0:
		return
	var size := 46
	var w := cinzel_bold.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var pos := Vector2(640.0 - w / 2.0, 92.0 + 6.0 * (1.0 - a))
	# weicher Schatten, dunkle Kontur, Gold
	for o in [Vector2(3, 4), Vector2(2, 3)]:
		draw_string(cinzel_bold, pos + o, LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(0.08, 0.04, 0.1, 0.35 * a))
	draw_string_outline(cinzel_bold, pos, LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, size, 7, Color(0.16, 0.08, 0.04, 0.95 * a))
	draw_string(cinzel_bold, pos, LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(GOLD, a))
	# Lichtkante oben auf den Buchstaben (gemalter Goldverlauf, angedeutet)
	draw_string(cinzel_bold, pos + Vector2(0, -1), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(1.0, 0.95, 0.75, 0.35 * a))
	draw_string(cinzel_bold, pos, LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(GOLD, a))
	# Zierlinie mit Raute
	var y := pos.y + 16.0
	var half := w * 0.42
	for side in [-1.0, 1.0]:
		var p0 := Vector2(640.0 + side * 14.0, y)
		var p1 := Vector2(640.0 + side * half, y)
		draw_line(p0 + Vector2(0, 1.5), p1 + Vector2(0, 1.5), Color(0.1, 0.05, 0.03, 0.7 * a), 3.0, true)
		draw_line(p0, p1, Color(GOLD, 0.9 * a), 2.0, true)
	_diamond(Vector2(640.0, y), 7.0, Color(GOLD, a), Color(0.16, 0.08, 0.04, a))


# --- Dialogfenster -------------------------------------------------------------------------------
func _draw_panel() -> void:
	var a := smoothstep(PANEL_T0, PANEL_T1, t)
	if a <= 0.0:
		return
	var r := PANEL
	r.position.y += 18.0 * (1.0 - a)
	# Schatten
	for i in 4:
		var g := 4.0 + i * 4.0
		_rrect(Rect2(r.position + Vector2(4, 6), r.size).grow(g - 2.0), 14.0 + g, Color(0.05, 0.02, 0.08, 0.10 * a))
	# Rahmen: dunkles Holzbraun (flach), Goldkante, Pergament
	_rrect(r, 12.0, Color(FRAME, a))
	_rrect(r.grow(-3.0), 10.0, Color(0.32, 0.21, 0.14, a))
	_rrect(r.grow(-6.0), 8.0, Color(GOLD_DARK, a))
	_rrect(r.grow(-8.0), 7.0, Color(GOLD, a))
	var inner := r.grow(-10.0)
	_rrect(inner, 6.0, Color(0.95, 0.88, 0.72, a))
	# Pergament: gemalte Putztextur, warm getönt
	draw_texture_rect_region(parchment, inner.grow(-2.0), Rect2(40, 60, 380, 214), Color(1.0, 0.88, 0.68, 0.85 * a))
	_edge_shade(inner.grow(-2.0), Color(0.45, 0.27, 0.10, 0.28 * a), 18.0)
	# Nieten an den Ecken
	for c in [r.position + Vector2(9, 9), r.position + Vector2(r.size.x - 9, 9),
			r.position + Vector2(9, r.size.y - 9), r.position + r.size - Vector2(9, 9)]:
		draw_circle(c + Vector2(0.5, 1), 5.0, Color(0.08, 0.04, 0.02, a))
		draw_circle(c, 4.5, Color(GOLD_DARK, a))
		draw_circle(c - Vector2(1.2, 1.2), 2.2, Color(1.0, 0.92, 0.6, a))
	_diamond(Vector2(r.position.x + r.size.x / 2.0, r.position.y + 4.0), 8.0, Color(GOLD, a), Color(FRAME, a))

	var x0 := inner.position.x + 18.0
	var y := inner.position.y + 34.0
	# Erzählzeile, Zeichen für Zeichen, mit Umbruch
	var n := int(clampf((t - TEXT_T0) * TEXT_CPS, 0.0, LINE.length()))
	var shown := LINE.substr(0, n)
	var lines := _wrap(LINE, body, 21, inner.size.x - 36.0)
	var used := 0
	for ln in lines:
		var part := shown.substr(used, ln.length())
		if part.length() > 0:
			draw_string(body, Vector2(x0, y), part, HORIZONTAL_ALIGNMENT_LEFT, -1, 21, Color(INK, a))
		used += ln.length() + 1
		y += 26.0
	# Trennlinie
	y += 2.0
	var ca := smoothstep(CHOICE_T0, CHOICE_T0 + 0.35, t)
	draw_line(Vector2(x0, y - 12.0), Vector2(inner.end.x - 18.0, y - 12.0), Color(0.55, 0.38, 0.18, 0.55 * ca * a), 1.5, true)
	# Auswahl mit Symbolen
	for i in CHOICES.size():
		var ci := smoothstep(CHOICE_T0 + 0.12 * i, CHOICE_T0 + 0.12 * i + 0.3, t) * a
		if ci <= 0.0:
			continue
		var cy := y + 6.0 + 31.0 * i
		var hil := i == 1 and t >= HILITE_T
		if hil:
			var hr := Rect2(x0 - 6.0, cy - 21.0, inner.size.x - 24.0, 28.0)
			_rrect(hr, 6.0, Color(1.0, 0.86, 0.45, 0.55 * ci))
			_rrect(hr.grow(-2.0), 5.0, Color(1.0, 0.95, 0.75, 0.45 * ci))
		_icon(i, Vector2(x0 + 11.0, cy - 7.0), ci)
		var col := Color(0.55, 0.12, 0.02, ci) if hil else Color(CHOICE_INK, ci)
		draw_string(body_bold, Vector2(x0 + 30.0, cy), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 20, col)
	# Eingabezeile für den Parser
	var pa := smoothstep(PARSER_T0 - 0.3, PARSER_T0, t) * a
	if pa > 0.0:
		var ir := Rect2(x0 - 6.0, inner.end.y - 34.0, inner.size.x - 24.0, 26.0)
		_rrect(ir, 5.0, Color(0.20, 0.13, 0.09, 0.85 * pa))
		_rrect(ir.grow(-1.5), 4.0, Color(0.30, 0.20, 0.13, 0.85 * pa))
		var m := int(clampf((t - PARSER_T0) * PARSER_CPS, 0.0, PARSER.length()))
		var txt := "> " + PARSER.substr(0, m)
		var tp := Vector2(ir.position.x + 10.0, ir.position.y + 19.0)
		draw_string(body_bold, tp, txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(1.0, 0.9, 0.62, pa))
		if fmod(t, 0.8) < 0.5:
			var cx := tp.x + body_bold.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x + 2.0
			draw_rect(Rect2(cx, tp.y - 14.0, 2.0, 17.0), Color(1.0, 0.9, 0.62, pa))


# --- Zeichenhilfen -------------------------------------------------------------------------------
func _rrect(r: Rect2, radius: float, col: Color) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = col
	sb.set_corner_radius_all(int(radius))
	sb.anti_aliasing = true
	sb.corner_detail = 8
	draw_style_box(sb, r)


func _edge_shade(r: Rect2, col: Color, w: float) -> void:
	var c0 := col
	var c1 := Color(col, 0.0)
	var p := r.position
	var e := r.end
	draw_polygon(PackedVector2Array([p, Vector2(e.x, p.y), Vector2(e.x, p.y + w), Vector2(p.x, p.y + w)]),
		PackedColorArray([c0, c0, c1, c1]))
	draw_polygon(PackedVector2Array([Vector2(p.x, e.y - w), Vector2(e.x, e.y - w), e, Vector2(p.x, e.y)]),
		PackedColorArray([c1, c1, c0, c0]))
	draw_polygon(PackedVector2Array([p, Vector2(p.x + w, p.y), Vector2(p.x + w, e.y), Vector2(p.x, e.y)]),
		PackedColorArray([c0, c1, c1, c0]))
	draw_polygon(PackedVector2Array([Vector2(e.x - w, p.y), Vector2(e.x, p.y), e, Vector2(e.x - w, e.y)]),
		PackedColorArray([c1, c0, c0, c1]))


func _diamond(c: Vector2, s: float, fill: Color, edge: Color) -> void:
	var pts := PackedVector2Array([c + Vector2(0, -s), c + Vector2(s, 0), c + Vector2(0, s), c + Vector2(-s, 0)])
	var big := PackedVector2Array([c + Vector2(0, -s - 2), c + Vector2(s + 2, 0), c + Vector2(0, s + 2), c + Vector2(-s - 2, 0)])
	draw_colored_polygon(big, edge)
	draw_colored_polygon(pts, fill)
	draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s), c + Vector2(s * 0.5, -s * 0.5), c, c + Vector2(-s * 0.5, -s * 0.5)]),
		Color(1.0, 0.96, 0.8, fill.a * 0.6))


func _icon(kind: int, c: Vector2, a: float) -> void:
	match kind:
		0:  # Weg: goldener Kreis mit Pfeil
			draw_circle(c + Vector2(0.5, 1.0), 9.5, Color(0.12, 0.06, 0.02, a))
			draw_circle(c, 9.0, Color(GOLD_DARK, a))
			draw_circle(c - Vector2(1, 1), 7.0, Color(GOLD, a))
			var arrow := PackedVector2Array([c + Vector2(-5, -2), c + Vector2(0, -2), c + Vector2(0, -6),
				c + Vector2(6, 0), c + Vector2(0, 6), c + Vector2(0, 2), c + Vector2(-5, 2)])
			draw_colored_polygon(arrow, Color(0.30, 0.15, 0.04, a))
		1:  # Auftrag: goldenes Ausrufezeichen mit dunkler Kontur
			var bar := PackedVector2Array([c + Vector2(-4, -11), c + Vector2(4, -11), c + Vector2(2.2, 4), c + Vector2(-2.2, 4)])
			var bar_o := PackedVector2Array([c + Vector2(-6, -13), c + Vector2(6, -13), c + Vector2(3.8, 6), c + Vector2(-3.8, 6)])
			draw_colored_polygon(bar_o, Color(0.16, 0.07, 0.02, a))
			draw_circle(c + Vector2(0, 9.5), 4.6, Color(0.16, 0.07, 0.02, a))
			draw_colored_polygon(bar, Color(1.0, 0.84, 0.2, a))
			draw_circle(c + Vector2(0, 9.5), 3.0, Color(1.0, 0.84, 0.2, a))
			draw_line(c + Vector2(-1.8, -9.5), c + Vector2(-0.9, 1.5), Color(1.0, 0.97, 0.7, a), 1.4, true)
		2:  # Gespräch: Sprechblase
			var body_r := Rect2(c + Vector2(-9.5, -8.5), Vector2(19, 14))
			_rrect(body_r.grow(1.5), 6.0, Color(0.16, 0.07, 0.02, a))
			draw_colored_polygon(PackedVector2Array([c + Vector2(-6, 4), c + Vector2(-1, 4), c + Vector2(-8, 11)]), Color(0.16, 0.07, 0.02, a))
			_rrect(body_r, 5.0, Color(0.98, 0.95, 0.86, a))
			draw_colored_polygon(PackedVector2Array([c + Vector2(-5, 4), c + Vector2(-2, 4), c + Vector2(-6.5, 8.5)]), Color(0.98, 0.95, 0.86, a))
			for k in 3:
				draw_circle(c + Vector2(-4.5 + 4.5 * k, -1.5), 1.4, Color(0.35, 0.2, 0.08, a))


func _wrap(text: String, font: Font, size: int, width: float) -> PackedStringArray:
	var out := PackedStringArray()
	var cur := ""
	for word in text.split(" "):
		var cand := word if cur == "" else cur + " " + word
		if font.get_string_size(cand, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width and cur != "":
			out.append(cur)
			cur = word
		else:
			cur = cand
	if cur != "":
		out.append(cur)
	return out

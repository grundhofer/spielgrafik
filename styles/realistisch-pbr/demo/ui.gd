extends Control
## Oberfläche im Stil heutiger realistischer 3D-Spiele (zurückhaltend, kein Rahmen):
##  - Ortseinblendung zu Beginn: Name in Cormorant Garamond, gesperrt, mit feiner Linie, blendet
##    ein und wieder aus (wie beim Betreten eines Gebiets)
##  - Dialog rechts unten auf einer Milchglasfläche (Bildschirm weichgezeichnet und abgedunkelt,
##    Shader ui_glass.gdshader): Ortsname klein und gesperrt, die Zeile in Source Sans 3, darunter
##    drei Antworten mit Tastensymbol; die zweite wird nach kurzer Zeit ausgewählt.
## Zeit kommt aus main.gd (set_time), keine Zufälle.

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]

const TITLE_IN := Vector2(0.35, 1.15)
const TITLE_OUT := Vector2(2.3, 3.0)
const PANEL := Rect2(800, 448, 444, 252)
const PANEL_IN := Vector2(3.35, 3.85)
const LINE_IN := Vector2(3.6, 4.1)
const CHOICE_T0 := 4.05
const CHOICE_STEP := 0.12
const SELECT_T := 4.75

const TITLE_SHADE := 0.35
const WHITE := Color(0.96, 0.95, 0.92)
const MUTED := Color(0.86, 0.82, 0.76)
const ACCENT := Color(1.0, 0.78, 0.5)

var t := 0.0
var serif := FontVariation.new()
var sans := FontVariation.new()
var sans_semi := FontVariation.new()
var glass: ColorRect
var title_shade := GradientTexture2D.new()


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var cg: FontFile = load("res://fonts/CormorantGaramond.ttf")
	var ss: FontFile = load("res://fonts/SourceSans3.ttf")
	serif.base_font = cg
	serif.variation_opentype = {"wght": 600}
	serif.spacing_glyph = 5
	sans.base_font = ss
	sans.variation_opentype = {"wght": 420}
	sans_semi.base_font = ss
	sans_semi.variation_opentype = {"wght": 620}
	sans_semi.spacing_glyph = 3
	# weicher dunkler Hof hinter der Ortseinblendung (der Abendhimmel dahinter ist hell)
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.55, 1.0])
	g.colors = PackedColorArray([Color(0, 0, 0, TITLE_SHADE), Color(0, 0, 0, TITLE_SHADE * 0.8), Color(0, 0, 0, 0)])
	g.interpolation_mode = Gradient.GRADIENT_INTERPOLATE_CUBIC
	title_shade.gradient = g
	title_shade.fill = GradientTexture2D.FILL_RADIAL
	title_shade.fill_from = Vector2(0.5, 0.5)
	title_shade.fill_to = Vector2(1.0, 0.5)
	title_shade.width = 256
	title_shade.height = 128
	glass = ColorRect.new()
	glass.position = PANEL.position
	glass.size = PANEL.size
	glass.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/ui_glass.gdshader")
	m.set_shader_parameter("size_px", PANEL.size)
	glass.material = m
	glass.show_behind_parent = true
	add_child(glass)


func set_time(v: float) -> void:
	t = v
	var a := _ease(PANEL_IN, t)
	glass.visible = a > 0.0
	(glass.material as ShaderMaterial).set_shader_parameter("alpha", a)
	glass.position = PANEL.position + Vector2(0.0, 14.0 * (1.0 - a))
	queue_redraw()


static func _ease(r: Vector2, x: float) -> float:
	return smoothstep(r.x, r.y, x)


func _draw() -> void:
	_draw_title()
	_draw_dialog()


func _draw_title() -> void:
	# Ortseinblendung oben links (die Mitte gehört dem Leuchtturm), wächst mit feiner Linie aus
	var a := _ease(TITLE_IN, t) * (1.0 - _ease(TITLE_OUT, t))
	if a <= 0.0:
		return
	var size := 46
	var text := LOCATION.to_upper()
	var x := 72.0 + 10.0 * (1.0 - _ease(TITLE_IN, t))
	var y := 92.0
	var w := serif.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x
	var c := Vector2(x + w * 0.5, y - 10.0)
	var half := Vector2(w * 0.5 + 170.0, 82.0)
	draw_texture_rect(title_shade, Rect2(c - half, half * 2.0), false, Color(1, 1, 1, a))
	for o in [Vector2(0, 2), Vector2(0, 3), Vector2(1, 4)]:
		draw_string(serif, Vector2(x, y) + o, text, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(0, 0, 0, 0.25 * a))
	draw_string(serif, Vector2(x, y), text, HORIZONTAL_ALIGNMENT_LEFT, -1, size, Color(WHITE, a))
	var line_len := (w + 40.0) * _ease(Vector2(TITLE_IN.x + 0.15, TITLE_IN.y + 0.45), t)
	var ly := y + 20.0
	var steps := 40
	for i in steps:
		var x0 := line_len * float(i) / steps
		var x1 := line_len * float(i + 1) / steps
		var edge := 1.0 - (x0 + x1) * 0.5 / maxf(line_len, 1.0)
		draw_line(Vector2(x - 2.0 + x0, ly), Vector2(x - 2.0 + x1, ly), Color(ACCENT, 0.9 * a * sqrt(edge)), 1.5)


func _draw_dialog() -> void:
	var a := _ease(PANEL_IN, t)
	if a <= 0.0:
		return
	var off := Vector2(0.0, 14.0 * (1.0 - a))
	var x0 := PANEL.position.x + 26.0
	var y0 := PANEL.position.y + off.y
	# Kopfzeile: Ort, gesperrt, mit Akzentstrich
	draw_rect(Rect2(x0, y0 + 22.0, 3.0, 14.0), Color(ACCENT, a))
	draw_string(sans_semi, Vector2(x0 + 12.0, y0 + 35.0), LOCATION.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(MUTED, 0.95 * a))
	# Zeile
	var la := _ease(LINE_IN, t)
	var line_y := y0 + 66.0
	var lines := _wrap(LINE, sans, 22, PANEL.size.x - 52.0)
	for i in lines.size():
		var p := Vector2(x0, line_y + 28.0 * i)
		draw_string(sans, p + Vector2(0, 1.5), lines[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color(0, 0, 0, 0.35 * la))
		draw_string(sans, p, lines[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color(WHITE, la))
	# Antworten
	var cy := line_y + 28.0 * lines.size() + 14.0
	draw_line(Vector2(x0, cy - 8.0), Vector2(PANEL.end.x - 26.0, cy - 8.0), Color(1, 1, 1, 0.14 * la), 1.0)
	var sel := smoothstep(SELECT_T, SELECT_T + 0.25, t)
	for i in CHOICES.size():
		var ca := smoothstep(CHOICE_T0 + CHOICE_STEP * i, CHOICE_T0 + CHOICE_STEP * i + 0.3, t)
		if ca <= 0.0:
			continue
		var row := Rect2(x0 - 10.0, cy + 33.0 * i - 2.0, PANEL.size.x - 32.0, 30.0)
		var dx := 10.0 * (1.0 - ca)
		if i == 1 and sel > 0.0:
			draw_rect(row, Color(1.0, 0.85, 0.65, 0.14 * sel * ca))
			draw_rect(Rect2(row.position, Vector2(3.0, row.size.y)), Color(ACCENT, sel * ca))
		# Tastensymbol: Quadrat mit abgerundeten Ecken und Ziffer
		var key := Rect2(x0 + dx, row.position.y + 4.0, 22.0, 22.0)
		_round_rect(key, 4.0, Color(1, 1, 1, (0.55 + 0.4 * (sel if i == 1 else 0.0)) * ca), false)
		var num := str(i + 1)
		var nw := sans_semi.get_string_size(num, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
		draw_string(sans_semi, Vector2(key.position.x + 11.0 - nw / 2.0 - 1.0, key.position.y + 16.5), num, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(WHITE, ca))
		var col := WHITE.lerp(Color(1.0, 0.9, 0.75), sel if i == 1 else 0.0)
		draw_string(sans, Vector2(x0 + 34.0 + dx, row.position.y + 21.5), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color(col, ca * (0.92 if i != 1 else 1.0)))


func _round_rect(r: Rect2, rad: float, col: Color, filled: bool) -> void:
	var pts := PackedVector2Array()
	var corners := [Vector2(r.end.x - rad, r.position.y + rad), Vector2(r.end.x - rad, r.end.y - rad),
			Vector2(r.position.x + rad, r.end.y - rad), Vector2(r.position.x + rad, r.position.y + rad)]
	var start := [-PI / 2.0, 0.0, PI / 2.0, PI]
	for c in 4:
		for k in 5:
			var ang: float = start[c] + PI / 2.0 * k / 4.0
			pts.append(corners[c] + Vector2(cos(ang), sin(ang)) * rad)
	if filled:
		draw_colored_polygon(pts, col)
	else:
		pts.append(pts[0])
		draw_polyline(pts, col, 1.2, true)


func _wrap(text: String, font: Font, size: int, width: float) -> PackedStringArray:
	var out := PackedStringArray()
	var cur := ""
	for word in text.split(" "):
		var test := word if cur == "" else cur + " " + word
		if font.get_string_size(test, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width and cur != "":
			out.append(cur)
			cur = word
		else:
			cur = test
	if cur != "":
		out.append(cur)
	return out

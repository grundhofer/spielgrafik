extends CanvasLayer
## Oberfläche: eine Karte aus Aquarellpapier unten rechts (shaders/ui_paper.gdshader), darauf
## Ort, Erzählzeile (Zeichen für Zeichen), drei Auswahlpunkte mit gemalten Farbtupfern, die zweite
## mit einem Pinselstrich hinterlegt, und die Parserzeile. Schrift echt gesetzt (Fraunces, Alegreya),
## nicht gemalt, damit sie scharf und lesbar bleibt. Die Karte liegt über dem gemalten Bild.

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "nimm paket"
const CARD_POS := Vector2(612.0, 556.0)
const CARD_SIZE := Vector2(628.0, 136.0)
const MARGIN := 16.0
const INK := Color(0.20, 0.14, 0.12)
const INK_BLUE := Color(0.17, 0.20, 0.38)
const DOTS := [Color(0.25, 0.42, 0.66), Color(0.78, 0.30, 0.22), Color(0.36, 0.55, 0.32)]

# Zeitplan (s)
const T_CARD := 0.15
const T_TYPE0 := 0.35
const T_TYPE1 := 2.4
const T_CHOICES := 2.8
const T_SELECT := 3.4
const T_PARSER := 4.3
const PARSER_CPS := 9.0

var t := 0.0
var f_title: FontVariation
var f_body: FontVariation
var f_body_b: FontVariation
var f_italic: FontVariation
var bg: ColorRect
var bg_mat: ShaderMaterial
var draw_node: Control


func _font(path: String, axes: Dictionary) -> FontVariation:
	var fv := FontVariation.new()
	fv.base_font = load(path)
	var ts := TextServerManager.get_primary_interface()
	var tags := {}
	for k in axes:
		tags[ts.name_to_tag(k)] = axes[k]
	fv.variation_opentype = tags
	return fv


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.trim_prefix("--t0="))
	f_title = _font("res://fonts/Fraunces-var.ttf", {"wght": 600.0, "opsz": 48.0, "SOFT": 100.0, "WONK": 1.0})
	f_italic = _font("res://fonts/Fraunces-Italic-var.ttf", {"wght": 460.0, "opsz": 24.0, "SOFT": 100.0})
	f_body = _font("res://fonts/Alegreya-wght.ttf", {"wght": 460.0})
	f_body_b = _font("res://fonts/Alegreya-wght.ttf", {"wght": 640.0})

	bg = ColorRect.new()
	bg.position = CARD_POS - Vector2(MARGIN, MARGIN)
	bg.size = CARD_SIZE + Vector2(2.0 * MARGIN, 2.0 * MARGIN)
	bg_mat = ShaderMaterial.new()
	bg_mat.shader = load("res://shaders/ui_paper.gdshader")
	bg_mat.set_shader_parameter("rect_size", CARD_SIZE)
	bg_mat.set_shader_parameter("margin", MARGIN)
	bg.material = bg_mat
	add_child(bg)
	draw_node = Control.new()
	draw_node.position = CARD_POS
	draw_node.size = CARD_SIZE
	draw_node.draw.connect(_draw_card)
	add_child(draw_node)
	_refresh()


func _process(delta: float) -> void:
	t += delta
	_refresh()


func _refresh() -> void:
	var a := smoothstep(T_CARD, T_CARD + 0.4, t)
	bg_mat.set_shader_parameter("opacity", a)
	draw_node.modulate.a = a
	draw_node.queue_redraw()


func _draw_card() -> void:
	var n := draw_node
	# Ort mit Pinselstrich darunter
	var title_pos := Vector2(22.0, 34.0)
	n.draw_string(f_title, title_pos, LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 25, INK_BLUE)
	var tw := f_title.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 25).x
	_brush_line(Vector2(20.0, 43.0), Vector2(22.0 + tw + 6.0, 41.0), 3.2, Color(0.80, 0.52, 0.22, 0.75))

	# Erzählzeile, Zeichen für Zeichen
	var k := clampf((t - T_TYPE0) / (T_TYPE1 - T_TYPE0), 0.0, 1.0)
	var shown := LINE.substr(0, int(round(k * LINE.length())))
	var lines := _wrap(shown, LINE, f_body, 20, 330.0)
	var y := 70.0
	for ln in lines:
		n.draw_string(f_body, Vector2(22.0, y), ln, HORIZONTAL_ALIGNMENT_LEFT, -1, 20, INK)
		y += 24.0

	# Parserzeile
	var pk := clampf((t - T_PARSER) * PARSER_CPS, 0.0, float(PARSER.length()))
	var ptxt := "> " + PARSER.substr(0, int(pk))
	var pp := Vector2(22.0, 122.0)
	n.draw_string(f_italic, pp, ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(INK, 0.85))
	var cw := f_italic.get_string_size(ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x
	if fmod(t, 0.8) < 0.5 or (t > T_PARSER and pk < PARSER.length()):
		n.draw_rect(Rect2(pp.x + cw + 2.0, pp.y - 14.0, 2.0, 17.0), Color(INK, 0.8))

	# Auswahl
	var ca := smoothstep(T_CHOICES, T_CHOICES + 0.4, t)
	var sel := smoothstep(T_SELECT, T_SELECT + 0.35, t)
	var x0 := 392.0
	for i in CHOICES.size():
		var cy := 44.0 + 32.0 * i
		if i == 1 and sel > 0.0:
			# Pinselstrich hinter der gewählten Zeile, von links aufgetragen
			var w := (f_body_b.get_string_size(CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 20).x + 34.0) * sel
			_brush_band(Vector2(x0 - 12.0, cy - 7.0), w, 22.0, Color(0.93, 0.74, 0.50, 0.75 * ca))
		_dot(Vector2(x0, cy - 6.0), 5.5, Color(DOTS[i], ca))
		var col := INK if i != 1 else Color(0.45, 0.16, 0.10)
		n.draw_string(f_body_b if i == 1 else f_body, Vector2(x0 + 16.0, cy), CHOICES[i],
				HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color(col, ca))


## Zeilenumbruch mit der vollen Zeile als Maß, damit Wörter beim Tippen nicht springen
func _wrap(shown: String, full: String, font: Font, size: int, width: float) -> PackedStringArray:
	var out := PackedStringArray()
	var words := full.split(" ")
	var cur := ""
	var breaks: Array[int] = []
	var pos := 0
	for w in words:
		var test := w if cur == "" else cur + " " + w
		if cur != "" and font.get_string_size(test, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width:
			breaks.append(pos)
			cur = w
		else:
			cur = test
		pos += w.length() + 1
	var start := 0
	for b in breaks:
		if shown.length() > start:
			out.append(shown.substr(start, mini(b - 1, shown.length()) - start))
		start = b
	if shown.length() > start:
		out.append(shown.substr(start))
	return out


## Pinselstrich als Polygon mit schwankender Breite und ausgefransten Enden
func _brush_line(p0: Vector2, p1: Vector2, width: float, col: Color) -> void:
	var pts := PackedVector2Array()
	var bottom := PackedVector2Array()
	var steps := 24
	var dir := (p1 - p0).normalized()
	var nrm := Vector2(-dir.y, dir.x)
	for i in steps + 1:
		var u := float(i) / steps
		var p := p0.lerp(p1, u)
		var w := width * (0.35 + 0.65 * sin(PI * pow(u, 0.7))) * (0.85 + 0.15 * sin(u * 23.0))
		pts.append(p + nrm * w * 0.5)
		bottom.append(p - nrm * w * 0.5)
	bottom.reverse()
	pts.append_array(bottom)
	draw_node.draw_colored_polygon(pts, col)


func _brush_band(p: Vector2, w: float, h: float, col: Color) -> void:
	if w < 2.0:
		return
	var pts := PackedVector2Array()
	var bottom := PackedVector2Array()
	var steps := 30
	for i in steps + 1:
		var u := float(i) / steps
		var x := p.x + w * u
		var wob := 1.6 * sin(u * 17.0 + 1.3) + 1.0 * sin(u * 41.0)
		var taper := 0.75 + 0.25 * smoothstep(0.0, 0.1, u) * (1.0 - smoothstep(0.85, 1.0, u))
		pts.append(Vector2(x, p.y - h * 0.5 * taper + wob))
		bottom.append(Vector2(x, p.y + h * 0.5 * taper - wob * 0.7))
	bottom.reverse()
	pts.append_array(bottom)
	draw_node.draw_colored_polygon(pts, col)


## Farbtupfer: unregelmäßiger Kreis mit dunklerem Rand (Pigment am Rand)
func _dot(c: Vector2, r: float, col: Color) -> void:
	var outer := PackedVector2Array()
	var inner := PackedVector2Array()
	for i in 20:
		var a := TAU * i / 20.0
		var rr := r * (1.0 + 0.12 * sin(a * 3.0 + c.y) + 0.06 * sin(a * 7.0))
		outer.append(c + Vector2(cos(a), sin(a)) * rr)
		inner.append(c + Vector2(cos(a), sin(a)) * rr * 0.72)
	draw_node.draw_colored_polygon(outer, col.darkened(0.25))
	draw_node.draw_colored_polygon(inner, col)

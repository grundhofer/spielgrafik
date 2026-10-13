extends Control
## Oberfläche im Low-Poly-Stil: Ortsschild und Dialogkasten sind selbst aus Dreiecken gebaut
## (unregelmäßiges Netz, eine Farbe je Dreieck aus einem Verlauf, wenige Prozent Abweichung), mit
## abgeschrägten Ecken statt Rundungen. Der Kasten setzt sich beim Erscheinen Dreieck für Dreieck von
## links nach rechts zusammen. Schrift: Quicksand (OFL), geometrisch und rund.
## Zeit kommt aus main.gd (t), damit die Aufnahme deterministisch ist.

const LOCATION := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "nimm paket"

const BOX := Rect2(440, 508, 808, 186)     # Dialogkasten (unten rechts, Dachs steht links)
const TAG_POS := Vector2(34, 30)
const CUT := 16.0                          # Abschrägung der Ecken in px
const CELL := 46.0                         # Rastermaß des Dreiecksnetzes

const PANEL_A := Color("2a2554")           # Verlauf des Kastens (links oben -> rechts unten)
const PANEL_B := Color("4a3a78")
const TAG_A := Color("f59a8c")
const TAG_B := Color("ffc89c")
const INK := Color("2b2550")
const CREAM := Color("fff3e6")
const LAVENDER := Color("bcaef0")
const PEACH := Color("ffb68e")
const CHOICE_BG := Color("564a8a")

# Zeitplan (s)
const BOX_T0 := 3.4
const BOX_BUILD := 0.5
const TEXT_T0 := 3.85
const CHARS_PER_S := 95.0
const CHOICE_T0 := 4.4
const PARSER_T0 := 4.5

var font_body: FontVariation
var font_bold: FontVariation
var box_tris: Array = []      # [PackedVector2Array, Color, Vector2 Mitte]
var tag_tris: Array = []
var choice_tris: Array = []   # je Auswahl eine Liste von Dreiecken
var tag_rect: Rect2
var t := 0.0


func _ready() -> void:
	var base := load("res://fonts/Quicksand-wght.ttf") as FontFile
	var ts := TextServerManager.get_primary_interface()
	font_body = FontVariation.new()
	font_body.base_font = base
	font_body.variation_opentype = {ts.name_to_tag("wght"): 600}
	font_bold = FontVariation.new()
	font_bold.base_font = base
	font_bold.variation_opentype = {ts.name_to_tag("wght"): 700}

	var rng := RandomNumberGenerator.new()
	rng.seed = 4711
	box_tris = _facets(BOX, CUT, CELL, PANEL_A, PANEL_B, 1.0, rng)
	var tw := font_bold.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 27).x
	tag_rect = Rect2(TAG_POS, Vector2(tw + 86, 52))
	tag_tris = _facets(tag_rect, 12.0, 30.0, TAG_A, TAG_B, 1.0, rng)
	for i in CHOICES.size():
		choice_tris.append(_facets(_choice_rect(i), 9.0, 34.0, CHOICE_BG, CHOICE_BG.lightened(0.12), 1.0, rng))


func _process(_delta: float) -> void:
	t = (get_tree().current_scene as Node).get("t")
	queue_redraw()


func _choice_rect(i: int) -> Rect2:
	return Rect2(BOX.position.x + 492, BOX.position.y + 22 + i * 50, 292, 42)


## Abgeschrägtes Rechteck als Polygon
static func _chamfer(r: Rect2, c: float) -> PackedVector2Array:
	var a := r.position
	var b := r.end
	return PackedVector2Array([
		Vector2(a.x + c, a.y), Vector2(b.x - c, a.y), Vector2(b.x, a.y + c), Vector2(b.x, b.y - c),
		Vector2(b.x - c, b.y), Vector2(a.x + c, b.y), Vector2(a.x, b.y - c), Vector2(a.x, a.y + c)])


## Unregelmäßiges Dreiecksnetz über r, auf die abgeschrägte Form zugeschnitten; Farbe je Dreieck aus
## dem Verlauf a -> b (nach Lage) mit kleiner Abweichung.
func _facets(r: Rect2, cut: float, cell: float, a: Color, b: Color, alpha: float,
		rng: RandomNumberGenerator) -> Array:
	var nx := maxi(1, int(round(r.size.x / cell)))
	var ny := maxi(1, int(round(r.size.y / cell)))
	var pts := []
	for j in ny + 1:
		var row := []
		for i in nx + 1:
			var p := r.position + Vector2(r.size.x * i / nx, r.size.y * j / ny)
			if i > 0 and i < nx and j > 0 and j < ny:
				p += Vector2(rng.randf_range(-0.3, 0.3) * r.size.x / nx, rng.randf_range(-0.3, 0.3) * r.size.y / ny)
			row.append(p)
		pts.append(row)
	var shape := _chamfer(r, cut)
	var out := []
	for j in ny:
		for i in nx:
			var p00: Vector2 = pts[j][i]
			var p10: Vector2 = pts[j][i + 1]
			var p01: Vector2 = pts[j + 1][i]
			var p11: Vector2 = pts[j + 1][i + 1]
			var tris := [[p00, p10, p11], [p00, p11, p01]] if rng.randf() < 0.5 else [[p00, p10, p01], [p10, p11, p01]]
			for tri in tris:
				var poly := PackedVector2Array(tri)
				for clipped in Geometry2D.intersect_polygons(poly, shape):
					if clipped.size() < 3:
						continue
					var cen := Vector2.ZERO
					for q in clipped:
						cen += q
					cen /= clipped.size()
					var k := clampf(((cen.x - r.position.x) / r.size.x) * 0.7 + ((cen.y - r.position.y) / r.size.y) * 0.3, 0.0, 1.0)
					var col := a.lerp(b, k)
					var jit := rng.randf_range(-0.05, 0.05)
					col = Color(col.r + jit, col.g + jit, col.b + jit * 1.2, alpha)
					out.append([clipped, col, cen])
	return out


func _draw_facets(tris: Array, grow: Callable = Callable()) -> void:
	for tri in tris:
		var poly: PackedVector2Array = tri[0]
		var s := 1.0
		if grow.is_valid():
			s = grow.call(tri[2])
			if s <= 0.0:
				continue
		if s < 1.0:
			var cen: Vector2 = tri[2]
			var scaled := PackedVector2Array()
			for q in poly:
				scaled.append(cen + (q - cen) * s)
			poly = scaled
		draw_colored_polygon(poly, tri[1])


func _draw() -> void:
	if not visible:
		return
	# Ortsschild: von Anfang an, Facetten in Pfirsich, kleines Rautensymbol aus vier Dreiecken
	var ta := smoothstep(0.15, 0.55, t)
	if ta > 0.0:
		var tag_grow := func(c: Vector2) -> float:
			var d := (c.x - tag_rect.position.x) / tag_rect.size.x
			return _ease(clampf((t - 0.15 - d * 0.3) / 0.25, 0.0, 1.0))
		_draw_facets(tag_tris, tag_grow)
		var ic := tag_rect.position + Vector2(30, 26)
		var top := ic + Vector2(0, -12)
		var bot := ic + Vector2(0, 12)
		var lft := ic + Vector2(-10, 0)
		var rgt := ic + Vector2(10, 0)
		var a := Color(INK, ta)
		draw_colored_polygon(PackedVector2Array([top, rgt, ic]), Color(INK.lightened(0.25), ta))
		draw_colored_polygon(PackedVector2Array([top, ic, lft]), a)
		draw_colored_polygon(PackedVector2Array([bot, ic, rgt]), Color(INK.lightened(0.1), ta))
		draw_colored_polygon(PackedVector2Array([bot, lft, ic]), Color(INK.lightened(0.35), ta))
		draw_string(font_bold, tag_rect.position + Vector2(54, 35), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 27,
			Color(INK, ta))

	if t < BOX_T0:
		return
	# Dialogkasten setzt sich von links nach rechts aus Dreiecken zusammen
	var box_grow := func(c: Vector2) -> float:
		var d := (c.x - BOX.position.x) / BOX.size.x
		return _ease(clampf((t - BOX_T0 - d * (BOX_BUILD - 0.2)) / 0.2, 0.0, 1.0))
	_draw_facets(box_tris, box_grow)
	# Akzentkante oben: schmaler Pfirsichstreifen auf der linken Hälfte
	var acc := clampf((t - BOX_T0 - 0.2) / 0.3, 0.0, 1.0)
	if acc > 0.0:
		var x0 := BOX.position.x + CUT
		var x1 := x0 + 120.0 * _ease(acc)
		draw_colored_polygon(PackedVector2Array([Vector2(x0, BOX.position.y), Vector2(x1, BOX.position.y),
			Vector2(x1 - 4, BOX.position.y + 4), Vector2(x0 + 4, BOX.position.y + 4)]), PEACH)

	# Text Zeichen für Zeichen
	var shown := int(maxf(0.0, t - TEXT_T0) * CHARS_PER_S)
	var y := BOX.position.y + 52
	for line in LINES:
		var part: String = line.substr(0, clampi(shown, 0, line.length()))
		draw_string(font_body, Vector2(BOX.position.x + 30, y), part, HORIZONTAL_ALIGNMENT_LEFT, -1, 24, CREAM)
		shown -= line.length()
		y += 36

	# Eingabezeile mit blinkendem Strich
	if t >= TEXT_T0:
		var py := BOX.position.y + BOX.size.y - 28
		var typed := PARSER.substr(0, clampi(int(maxf(0.0, t - PARSER_T0) * 26.0), 0, PARSER.length()))
		var txt := "> " + typed
		draw_string(font_body, Vector2(BOX.position.x + 30, py), txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 22, LAVENDER)
		if fposmod(t, 0.8) < 0.5:
			var cw := font_body.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 22).x
			draw_rect(Rect2(BOX.position.x + 32 + cw, py - 18, 10, 21), LAVENDER)

	# Auswahl: abgeschrägte Facettenknöpfe, der gewählte in Pfirsich mit Dreieckszeiger
	for i in CHOICES.size():
		var ca := clampf((t - CHOICE_T0 - i * 0.08) / 0.18, 0.0, 1.0)
		if ca <= 0.0:
			continue
		var r := _choice_rect(i)
		var dx := (1.0 - _ease(ca)) * 30.0
		var tris: Array = choice_tris[i]
		for tri in tris:
			var poly := PackedVector2Array()
			for q in tri[0]:
				poly.append(q + Vector2(dx, 0))
			var col: Color = tri[1]
			if i == 0:
				col = Color(PEACH.r + (col.r - CHOICE_BG.r) * 0.6, PEACH.g + (col.g - CHOICE_BG.g) * 0.6,
					PEACH.b + (col.b - CHOICE_BG.b) * 0.6)
			draw_colored_polygon(poly, Color(col, ca))
		var tc := INK if i == 0 else CREAM
		draw_string(font_body, Vector2(r.position.x + 38 + dx, r.position.y + 29), CHOICES[i],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 21, Color(tc, ca))
		if i == 0:
			var bob := 3.0 * sin(TAU * 1.6 * t)
			var c := Vector2(r.position.x + 20 + dx + bob, r.position.y + 21)
			draw_colored_polygon(PackedVector2Array([c + Vector2(-6, -8), c + Vector2(7, 0), c + Vector2(-6, 8)]),
				Color(INK, ca))


static func _ease(x: float) -> float:
	return 1.0 - pow(1.0 - x, 3.0)

extends CanvasLayer
## Oberfläche im Stil der HD-2D-Rollenspiele: HD-Schrift statt Pixelschrift, dunkles Nachtblau mit feinem
## Goldrahmen und kleinen Rauten in den Ecken. Ortsname oben links blendet mit einer Zierlinie ein,
## das Textfenster unten rechts schreibt die Zeile Zeichen für Zeichen, darunter Auswahl mit Zeiger und
## Parser-Zeile. Zeit kommt aus main.gd (t), damit die Aufnahme reproduzierbar bleibt.

const TITLE := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "› nimm paket"
const GOLD := Color(0.86, 0.72, 0.42)
const GOLD_DIM := Color(0.62, 0.5, 0.3)
const INK := Color(0.95, 0.92, 0.84)
const BOX := Rect2(612, 520, 640, 178)
const TYPE_T := Vector2(0.9, 2.6)         # Zeile schreibt sich in dieser Zeit
const CHOICE_T := 2.8

var main: Node
var title_lbl: Label
var title_line: Control
var box: Control
var line_lbl: Label
var choice_lbls: Array[Label] = []
var cursor: Control
var parser_lbl: Label
var serif: FontVariation
var serif_caps: FontVariation


func _ready() -> void:
	main = get_parent()
	var garamond: FontFile = load("res://fonts/EBGaramond-wght.ttf")
	var cinzel: FontFile = load("res://fonts/Cinzel-wght.ttf")
	serif = FontVariation.new()
	serif.base_font = garamond
	serif.variation_opentype = {"wght": 500}
	serif_caps = FontVariation.new()
	serif_caps.base_font = cinzel
	serif_caps.variation_opentype = {"wght": 600}

	# Ortsname oben links
	title_lbl = Label.new()
	title_lbl.text = TITLE
	title_lbl.position = Vector2(46, 30)
	title_lbl.add_theme_font_override("font", serif_caps)
	title_lbl.add_theme_font_size_override("font_size", 30)
	title_lbl.add_theme_color_override("font_color", INK)
	title_lbl.add_theme_color_override("font_shadow_color", Color(0.05, 0.04, 0.1, 0.85))
	title_lbl.add_theme_constant_override("shadow_offset_x", 2)
	title_lbl.add_theme_constant_override("shadow_offset_y", 2)
	title_lbl.add_theme_constant_override("shadow_outline_size", 6)
	add_child(title_lbl)
	title_line = Control.new()
	title_line.position = Vector2(40, 74)
	title_line.size = Vector2(380, 12)
	title_line.draw.connect(_draw_title_line)
	add_child(title_line)

	# Textfenster
	box = Control.new()
	box.position = BOX.position
	box.size = BOX.size
	box.draw.connect(_draw_box)
	add_child(box)
	line_lbl = _label(Vector2(30, 16), Vector2(BOX.size.x - 60, 64), 23, INK)
	line_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	line_lbl.text = LINE
	line_lbl.add_theme_constant_override("line_spacing", -2)
	for i in CHOICES.size():
		var l := _label(Vector2(58, 84 + i * 26), Vector2(330, 28), 20, INK)
		l.text = CHOICES[i]
		choice_lbls.append(l)
	parser_lbl = _label(Vector2(410, 136), Vector2(200, 28), 20, GOLD)
	parser_lbl.text = PARSER
	parser_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	cursor = Control.new()
	cursor.size = Vector2(16, 16)
	cursor.draw.connect(_draw_cursor)
	box.add_child(cursor)


func _label(pos: Vector2, sz: Vector2, fs: int, col: Color) -> Label:
	var l := Label.new()
	l.position = pos
	l.size = sz
	l.add_theme_font_override("font", serif)
	l.add_theme_font_size_override("font_size", fs)
	l.add_theme_color_override("font_color", col)
	l.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.6))
	l.add_theme_constant_override("shadow_offset_x", 1)
	l.add_theme_constant_override("shadow_offset_y", 1)
	box.add_child(l)
	return l


func _process(_delta: float) -> void:
	var t: float = main.t
	# Ortsname: Schrift und Zierlinie blenden ein
	var a := smoothstep(0.15, 0.9, t)
	title_lbl.modulate.a = a
	title_line.modulate.a = a
	title_line.queue_redraw()
	# Textfenster: kurz einblenden, Zeile schreibt sich, dann Auswahl
	var b := smoothstep(0.45, 0.8, t)
	box.modulate.a = b
	var n := int(round(LINE.length() * clampf(inverse_lerp(TYPE_T.x, TYPE_T.y, t), 0.0, 1.0)))
	line_lbl.visible_characters = n
	var c := smoothstep(CHOICE_T, CHOICE_T + 0.3, t)
	for l in choice_lbls:
		l.modulate.a = c
	parser_lbl.modulate.a = c
	parser_lbl.text = PARSER + ("▍" if fmod(t, 0.8) < 0.45 else " ")
	# Zeiger auf der zweiten Wahl, wippt leicht
	cursor.position = Vector2(30 + 3.0 * sin(t * 6.0), 84 + 26 + 7)
	cursor.modulate.a = c
	cursor.queue_redraw()
	choice_lbls[1].add_theme_color_override("font_color", GOLD.lightened(0.25))


func _draw_title_line() -> void:
	var w := title_line.size.x
	var y := 6.0
	var reveal := smoothstep(0.3, 1.2, float(main.t))
	var x1 := 6.0 + (w - 30.0) * reveal
	title_line.draw_line(Vector2(6, y), Vector2(x1, y), GOLD, 1.5, true)
	_diamond(title_line, Vector2(6, y), 4.5, GOLD)
	_diamond(title_line, Vector2(x1 + 8, y), 3.0, GOLD_DIM)


func _draw_box() -> void:
	var r := Rect2(Vector2.ZERO, box.size)
	# Hintergrund: Nachtblau, nach unten dunkler, halbdurchsichtig
	var top := Color(0.11, 0.12, 0.25, 0.86)
	var bot := Color(0.04, 0.05, 0.12, 0.92)
	var pts := PackedVector2Array([r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)])
	box.draw_polygon(pts, PackedColorArray([top, top, bot, bot]))
	# Doppelrahmen: außen gold, innen dünn und dunkler
	box.draw_rect(r.grow(-1), GOLD, false, 2.0)
	box.draw_rect(r.grow(-6), GOLD_DIM, false, 1.0)
	for p in [r.position + Vector2(6, 6), Vector2(r.end.x - 6, 6), r.end - Vector2(6, 6), Vector2(6, r.end.y - 6)]:
		_diamond(box, p, 5.0, GOLD)
	# Trennlinie zwischen Zeile und Auswahl
	box.draw_line(Vector2(30, 80), Vector2(r.size.x - 30, 80), Color(GOLD_DIM, 0.6), 1.0)


func _draw_cursor() -> void:
	var p := PackedVector2Array([Vector2(0, 0), Vector2(12, 7), Vector2(0, 14)])
	cursor.draw_colored_polygon(p, GOLD)
	cursor.draw_polyline(PackedVector2Array([p[0], p[1], p[2], p[0]]), Color(0.3, 0.22, 0.1), 1.0, true)


func _diamond(ci: CanvasItem, c: Vector2, s: float, col: Color) -> void:
	ci.draw_colored_polygon(PackedVector2Array([c + Vector2(0, -s), c + Vector2(s, 0), c + Vector2(0, s),
		c + Vector2(-s, 0)]), col)

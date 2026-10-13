extends Control
## Textoberfläche aus Knete: eine ausgerollte, cremefarbene Platte (clay_ui.gdshader) mit einem
## terrakottafarbenen Namensschild für den Ort, Auswahl mit kleinen Knetkugeln als Nummern und der
## Eingabezeile. Schrift Fredoka (rund, wie aus Knetwürsten gelegt; OFL). Die Eingabe tippt und der
## Cursor blinkt auf Zweien wie die Figur (Bildindex kommt von main.gd).

const INK := Color("3b2618")
const CREAM := Color("f6ead2")
const SLAB := Color("eadcbf")
const TAB := Color("c9643f")
const BALLS := [Color("e2b13c"), Color("d2453a"), Color("4d8f9a")]

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const SELECTED := 1

const PANEL := Rect2(700, 494, 556, 208)    # sichtbare Platte (ohne Schattenrand)
const MARGIN := 22.0
const TYPE_T := 1.2                          # Eingabe beginnt zu tippen
const TYPE_RATE := 7.5                       # Zeichen je Sekunde (je zweites Animationsbild eines)
const SELECT_T := 2.4                        # Auswahl 2 wird eingedrückt

const UI_SHADER := preload("res://shaders/clay_ui.gdshader")

var t := 0.0
var step := 0
var body: FontVariation
var bold: FontVariation
var parser_label: Label
var cursor: ColorRect
var sel_slab: ColorRect


func _ready() -> void:
	var base := load("res://fonts/Fredoka-var.ttf") as FontFile
	var ts := TextServerManager.get_primary_interface()
	body = FontVariation.new()
	body.base_font = base
	body.variation_opentype = {ts.name_to_tag("wght"): 500}
	bold = FontVariation.new()
	bold.base_font = base
	bold.variation_opentype = {ts.name_to_tag("wght"): 620}

	_slab(PANEL, SLAB, 1.0, 26.0, false, false)
	# Ausgewählte Zeile: flache Mulde in der Platte
	sel_slab = _slab(Rect2(PANEL.position.x + 22, PANEL.position.y + 102 + 30 * SELECTED - 3, 300, 30), SLAB, 4.0, 14.0, false, true)
	sel_slab.visible = false
	# Namensschild
	var tab := Rect2(PANEL.position.x + 20, PANEL.position.y - 22, 236, 44)
	var tab_slab := _slab(tab, TAB, 2.0, 18.0, false, false)
	(tab_slab.material as ShaderMaterial).set_shader_parameter("prints_amt", 0.35)
	_label(LOCATION, Vector2(tab.position.x + 16, tab.position.y + 6), 22, CREAM, bold, tab.size.x - 20)
	# Zeile
	_label(LINE, Vector2(PANEL.position.x + 26, PANEL.position.y + 32), 21, INK, body, PANEL.size.x - 52)
	# Auswahl
	for i in CHOICES.size():
		var y := PANEL.position.y + 104 + 30 * i
		var ball := Rect2(PANEL.position.x + 28, y, 24, 24)
		_slab(ball, BALLS[i], 7.0 + i, 12.0, true, false)
		_label(str(i + 1), Vector2(ball.position.x + 7, ball.position.y - 1), 17, CREAM, bold, 20)
		_label(CHOICES[i], Vector2(ball.position.x + 36, y - 3), 20, INK, body, 400)
	# Eingabe
	parser_label = _label("", Vector2(PANEL.position.x + 380, PANEL.position.y + 164), 20, INK, bold, 160)
	cursor = ColorRect.new()
	cursor.color = INK
	cursor.size = Vector2(10, 20)
	add_child(cursor)


func _slab(r: Rect2, col: Color, slab_seed: float, radius: float, circle: bool, pressed: bool) -> ColorRect:
	var cr := ColorRect.new()
	cr.position = r.position - Vector2(MARGIN, MARGIN)
	cr.size = r.size + Vector2(2 * MARGIN, 2 * MARGIN)
	cr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var m := ShaderMaterial.new()
	m.shader = UI_SHADER
	m.set_shader_parameter("size", cr.size)
	m.set_shader_parameter("margin", MARGIN)
	m.set_shader_parameter("radius", radius)
	m.set_shader_parameter("base", col)
	m.set_shader_parameter("seed", slab_seed)
	m.set_shader_parameter("circle", circle)
	m.set_shader_parameter("pressed", pressed)
	if r.size.y < 60.0:
		m.set_shader_parameter("speck_amt", 0.0)
	if circle or pressed:
		m.set_shader_parameter("bevel", 7.0)
		m.set_shader_parameter("wobble", 1.0)
		m.set_shader_parameter("shadow_off", Vector2(2, 3))
		m.set_shader_parameter("shadow_blur", 5.0)
		m.set_shader_parameter("prints_amt", 0.3)
	if pressed:
		m.set_shader_parameter("shadow_alpha", 0.0)
		m.set_shader_parameter("base", col.darkened(0.08))
	cr.material = m
	add_child(cr)
	return cr


func _label(text: String, pos: Vector2, size: int, col: Color, font: Font, width: float) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	l.size = Vector2(width, size * 1.5)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.add_theme_constant_override("line_spacing", -2)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(l)
	return l


func set_time(time: float, fig_step: int) -> void:
	t = time
	step = fig_step
	var ts := float(step) / 15.0
	var n := clampi(int(floor((ts - TYPE_T) * TYPE_RATE)), 0, PARSER.length())
	parser_label.text = PARSER.substr(0, n)
	var w := bold.get_string_size(parser_label.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 20).x
	cursor.position = parser_label.position + Vector2(w + 3, 5)
	cursor.visible = (n < PARSER.length()) or (int(floor(ts / 0.4)) % 2 == 0)
	sel_slab.visible = ts >= SELECT_T

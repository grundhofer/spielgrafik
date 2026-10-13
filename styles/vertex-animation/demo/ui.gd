extends CanvasLayer
## Oberfläche: Textbox mit ui_text aus data/motif.json und ein kleines Technikfenster, das die beiden
## Vertex-Animation-Texturen zeigt (Zeile = Bild, Spalte = Punkt) samt der gerade abgespielten Zeile.

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const INK := Color("f1e9da")
const DIM := Color("b9b2a6")
const ACCENT := Color("f0a54a")
const PANEL := Color(0.055, 0.075, 0.105, 0.82)
const EDGE := Color(1, 1, 1, 0.14)

const VAT_VIEW := """
shader_type canvas_item;
// Versatz (m) als Farbe: 0 = mittleres Grau, ± skaliert
uniform float gain = 0.55;
void fragment() {
	vec3 v = texture(TEXTURE, UV).rgb;
	COLOR = vec4(clamp(v * gain + 0.5, 0.0, 1.0), 1.0);
}
"""

var sans: FontVariation
var sans_bold: FontVariation
var mono: FontVariation
var flag_head: ColorRect
var gull_heads: Array[ColorRect] = []
var flag_rect: TextureRect
var gull_rect: TextureRect
var cursor: Label
var blink_t := 0.0


func _ready() -> void:
	var ss := load("res://fonts/SourceSans3.ttf") as FontFile
	sans = FontVariation.new()
	sans.base_font = ss
	sans.variation_opentype = {"wght": 430}
	sans_bold = FontVariation.new()
	sans_bold.base_font = ss
	sans_bold.variation_opentype = {"wght": 650}
	var jb := load("res://fonts/JetBrainsMono-wght.ttf") as FontFile
	mono = FontVariation.new()
	mono.base_font = jb
	mono.variation_opentype = {"wght": 480}
	_build_textbox()
	_build_vat_panel()


func _panel(pos: Vector2, size: Vector2) -> Panel:
	var p := Panel.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = PANEL
	sb.border_color = EDGE
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(10)
	sb.shadow_color = Color(0, 0, 0, 0.35)
	sb.shadow_size = 10
	p.add_theme_stylebox_override("panel", sb)
	p.position = pos
	p.size = size
	add_child(p)
	return p


func _label(parent: Control, text: String, font: Font, size: int, color: Color, pos: Vector2, w := 0.0) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.position = pos
	if w > 0.0:
		l.size.x = w
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	parent.add_child(l)
	return l


func _build_textbox() -> void:
	var p := _panel(Vector2(684, 540), Vector2(572, 158))
	var bar := ColorRect.new()
	bar.color = ACCENT
	bar.position = Vector2(22, 20)
	bar.size = Vector2(3, 15)
	p.add_child(bar)
	var loc := _label(p, LOCATION.to_upper(), sans_bold, 14, ACCENT, Vector2(34, 16))
	loc.add_theme_constant_override("outline_size", 0)
	_label(p, LINE, sans, 21, INK, Vector2(22, 40), 528)
	var x := 22.0
	for i in CHOICES.size():
		var chip := Panel.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(1, 1, 1, 0.06) if i != 1 else Color(0.94, 0.65, 0.29, 0.18)
		sb.border_color = Color(1, 1, 1, 0.12) if i != 1 else Color(0.94, 0.65, 0.29, 0.6)
		sb.set_border_width_all(1)
		sb.set_corner_radius_all(6)
		chip.add_theme_stylebox_override("panel", sb)
		var txt := "%d  %s" % [i + 1, CHOICES[i]]
		var w := sans.get_string_size(txt, HORIZONTAL_ALIGNMENT_LEFT, -1, 16).x + 20
		chip.position = Vector2(x, 94)
		chip.size = Vector2(w, 26)
		p.add_child(chip)
		_label(chip, txt, sans, 16, INK if i == 1 else DIM, Vector2(10, 2))
		x += w + 8
	_label(p, PARSER, mono, 15, ACCENT, Vector2(22, 128))
	cursor = _label(p, "▌", mono, 15, ACCENT, Vector2(22 + mono.get_string_size(PARSER + " ", HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x, 128))


func _vat_view(parent: Control, path: String, pos: Vector2, size: Vector2, gain: float) -> TextureRect:
	var tr := TextureRect.new()
	tr.texture = load(path) as Texture2D
	tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	tr.stretch_mode = TextureRect.STRETCH_SCALE
	tr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	tr.position = pos
	tr.size = size
	var m := ShaderMaterial.new()
	var sh := Shader.new()
	sh.code = VAT_VIEW
	m.shader = sh
	m.set_shader_parameter("gain", gain)
	tr.material = m
	parent.add_child(tr)
	var frame := ReferenceRect.new()
	frame.border_color = Color(1, 1, 1, 0.25)
	frame.editor_only = false
	frame.position = pos - Vector2(1, 1)
	frame.size = size + Vector2(2, 2)
	parent.add_child(frame)
	return tr


func _build_vat_panel() -> void:
	var p := _panel(Vector2(20, 20), Vector2(372, 236))
	_label(p, "Vertex-Animation-Texturen", sans_bold, 17, INK, Vector2(16, 9))
	_label(p, "Zeile = Bild  ·  Spalte = Punkt  ·  RGBA16F", mono, 11, DIM, Vector2(16, 33))
	flag_rect = _vat_view(p, "res://vat/flag_pos.exr", Vector2(16, 56), Vector2(340, 64), 0.6)
	flag_head = ColorRect.new()
	flag_head.color = ACCENT
	flag_head.size = Vector2(344, 2)
	flag_rect.add_child(flag_head)
	_label(p, "Fahne  Stoffsimulation  651 × 120", mono, 11, DIM, Vector2(16, 123))
	gull_rect = _vat_view(p, "res://vat/gull_pos.exr", Vector2(16, 148), Vector2(274, 48), 1.3)
	for i in 11:
		var h := ColorRect.new()
		h.color = ACCENT
		h.size = Vector2(6, 2)
		gull_rect.add_child(h)
		gull_heads.append(h)
	_label(p, "Möwe  Flügelschlag  137 × 24", mono, 11, DIM, Vector2(16, 199))
	_label(p, "11 Möwen, 1 Textur, eigene Phase", mono, 11, DIM, Vector2(16, 214))
	var note := _label(p, "Meer:\nGerstner\nim Vertex-\nShader", mono, 11, DIM, Vector2(298, 148))
	note.add_theme_constant_override("line_spacing", -1)


## flag: abgespielte Zeile der Fahne (0..1), gull: je Möwe (0..1)
func set_rows(flag: float, gull: Array[float]) -> void:
	if flag_head:
		flag_head.position = Vector2(-2, floor(flag * flag_rect.size.y))
	for i in mini(gull.size(), gull_heads.size()):
		gull_heads[i].position = Vector2(-8 + 0.0 * i, floor(gull[i] * gull_rect.size.y))
		gull_heads[i].size = Vector2(6, 2)
	blink_t += 1.0 / 30.0
	if cursor:
		cursor.visible = fmod(blink_t, 1.0) < 0.6

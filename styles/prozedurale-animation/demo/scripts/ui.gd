extends CanvasLayer
## Oberfläche: Textleiste unten (ui_text aus data/motif.json) und Einblendung „Bewegung nur aus Code“:
## ein SubViewport, der dieselbe 2D-Welt zeigt (world_2d geteilt), mit Abdunkelung und Röntgenlinien,
## die nur dort gezeichnet werden (canvas_cull_mask / visibility_layer 2).

var ui: Dictionary
var regular: FontFile
var mono: FontFile
var loc: Label
var line: Label
var parser: Label
var caret: ColorRect
var choice_nodes: Array[Control] = []
var inset_vp: SubViewport
var inset_info: RichTextLabel
var badger: Node2D
var parser_font: Font
var show_inset := true
var text_line := ""


func fv(w: int, spacing := 0) -> FontVariation:
	var f := FontVariation.new()
	f.base_font = regular
	f.variation_opentype = {TextServerManager.get_primary_interface().name_to_tag("wght"): w}
	f.spacing_glyph = spacing
	return f


func _label(text: String, font: Font, size: int, col: Color, pos: Vector2, parent: Node = null) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	(parent if parent else self).add_child(l)
	return l


func _box(pos: Vector2, size: Vector2, bg: Color, border: Color, bw: int, radius: int, shadow := 0) -> Panel:
	var p := Panel.new()
	p.position = pos
	p.size = size
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.set_border_width_all(bw)
	sb.set_corner_radius_all(radius)
	sb.anti_aliasing = true
	if shadow > 0:
		sb.shadow_color = Color(0, 0, 0, 0.35)
		sb.shadow_size = shadow
		sb.shadow_offset = Vector2(0, 3)
	p.add_theme_stylebox_override("panel", sb)
	add_child(p)
	return p


func setup(ui_text: Dictionary, badger_ref: Node2D, world: World2D, with_inset: bool) -> void:
	ui = ui_text
	badger = badger_ref
	show_inset = with_inset
	regular = load("res://fonts/Baloo2-wght.ttf")
	mono = load("res://fonts/JetBrainsMono-wght.ttf")
	text_line = String(ui["line"])
	# Textleiste
	_box(Vector2(16, 598), Vector2(1248, 110), Color(0.97, 0.93, 0.84, 0.97), Color(0.25, 0.15, 0.10), 3, 16, 6)
	loc = _label(String(ui["location"]).to_upper(), fv(800, 1), 16, Color(0.66, 0.23, 0.15), Vector2(38, 607))
	line = _label(text_line, fv(600), 24, Color(0.20, 0.13, 0.10), Vector2(38, 628))
	parser_font = fv(500)
	parser = _label(String(ui["parser_prompt"]), parser_font, 20, Color(0.40, 0.31, 0.26), Vector2(38, 668))
	caret = ColorRect.new()
	caret.color = Color(0.40, 0.31, 0.26)
	caret.size = Vector2(10, 3)
	add_child(caret)
	var div := ColorRect.new()
	div.color = Color(0.25, 0.15, 0.10, 0.22)
	div.position = Vector2(866, 614)
	div.size = Vector2(2, 78)
	add_child(div)
	var choices: Array = ui["choices"]
	for i in choices.size():
		var holder := Control.new()
		holder.position = Vector2(888, 612 + 28 * i)
		add_child(holder)
		var badge := Panel.new()
		badge.size = Vector2(22, 22)
		badge.position = Vector2(0, 3)
		var sb := StyleBoxFlat.new()
		sb.bg_color = Color(0.66, 0.23, 0.15)
		sb.set_corner_radius_all(11)
		sb.anti_aliasing = true
		badge.add_theme_stylebox_override("panel", sb)
		holder.add_child(badge)
		var num := _label(str(i + 1), fv(800), 15, Color(1, 0.97, 0.9), Vector2(0, 2), holder)
		num.size = Vector2(22, 22)
		num.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_label(String(choices[i]), fv(600), 20, Color(0.22, 0.14, 0.10), Vector2(32, -2), holder)
		choice_nodes.append(holder)
	if show_inset:
		_build_inset(world)


## Einblendung im freien Himmel zwischen Laterne und Leuchtfeuer (x 486–816, y 12–248), damit Pfostenkopf,
## Ausleger und Haken der Laterne (ab y ≈ 258) frei bleiben.
const INSET_X := 486.0


func _build_inset(world: World2D) -> void:
	_box(Vector2(INSET_X, 12), Vector2(330, 236), Color(0.07, 0.08, 0.12, 0.90), Color(0.62, 0.55, 0.44, 0.9), 2, 12, 4)
	_label("Bewegung nur aus Code", fv(700), 17, Color(0.98, 0.92, 0.80), Vector2(INSET_X + 16, 14))
	var cont := SubViewportContainer.new()
	cont.position = Vector2(INSET_X + 10, 42)
	cont.size = Vector2(310, 156)
	cont.stretch = true
	add_child(cont)
	inset_vp = SubViewport.new()
	inset_vp.size = Vector2i(310, 156)
	inset_vp.world_2d = world
	inset_vp.canvas_cull_mask = 1 | 2
	inset_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	cont.add_child(inset_vp)
	inset_info = RichTextLabel.new()
	inset_info.bbcode_enabled = true
	inset_info.position = Vector2(INSET_X + 16, 201)
	inset_info.size = Vector2(310, 44)
	inset_info.scroll_active = false
	inset_info.add_theme_font_override("normal_font", mono)
	inset_info.add_theme_font_size_override("normal_font_size", 12)
	inset_info.add_theme_color_override("default_color", Color(0.80, 0.82, 0.88))
	add_child(inset_info)


func update(t: float) -> void:
	line.visible_characters = clampi(int((t - 0.15) * 40.0), 0, text_line.length())
	for i in choice_nodes.size():
		choice_nodes[i].modulate.a = smoothstep(1.7 + 0.1 * i, 2.1 + 0.1 * i, t)
	var pt: String = parser.text
	var n := clampi(int((t - 1.88) * 16.0), 0, pt.length())
	parser.visible_characters = n
	var w := parser_font.get_string_size(pt.substr(0, n), HORIZONTAL_ALIGNMENT_LEFT, -1, 20).x
	caret.position = parser.position + Vector2(w + 3, 24)
	var typing := t > 1.88 and n < pt.length()
	caret.visible = t > 1.9 and (typing or fmod(t, 0.9) < 0.55)
	if show_inset:
		var b = badger
		var hs: Vector2 = b.position + Vector2(b.hip.x, 0) * b.DS
		var z := 0.76
		var c := Vector2(hs.x - 14.0, b.position.y - 88.0)
		inset_vp.canvas_transform = Transform2D(0.0, Vector2(z, z), 0.0, Vector2(155, 80) - c * z)
		var sq: float = (float(b.sy) - 1.0) * 100.0
		var tilt_deg: float = rad_to_deg(float(b.tilt))
		inset_info.text = "[color=#ffa04a]IK-Beine[/color] · [color=#ff6b80]Schal[/color]/[color=#73e0ff]Riemen[/color]: Verlet 120 Hz\nSchritt %d  Stauchung %s %%  Neigung %s°" % [
			b.n_steps, _de(sq), _de(tilt_deg)]


func _de(x: float) -> String:
	var s := "%+.1f" % x
	return s.replace(".", ",").replace("-", "−")

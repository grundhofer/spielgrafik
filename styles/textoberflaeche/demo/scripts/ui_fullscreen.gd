extends Control
## Form 4: Vollbild-Gemälde mit halbtransparentem Textpanel unten und Inventar-Icons. Der Text blendet weich
## Zeichen für Zeichen ein; der Mauszeiger nimmt das Paket vom Kai, es fliegt in die Tasche.

const RevealFX := preload("res://scripts/reveal_fx.gd")

const PANEL := Rect2(10, 268, 620, 82)
const TEXT_POS := Vector2(26, 296)
const TEXT_W := 392.0
const SLOT0 := Vector2(440, 294)
const SLOT := 38.0
const SLOT_GAP := 7.0
const ICON := 30.0
const LINE := "Die Laterne flackert im Wind.\nAm Kai wartet ein Paket auf dich."
const ITEMS := ["", "key", "letter", "compass"]

const TEXT_T := 0.35
const PTR_IN := 2.75
const PTR_MOVE := [2.85, 3.4]
const HOVER_T := 3.42
const CLICK_T := 3.95
const FLY := [4.02, 4.6]
const TOAST := [4.62, 5.75]

const CREAM := Color(0.95, 0.92, 0.85)
const AMBER := Color(0.93, 0.72, 0.42)

var t := 0.0
var cfg: Dictionary
var crop: Vector2
var fx := RevealFX.new()
var text: RichTextLabel
var slots: Array[Panel] = []
var slot_icons: Array[TextureRect] = []
var flash: Panel
var fly: Sprite2D
var pointer: Node2D
var tooltip: PanelContainer
var toast: PanelContainer
var harbor: Node2D
var ptr_start := Vector2(452, 150)


func _ready() -> void:
	cfg = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	crop = Vector2(cfg.crops.fullscreen[0], cfg.crops.fullscreen[1])
	harbor = $Picture/Harbor
	harbor.position = -crop
	var serif_sans: Font = load("res://fonts/AlegreyaSans-Medium.ttf")
	var sc := FontVariation.new()
	sc.base_font = load("res://fonts/AlegreyaSC-Medium.ttf")
	sc.spacing_glyph = 2

	var panel := Panel.new()
	panel.position = PANEL.position
	panel.size = PANEL.size
	panel.add_theme_stylebox_override("panel", _box(Color(0.05, 0.06, 0.09, 0.80), Color(0.95, 0.85, 0.65, 0.30), 8))
	add_child(panel)

	var loc := Label.new()
	loc.text = "Hafen von Lornholm"
	loc.add_theme_font_override("font", sc)
	loc.add_theme_font_size_override("font_size", 14)
	loc.add_theme_color_override("font_color", AMBER)
	loc.position = Vector2(26, 274)
	add_child(loc)

	fx.start = TEXT_T
	text = RichTextLabel.new()
	text.bbcode_enabled = true
	text.scroll_active = false
	text.fit_content = true
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.position = TEXT_POS
	text.size = Vector2(TEXT_W, 40)
	text.add_theme_font_override("normal_font", serif_sans)
	text.add_theme_font_size_override("normal_font_size", 17)
	text.add_theme_color_override("default_color", CREAM)
	text.add_theme_constant_override("line_separation", 1)
	text.install_effect(fx)
	text.text = "[reveal]" + LINE + "[/reveal]"
	text.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(text)

	var bag := Label.new()
	bag.text = "Tasche"
	bag.add_theme_font_override("font", sc)
	bag.add_theme_font_size_override("font_size", 12)
	bag.add_theme_color_override("font_color", Color(0.95, 0.88, 0.75, 0.55))
	bag.position = Vector2(SLOT0.x, 273)
	add_child(bag)
	for i in ITEMS.size():
		var s := Panel.new()
		s.position = SLOT0 + Vector2(i * (SLOT + SLOT_GAP), 0)
		s.size = Vector2(SLOT, SLOT)
		s.add_theme_stylebox_override("panel", _box(Color(0.95, 0.88, 0.75, 0.13), Color(0.95, 0.85, 0.65, 0.28), 6))
		add_child(s)
		slots.append(s)
		var ic := TextureRect.new()
		ic.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		ic.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		ic.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		ic.size = Vector2(ICON, ICON)
		ic.position = s.position + Vector2((SLOT - ICON) / 2.0, (SLOT - ICON) / 2.0)
		if ITEMS[i] != "":
			ic.texture = load("res://art/icons/%s.png" % ITEMS[i])
		add_child(ic)
		slot_icons.append(ic)
	flash = Panel.new()
	flash.add_theme_stylebox_override("panel", _box(Color(1.0, 0.85, 0.55, 0.0), Color(1.0, 0.85, 0.55, 0.9), 7, 2))
	flash.size = Vector2(SLOT + 6, SLOT + 6)
	flash.position = SLOT0 - Vector2(3, 3)
	flash.modulate.a = 0.0
	add_child(flash)

	fly = Sprite2D.new()
	fly.texture = load("res://art/icons/parcel.png")
	fly.visible = false
	fly.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	add_child(fly)

	tooltip = _pill("Paket", 13, sc)
	toast = _pill("Paket aufgenommen", 14, sc)
	pointer = _make_pointer()
	_update()


func _box(bg: Color, border: Color, radius: int, bw: int = 1) -> StyleBoxFlat:
	var sb := StyleBoxFlat.new()
	sb.bg_color = bg
	sb.border_color = border
	sb.border_width_left = bw
	sb.border_width_right = bw
	sb.border_width_top = bw
	sb.border_width_bottom = bw
	sb.corner_radius_top_left = radius
	sb.corner_radius_top_right = radius
	sb.corner_radius_bottom_left = radius
	sb.corner_radius_bottom_right = radius
	sb.anti_aliasing = true
	return sb


func _pill(s: String, size: int, font: Font) -> PanelContainer:
	var p := PanelContainer.new()
	var sb := _box(Color(0.05, 0.06, 0.09, 0.85), Color(0.95, 0.85, 0.65, 0.35), 5)
	sb.content_margin_left = 8
	sb.content_margin_right = 8
	sb.content_margin_top = 2
	sb.content_margin_bottom = 3
	p.add_theme_stylebox_override("panel", sb)
	var l := Label.new()
	l.text = s
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", CREAM)
	p.add_child(l)
	p.modulate.a = 0.0
	add_child(p)
	return p


func _make_pointer() -> Node2D:
	var n := Node2D.new()
	var pts := PackedVector2Array([Vector2(0, 0), Vector2(0, 16), Vector2(4, 12.5), Vector2(7, 19),
			Vector2(9.5, 18), Vector2(6.6, 11.5), Vector2(11.5, 11.5)])
	var poly := Polygon2D.new()
	poly.polygon = pts
	poly.color = Color(0.98, 0.96, 0.9)
	poly.antialiased = true
	n.add_child(poly)
	var line := Line2D.new()
	var closed := pts.duplicate()
	closed.append(pts[0])
	line.points = closed
	line.width = 1.2
	line.default_color = Color(0.08, 0.07, 0.07)
	line.joint_mode = Line2D.LINE_JOINT_ROUND
	line.antialiased = true
	n.add_child(line)
	n.modulate.a = 0.0
	add_child(n)
	return n


func _process(delta: float) -> void:
	t += delta
	_update()


func ease_io(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func _update() -> void:
	fx.t = t
	var world_parcel := Vector2(cfg.parcel.pos[0], cfg.parcel.pos[1]) - crop - Vector2(0, cfg.parcel.size * 0.45)
	var slot_c := SLOT0 + Vector2(SLOT / 2.0, SLOT / 2.0)
	# Zeiger: einblenden, zum Paket gleiten, klicken, danach ausblenden
	var target := world_parcel + Vector2(3, 2)
	var u := ease_io((t - PTR_MOVE[0]) / (PTR_MOVE[1] - PTR_MOVE[0]))
	var p := ptr_start.lerp(target, u)
	if t > FLY[1]:
		p += Vector2(0, -6.0 * ease_io((t - FLY[1]) / 0.4))
	pointer.position = p.round()
	pointer.modulate.a = clampf((t - PTR_IN) / 0.2, 0.0, 1.0) * (1.0 - clampf((t - 5.0) / 0.3, 0.0, 1.0))
	var press := 1.0 - clampf(absf(t - CLICK_T - 0.05) / 0.07, 0.0, 1.0)
	pointer.scale = Vector2.ONE * (1.0 - 0.15 * press)
	# Hover: Paket hellt auf, Hinweis „Paket“ erscheint
	var hov := clampf((t - HOVER_T) / 0.12, 0.0, 1.0) * (1.0 - clampf((t - CLICK_T) / 0.1, 0.0, 1.0))
	tooltip.modulate.a = hov
	tooltip.position = (p + Vector2(14, -22)).round()
	var parcel: Sprite2D = harbor.parcel
	var pshadow: Sprite2D = harbor.parcel_shadow
	if parcel:
		parcel.modulate = Color(1, 1, 1).lerp(Color(1.35, 1.28, 1.12), hov)
		parcel.visible = t < FLY[0]
		pshadow.visible = t < FLY[0]
	# Flug in die Tasche: Bogen, dabei wächst das Paket auf Icon-Größe
	var tex_w := float(fly.texture.get_width())
	if t >= FLY[0] and t < FLY[1]:
		var f := ease_io((t - FLY[0]) / (FLY[1] - FLY[0]))
		var a := world_parcel
		var c := (a + slot_c) / 2.0 + Vector2(0, -70)
		var q := a.lerp(c, f).lerp(c.lerp(slot_c, f), f)
		fly.visible = true
		fly.position = q
		var size := lerpf(float(cfg.parcel.size) * 1.1, ICON * 1.15, f)
		fly.scale = Vector2.ONE * size / tex_w
		fly.rotation = sin(f * PI) * -0.35
	else:
		fly.visible = false
	slot_icons[0].texture = load("res://art/icons/parcel.png") if t >= FLY[1] else null
	var fl := clampf((t - FLY[1]) / 0.06, 0.0, 1.0) * (1.0 - clampf((t - FLY[1] - 0.1) / 0.5, 0.0, 1.0))
	flash.modulate.a = fl
	# Meldung über dem Panel
	var ta := clampf((t - TOAST[0]) / 0.2, 0.0, 1.0) * (1.0 - clampf((t - TOAST[1]) / 0.25, 0.0, 1.0))
	toast.modulate.a = ta
	toast.position = Vector2(round(slot_c.x + 2.0 * (SLOT + SLOT_GAP) - toast.size.x / 2.0 - 30.0), round(240.0 - 4.0 * ta))

extends RefCounted
## Oberfläche wie in einem Raum-Fluchtspiel der Browserspiel-Ära, ganz in Bühnenkoordinaten:
## Leiste unten mit Textzeile und Inventar (Icons als Vektorformen), Ortsname, Tonknopf,
## Pfeile zum Weitergehen, Hinweisschild am Mauszeiger, Pfeil- und Hand-Mauszeiger.

const V = preload("res://vec.gd")

const PANEL_Y := 331.0
const SLOT := 36.0
const SLOT_Y := 357.0
const SLOTS := 7
const CREAM := Color("fff3d6")
const YELLOW := Color("ffd257")

var font_body: FontVariation
var font_bold: FontVariation
var slots: Array = []        # Node2D je Feld (Mittelpunkt)
var nav: Array = []
var cursor: Node2D
var arrow: Node2D
var hand: Node2D
var ring: Node2D
var tips: Dictionary = {}     # Text -> Node2D (Schild, Ursprung = Spitze am Zeiger)
var line_label: Label
var oversampling := 2.0


static func C(hex: String) -> Color:
	return Color(hex)


func _font(weight: int) -> FontVariation:
	var base: FontFile = load("res://fonts/Baloo2-wght.ttf")
	base.oversampling = oversampling   # Schrift steht in der um 1,8 vergrößerten Bühne
	var fv := FontVariation.new()
	fv.base_font = base
	var tag := TextServerManager.get_primary_interface().name_to_tag("wght")
	fv.variation_opentype = {tag: weight}
	return fv


func slot_center(i: int) -> Vector2:
	return Vector2(14.0 + SLOT * 0.5 + i * (SLOT + 6.0), SLOT_Y + SLOT * 0.5)


func build(stage: Node2D, ui_text: Dictionary) -> void:
	font_body = _font(500)
	font_bold = _font(800)
	var g := V.group(stage, "UI")
	# Pfeile links/rechts (weitergehen)
	for spec in [[Vector2(14, 236), -1.0], [Vector2(536, 236), 1.0]]:
		var n := V.group(g, "Nav", spec[0])
		var s: float = spec[1]
		var pts := V.rpoly([Vector2(-6 * s, -12), Vector2(7 * s, 0), Vector2(-6 * s, 12), Vector2(-3 * s, 0)], [2.0, 2.5, 2.0, 1.0], 4)
		V.fill(n, pts, Color(1, 1, 1, 0.82))
		V.fill(n, V.rpoly([Vector2(-5 * s, -9), Vector2(3 * s, -1.5), Vector2(-2.6 * s, -1.5)], 1.0, 3), Color(1, 1, 1, 0.9))
		V.ink(n, pts, 1.6, 0.5)
		nav.append(n)
	# Leiste unten
	var panel := V.rpoly([Vector2(3, PANEL_Y), Vector2(547, PANEL_Y), Vector2(547, 398), Vector2(3, 398)], 9.0, 6)
	V.fill(g, panel, {"lin": [[0.0, C("34406a")], [0.5, C("252e50")], [1.0, C("171c33")]], "from": Vector2(0, PANEL_Y), "to": Vector2(0, 398)})
	V.fill(g, V.rpoly([Vector2(8, PANEL_Y + 3), Vector2(542, PANEL_Y + 3), Vector2(542, PANEL_Y + 10), Vector2(8, PANEL_Y + 10)], 4.0, 4), Color(1, 1, 1, 0.10))
	V.ink(g, panel, 2.6, 0.55)
	# Textzeile
	var strip := V.rpoly([Vector2(12, PANEL_Y + 6), Vector2(538, PANEL_Y + 6), Vector2(538, PANEL_Y + 23), Vector2(12, PANEL_Y + 23)], 5.0, 4)
	V.fill(g, strip, C("10142a"))
	V.ink(g, strip, 1.1, 0.7)
	line_label = _label(g, ui_text["line"], font_body, 10.0, CREAM, Vector2(18, PANEL_Y + 5.6), Vector2(514, 17))
	# Inventar
	for i in SLOTS:
		var c := slot_center(i)
		var box := V.rpoly([c + Vector2(-SLOT / 2, -SLOT / 2), c + Vector2(SLOT / 2, -SLOT / 2), c + Vector2(SLOT / 2, SLOT / 2), c + Vector2(-SLOT / 2, SLOT / 2)], 6.0, 5)
		V.fill(g, box, {"lin": [[0.0, C("1b2140")], [0.35, C("2c3762")], [1.0, C("3c4a7c")]], "from": c + Vector2(0, -SLOT / 2), "to": c + Vector2(0, SLOT / 2)})
		V.ink(g, box, 1.5, 0.6)
		var sg := V.group(g, "Slot%d" % i, c)
		slots.append(sg)
	_icon_key(slots[0])
	_icon_letter(slots[1])
	_icon_compass(slots[2])
	_icon_map(slots[3])
	# Ortsname und Tonknopf
	var loc := _label(g, ui_text["location"], font_bold, 14.0, YELLOW, Vector2(318, SLOT_Y + 3), Vector2(186, 24))
	loc.add_theme_color_override("font_outline_color", V.INK)
	loc.add_theme_constant_override("outline_size", 4)
	loc.add_theme_color_override("font_shadow_color", Color(0, 0, 0, 0.45))
	loc.add_theme_constant_override("shadow_offset_x", 0)
	loc.add_theme_constant_override("shadow_offset_y", 1)
	var btn := V.group(g, "SoundButton", Vector2(524, SLOT_Y + 18))
	var circ := V.ellipse(Vector2.ZERO, 11, 11, 32)
	V.fill(btn, circ, {"rad": [[0.0, C("ffd77a")], [0.7, C("f0a030")], [1.0, C("c87818")]], "c": Vector2(-3, -4), "r": Vector2(15, 15)})
	V.fill(btn, V.smooth([Vector2(-8, -3), Vector2(-5, -8), Vector2(0, -9.4), Vector2(5, -8), Vector2(8, -3), Vector2(0, -5)], true, 5), Color(1, 1, 1, 0.45))
	V.ink(btn, circ, 1.6, 0.5)
	var spk := PackedVector2Array([Vector2(-5.5, -2), Vector2(-3, -2), Vector2(0.5, -5), Vector2(0.5, 5), Vector2(-3, 2), Vector2(-5.5, 2)])
	V.fill(btn, spk, V.INK)
	V.stroke(btn, V.smooth([Vector2(2.5, -3), Vector2(4, 0), Vector2(2.5, 3)], false, 5), 1.1, 0.2, 0.2, 0.3)
	V.stroke(btn, V.smooth([Vector2(4.5, -5.2), Vector2(7, 0), Vector2(4.5, 5.2)], false, 5), 1.1, 0.2, 0.2, 0.3)
	# Hinweisschilder (Auswahl aus ui_text als Klickpunkt-Beschriftung)
	ring = V.group(stage, "ClickRing")
	V.ink(ring, V.ellipse(Vector2.ZERO, 10, 10, 36), 1.8, 0.8, [], Color(1, 1, 1, 0.95))
	ring.visible = false
	cursor = V.group(stage, "Cursor")
	_cursor_shapes()


func make_tip(stage: Node2D, text: String, off := Vector2(14, -24)) -> Node2D:
	var tip := V.group(stage, "Tip")
	var w := font_bold.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, 9).x + 14.0
	var h := 17.0
	if off.x < 0.0:
		off.x -= w
	var x0 := off.x
	var y0 := off.y
	var box := V.rpoly([Vector2(x0, y0), Vector2(x0 + w, y0), Vector2(x0 + w, y0 + h), Vector2(x0, y0 + h)], 5.0, 4)
	V.fill(tip, V.xform(box, Transform2D(0, Vector2(1.5, 1.8))), Color(0.08, 0.04, 0.12, 0.35))
	V.fill(tip, box, {"lin": [[0.0, C("fffbe8")], [1.0, C("ffe9a8")]], "from": Vector2(0, y0), "to": Vector2(0, y0 + h)})
	V.ink(tip, box, 1.3, 0.55)
	var lab := _label(tip, text, font_bold, 9.0, C("3a2414"), Vector2(x0 + 7, y0 + 0.2), Vector2(w - 12, h - 3))
	lab.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	tip.visible = false
	tips[text] = tip
	return tip


func _label(parent: Node, text: String, f: Font, size: float, col: Color, pos: Vector2, sz: Vector2) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	l.size = sz
	l.add_theme_font_override("font", f)
	l.add_theme_font_size_override("font_size", int(round(size)))
	l.add_theme_color_override("font_color", col)
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(l)
	return l


func _cursor_shapes() -> void:
	arrow = V.group(cursor, "Arrow")
	var ap := PackedVector2Array([Vector2(0, 0), Vector2(0, 15.5), Vector2(3.8, 12), Vector2(6.6, 18), Vector2(9.4, 16.8), Vector2(6.8, 11.2), Vector2(11.6, 11.2)])
	V.fill(arrow, V.xform(ap, Transform2D(0, Vector2(1.2, 1.6))), Color(0, 0, 0, 0.3))
	V.fill(arrow, ap, Color.WHITE)
	V.ink(arrow, ap, 1.3, 0.8)
	hand = V.group(cursor, "Hand")
	var hp := V.smooth([Vector2(-2.4, 1.0), Vector2(0, -0.6), Vector2(2.4, 1.0), Vector2(2.5, 8.0), Vector2(4.4, 7.2), Vector2(6.2, 8.2),
		Vector2(7.8, 8.6), Vector2(9.4, 9.6), Vector2(10.8, 11.2), Vector2(11.4, 13.4), Vector2(10.6, 17.4), Vector2(8.4, 20.2),
		Vector2(1.6, 20.2), Vector2(-1.0, 18.0), Vector2(-5.8, 13.4), Vector2(-5.6, 11.2), Vector2(-3.8, 10.8), Vector2(-2.4, 12.0)], true, 5)
	V.fill(hand, V.xform(hp, Transform2D(0, Vector2(1.2, 1.6))), Color(0, 0, 0, 0.3))
	V.fill(hand, hp, Color.WHITE)
	V.fill(hand, V.smooth([Vector2(8.6, 12.4), Vector2(10.4, 13.6), Vector2(9.8, 17.2), Vector2(7.8, 19.4), Vector2(4, 19.6), Vector2(8, 17)], true, 4), C("cfd3e0"))
	V.ink(hand, hp, 1.3, 0.8)
	for ln in [[Vector2(2.6, 9.6), Vector2(2.7, 13.0)], [Vector2(6.3, 9.0), Vector2(6.4, 13.2)], [Vector2(9.0, 10.4), Vector2(9.2, 14.0)]]:
		V.stroke(hand, PackedVector2Array(ln), 0.9, 0.2, 0.5, 0.1)
	V.stroke(hand, PackedVector2Array([Vector2(1.2, 20.2), Vector2(9.0, 20.2)]), 0.9, 0.2, 0.2, 0.3)
	var cuff := V.rpoly([Vector2(1.0, 20.0), Vector2(9.2, 20.0), Vector2(9.0, 23.5), Vector2(1.2, 23.5)], 1.0)
	V.shape(hand, cuff, Color.WHITE, 1.1)
	hand.visible = false


# ------------------------------------------------------------------ Inventar-Icons (Ursprung = Feldmitte)
func _icon_key(g: Node2D) -> void:
	var ring_o := V.ellipse(Vector2(-8, -7), 6.5, 6.5, 24)
	var shaft := V.rpoly([Vector2(-4, -3), Vector2(11, 8), Vector2(9.2, 10.4), Vector2(-6, -1)], 1.2)
	var bit := V.rpoly([Vector2(5, 4), Vector2(9, 1), Vector2(11.5, 4.5), Vector2(7.6, 7.5)], 0.8)
	for p in [shaft, bit, ring_o]:
		V.fill(g, p, C("e2b23c"))
	V.fill(g, V.ellipse(Vector2(-8, -7), 2.8, 2.8, 16), C("2c3762"))
	V.fill(g, V.smooth([Vector2(-12, -9), Vector2(-9, -12), Vector2(-6, -12.4), Vector2(-9.4, -10.4)], true, 4), C("fff2b0"))
	V.ink(g, shaft, 1.2, 0.5)
	V.ink(g, bit, 1.2, 0.5)
	V.ink(g, ring_o, 1.3, 0.5)
	V.ink(g, V.ellipse(Vector2(-8, -7), 2.8, 2.8, 16), 0.9, 0.6)


func _icon_letter(g: Node2D) -> void:
	var env := V.rpoly([Vector2(-12, -8), Vector2(12, -8), Vector2(12, 9), Vector2(-12, 9)], 1.5)
	V.fill(g, env, C("f4ecd8"))
	V.fill(g, PackedVector2Array([Vector2(-12, 9), Vector2(0, 0), Vector2(12, 9)]), C("ddd0b2"))
	V.stroke(g, PackedVector2Array([Vector2(-11, -7), Vector2(0, 2), Vector2(11, -7)]), 1.1, 0.1, 0.1, 0.4)
	V.ink(g, env, 1.3, 0.5)
	var seal := V.ellipse(Vector2(0, 2), 3.6, 3.4, 16)
	V.shape(g, seal, C("c8323a"), 1.0)
	V.fill(g, V.ellipse(Vector2(-1, 1), 1.0, 0.8, 8), C("f08088"))


func _icon_compass(g: Node2D) -> void:
	var case := V.ellipse(Vector2(0, 1), 12, 12, 32)
	V.fill(g, case, C("d39a32"))
	var face := V.ellipse(Vector2(0, 1), 9, 9, 28)
	V.fill(g, face, C("f6f0e0"))
	V.fill(g, PackedVector2Array([Vector2(0, -7), Vector2(2.4, 1), Vector2(-2.4, 1)]), C("d3343c"))
	V.fill(g, PackedVector2Array([Vector2(0, 9), Vector2(2.4, 1), Vector2(-2.4, 1)]), C("3b3a48"))
	V.fill(g, V.ellipse(Vector2(0, 1), 1.2, 1.2, 8), V.INK)
	V.shape(g, V.rpoly([Vector2(-2.5, -15), Vector2(2.5, -15), Vector2(2.5, -11), Vector2(-2.5, -11)], 1.0), C("d39a32"), 1.0)
	V.fill(g, V.smooth([Vector2(-8, -4), Vector2(-5, -8), Vector2(-1, -9.5), Vector2(-5, -6)], true, 4), Color(1, 1, 1, 0.8))
	V.ink(g, face, 0.9, 0.6)
	V.ink(g, case, 1.4, 0.5)


func _icon_map(g: Node2D) -> void:
	var paper := V.rpoly([Vector2(-11, -8), Vector2(10, -10), Vector2(11, 8), Vector2(-10, 10)], 1.5)
	V.fill(g, paper, C("e9d6a6"))
	V.stroke(g, V.smooth([Vector2(-7, 5), Vector2(-3, 0), Vector2(1, 2), Vector2(6, -4)], false, 5), 1.0, 0.1, 0.1, 0.8, C("b0503a"))
	V.stroke(g, PackedVector2Array([Vector2(4, -6), Vector2(8, -2)]), 1.2, 0.0, 0.0, 1.0, C("c8323a"))
	V.stroke(g, PackedVector2Array([Vector2(8, -6), Vector2(4, -2)]), 1.2, 0.0, 0.0, 1.0, C("c8323a"))
	V.ink(g, paper, 1.3, 0.5)
	for y in [-9.0, 9.0]:
		var roll := V.capsule(Vector2(-12, y), Vector2(12, y - 2), 2.4)
		V.shape(g, roll, C("c9a46a"), 1.1)


func icon_parcel(g: Node2D) -> void:
	var box := V.rpoly([Vector2(-12, -8), Vector2(12, -8), Vector2(12, 8), Vector2(-12, 8)], 2.0)
	V.fill(g, box, C("c99a5c"))
	V.fill(g, PackedVector2Array([Vector2(5, -7), Vector2(11, -7), Vector2(11, 7), Vector2(5, 7)]), C("a5773f"))
	V.stroke(g, PackedVector2Array([Vector2(-1, -7.5), Vector2(-1, 7.5)]), 1.3, 0.0, 0.0, 1.0, C("f3e5c2"))
	V.stroke(g, PackedVector2Array([Vector2(-11.5, 0), Vector2(11.5, 0)]), 1.3, 0.0, 0.0, 1.0, C("f3e5c2"))
	V.ink(g, box, 1.5, 0.45)

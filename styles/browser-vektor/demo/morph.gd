extends RefCounted
## Form-Tween wie im Vektor-Animationsprogramm: zwei Schlüsselformen mit gleicher Punktzahl,
## dazwischen wird jeder Kontrollpunkt linear verschoben und die Kontur neu berechnet.

const V = preload("res://vec.gd")

var a: Array          # Kontrollpunkte Schlüsselform A
var b: Array          # Kontrollpunkte Schlüsselform B
var closed := true
var smooth_seg := 6
var fill_pg: Polygon2D
var ink_pg: Polygon2D
var w := 1.4
var lo := 0.45
var stroke_mode := false   # offener Strich mit spitzen Enden statt Fläche + Kontur
var ta := 0.4
var tb := 0.4


static func make_shape(parent: Node, ka: Array, kb: Array, paint, width := 1.4, seg := 6):
	var m = load("res://morph.gd").new()
	m.a = ka
	m.b = kb
	m.w = width
	m.smooth_seg = seg
	m.fill_pg = V.fill(parent, V.smooth(ka, true, seg), paint)
	if width > 0.0:
		m.ink_pg = V.ink(parent, V.smooth(ka, true, seg), width)
	return m


static func make_stroke(parent: Node, ka: Array, kb: Array, width: float, col: Color, seg := 6, t_a := 0.4, t_b := 0.4):
	var m = load("res://morph.gd").new()
	m.a = ka
	m.b = kb
	m.w = width
	m.closed = false
	m.stroke_mode = true
	m.smooth_seg = seg
	m.ta = t_a
	m.tb = t_b
	m.ink_pg = V.stroke(parent, V.smooth(ka, false, seg), width, t_a, t_b, 0.0, col)
	return m


func set_t(t: float) -> void:
	var pts := []
	for i in a.size():
		pts.append((a[i] as Vector2).lerp(b[i], t))
	var poly := V.smooth(pts, closed, smooth_seg)
	if stroke_mode:
		V.ribbon_into(ink_pg, poly, V.stroke_widths(poly, w, ta, tb, 0.0), false)
		return
	fill_pg.polygon = poly
	if ink_pg:
		V.ribbon_into(ink_pg, poly, V.outline_widths(poly, w, lo), true)

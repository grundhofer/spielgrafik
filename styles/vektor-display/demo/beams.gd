extends Node2D
## Zeichnet die Anzeigeliste eines Bildes als Strahlbänder (ein Dreiecksfeld pro Bild).
## Jede Strecke: ein Mittelstück und zwei runde Enden. An Polylinien-Enden leuchtet das Ende voll
## (der Strahl verweilt beim Ein- und Ausschalten), an inneren Knicken nur schwach (Kappenfaktor).

var points := PackedVector2Array()
var colors := PackedColorArray()
var uvs := PackedVector2Array()
var indices := PackedInt32Array()
var segment_count := 0


func clear() -> void:
	points.clear()
	colors.clear()
	uvs.clear()
	indices.clear()
	segment_count = 0


func _quad(a: Vector2, b: Vector2, c: Vector2, d: Vector2,
		ua: Vector2, ub: Vector2, uc: Vector2, ud: Vector2, col: Color) -> void:
	var base := points.size()
	points.append(a); points.append(b); points.append(c); points.append(d)
	uvs.append(ua); uvs.append(ub); uvs.append(uc); uvs.append(ud)
	colors.append(col); colors.append(col); colors.append(col); colors.append(col)
	indices.append(base); indices.append(base + 1); indices.append(base + 2)
	indices.append(base); indices.append(base + 2); indices.append(base + 3)


func point(p: Vector2, col: Color, r: float) -> void:
	_quad(p + Vector2(-r, -r), p + Vector2(r, -r), p + Vector2(r, r), p + Vector2(-r, r),
		Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1), col)


func segment(a: Vector2, b: Vector2, col: Color, r: float, cap_a: float, cap_b: float) -> void:
	var v := b - a
	var l := v.length()
	if l < 0.05:
		point(a, col * maxf(cap_a, cap_b), r)
		return
	var u := v / l
	var n := Vector2(-u.y, u.x) * r
	var ur := u * r
	segment_count += 1
	_quad(a - n, b - n, b + n, a + n, Vector2(-1, 0), Vector2(-1, 0), Vector2(1, 0), Vector2(1, 0), col)
	if cap_a > 0.0:
		_quad(a - ur - n, a - n, a + n, a - ur + n, Vector2(-1, 1), Vector2(-1, 0), Vector2(1, 0), Vector2(1, 1), col * cap_a)
	if cap_b > 0.0:
		_quad(b - n, b + ur - n, b + ur + n, b + n, Vector2(-1, 0), Vector2(-1, 1), Vector2(1, 1), Vector2(1, 0), col * cap_b)


## Polylinie: end_cap gilt an den freien Enden, joint_cap an inneren Ecken (je Seite).
func polyline(pts: PackedVector2Array, col: Color, r: float, closed := false, end_cap := 1.0, joint_cap := 0.4) -> void:
	var n := pts.size()
	if n == 0:
		return
	if n == 1:
		point(pts[0], col * end_cap, r)
		return
	var segs := n if closed else n - 1
	for i in segs:
		var a := pts[i]
		var b := pts[(i + 1) % n]
		var ca := joint_cap if (closed or i > 0) else end_cap
		var cb := joint_cap if (closed or i < segs - 1) else end_cap
		segment(a, b, col, r, ca, cb)


func _draw() -> void:
	if points.is_empty():
		return
	RenderingServer.canvas_item_add_triangle_array(get_canvas_item(), indices, points, colors, uvs)

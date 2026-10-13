extends Node2D
## Röntgenblick für die Einblendung: zeichnet Körperrahmen, Neigungsachse, Bein-IK, Verlet-Ketten,
## Rückenkapsel und Fahrtwind. Sichtbar nur im SubViewport (visibility_layer 2).

var b: Node2D
const YEL := Color(1.0, 0.84, 0.30)
const ORA := Color(1.0, 0.56, 0.22)
const PIN := Color(1.0, 0.42, 0.50)
const CYA := Color(0.45, 0.88, 1.0)
const GRN := Color(0.45, 1.0, 0.55)
const WHT := Color(0.95, 0.95, 1.0)


func _draw() -> void:
	var xf: Transform2D = b.body_xf()
	var org: Vector2 = b.v2(b.R["body_tex_origin"]) - b.pivot
	var sz: Vector2 = b.v2(b.R["sizes"]["body"])
	var box := PackedVector2Array()
	for c in [org, org + Vector2(sz.x, 0), org + sz, org + Vector2(0, sz.y), org]:
		box.append(xf * c)
	draw_polyline(box, Color(YEL, 0.8), 2.4, true)
	draw_line(xf * Vector2.ZERO, xf * Vector2(0, -175), Color(YEL, 0.9), 2.4, true)
	draw_circle(xf * Vector2.ZERO, 4.2, YEL)
	# Rückenkapsel (Kollision für Schal und Tasche)
	var ca: Vector2 = b.cap_a
	var cb: Vector2 = b.cap_b
	var r: float = b.cap_r
	var nrm := (cb - ca).normalized().orthogonal()
	draw_arc(ca, r, 0, TAU, 40, Color(CYA, 0.28), 1.6, true)
	draw_arc(cb, r, 0, TAU, 40, Color(CYA, 0.28), 1.6, true)
	draw_line(ca + nrm * r, cb + nrm * r, Color(CYA, 0.28), 1.6, true)
	draw_line(ca - nrm * r, cb - nrm * r, Color(CYA, 0.28), 1.6, true)
	# Beine: Hüfte - Knie - Knöchel (IK), Fuß, Standpunkt
	for f in b.feet:
		var col := ORA if f.name == "near" else Color(ORA, 0.6)
		draw_polyline(PackedVector2Array([f.H, f.K, f.A]), col, 3.4, true)
		draw_line(f.A, f.A + (b.toe_off as Vector2).rotated(f.phi), col, 3.0, true)
		for p in [f.H, f.K, f.A]:
			draw_circle(p, 3.6, col)
		var g := Vector2(f.pos.x if not f.swing else f.target.x, f.ground)
		if f.swing:
			draw_arc(g, 4.4, 0, TAU, 16, WHT, 2.0, true)
		else:
			draw_rect(Rect2(g - Vector2(4.4, 4.4), Vector2(8.8, 8.8)), GRN)
	# Verlet-Ketten
	_chain(b.scarf.p, PIN)
	_chain(b.strap.p, CYA)
	# Fahrtwind am Schal: Luft relativ zum Körper
	var rel: Vector2 = (b.air - Vector2(b.body_v(b.t), 0)) * 0.22
	var s0: Vector2 = b.scarf.p[0] + Vector2(-6, -16)
	if rel.length() > 4.0:
		draw_line(s0, s0 + rel, WHT, 2.4, true)
		var hd := rel.normalized()
		draw_colored_polygon(PackedVector2Array([s0 + rel + hd * 7.0, s0 + rel + hd.orthogonal() * 4.5, s0 + rel - hd.orthogonal() * 4.5]), WHT)


func _chain(p: PackedVector2Array, col: Color) -> void:
	draw_polyline(p, Color(col, 0.9), 2.6, true)
	for i in p.size():
		draw_circle(p[i], 3.2 if i > 0 else 4.2, col)

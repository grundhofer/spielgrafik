extends RefCounted
## Handgezeichnete Striche für alles, was Godot selbst zeichnet.
##
## Ein Strich wird auf etwa 4-px-Schritte neu abgetastet, quer zur Laufrichtung leicht verbogen (Zufallsversatz
## alle ~22 px, dazwischen weich), und seine Deckung schwankt wie der Druck einer Hand; die Enden laufen aus.
## Der Zufall hängt nur vom übergebenen Seed ab: Gleicher Seed = gleicher Strich. Für den Line-Boil wird der Seed
## je Fassung (0..2) geändert, so wechselt jeder Strich wie die Zeichnung zwischen drei leicht verschiedenen Fassungen.


static func _resample(pts: PackedVector2Array, step: float) -> PackedVector2Array:
	var out := PackedVector2Array()
	if pts.size() < 2:
		return pts
	var total := 0.0
	for i in range(1, pts.size()):
		total += pts[i].distance_to(pts[i - 1])
	var n := maxi(2, int(ceil(total / step)) + 1)
	var seg := 1
	var acc := 0.0
	var seg_len := pts[1].distance_to(pts[0])
	for k in n:
		var d := total * float(k) / float(n - 1)
		while seg < pts.size() - 1 and acc + seg_len < d:
			acc += seg_len
			seg += 1
			seg_len = pts[seg].distance_to(pts[seg - 1])
		var f := 0.0 if seg_len < 1e-4 else clampf((d - acc) / seg_len, 0.0, 1.0)
		out.append(pts[seg - 1].lerp(pts[seg], f))
	return out


## Zeichnet einen Bleistiftstrich durch pts. wobble = größter Querversatz in px, fade = Abnahme der Deckung zum Ende.
static func stroke(ci: CanvasItem, pts: PackedVector2Array, col: Color, width: float, sd: int,
		wobble := 0.8, taper := 0.12, fade := 0.0) -> void:
	var res := _resample(pts, 4.0)
	var n := res.size()
	if n < 2:
		return
	var rng := RandomNumberGenerator.new()
	rng.seed = sd
	var total := 0.0
	for i in range(1, n):
		total += res[i].distance_to(res[i - 1])
	var kn := maxi(2, int(ceil(total / 22.0)) + 1)
	var knots := PackedFloat32Array()
	for k in kn:
		knots.append(rng.randf_range(-wobble, wobble))
	var ph := rng.randf() * TAU
	var out := PackedVector2Array()
	var cols := PackedColorArray()
	for i in n:
		var u := float(i) / float(n - 1)
		var dir := (res[mini(i + 1, n - 1)] - res[maxi(i - 1, 0)]).normalized()
		var nrm := Vector2(-dir.y, dir.x)
		var kf := u * float(kn - 1)
		var k0 := mini(int(floor(kf)), kn - 1)
		var k1 := mini(k0 + 1, kn - 1)
		var off := lerpf(knots[k0], knots[k1], smoothstep(0.0, 1.0, kf - float(k0)))
		out.append(res[i] + nrm * off)
		var a := col.a * (0.82 + 0.18 * sin(u * total / 9.0 + ph))
		if taper > 0.0:
			a *= clampf(minf(u, 1.0 - u) / taper * 0.65 + 0.35, 0.35, 1.0)
		a *= 1.0 - fade * u
		cols.append(Color(col, a))
	ci.draw_polyline_colors(out, cols, width, true)


## Gerade Linie von a nach b.
static func line(ci: CanvasItem, a: Vector2, b: Vector2, col: Color, width: float, sd: int, wobble := 0.8) -> void:
	stroke(ci, PackedVector2Array([a, b]), col, width, sd, wobble)

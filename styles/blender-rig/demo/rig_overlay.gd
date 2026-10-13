extends Control
## Zeichnet die 21 Knochen des Dachses als Oktaeder wie Blender (Anzeige "Octahedral", "In Front"):
## Kopf, Spitze und ein Querring bei 10 % der Länge (Radius 13 % der Länge, etwas kräftiger als Blender);
## gefüllte Umrisse, Kanten, Gelenkpunkte. Projektion mit Camera3D.unproject_position, Reihenfolge von hinten nach vorn.
## Farben nach Körperseite: Mitte gelb, links (.L) cyan, rechts (.R) rosa, Schal und Schwanz grün.

const COL_MID := Color(1.0, 0.80, 0.28)
const COL_L := Color(0.30, 0.82, 1.0)
const COL_R := Color(1.0, 0.42, 0.72)
const COL_SOFT := Color(0.50, 0.95, 0.52)
const COL_ROOT := Color(0.80, 0.80, 0.84)
const RING_AT := 0.1
const RING_R := 0.13

var bones := []        # je Knochen: {"name", "z", "head", "tail", "ring": PackedVector2Array(4), "col"}
var amount := 0.0


func set_frame(frames: Array, cam: Camera3D, a: float) -> void:
	amount = a
	bones.clear()
	if a <= 0.001:
		queue_redraw()
		return
	for f in frames:
		var h: Vector3 = f["head"]
		var tl: Vector3 = f["tail"]
		var d := tl - h
		var p: Vector3 = f["perp"]
		var q := d.normalized().cross(p).normalized()
		var c := h + d * RING_AT
		var r := d.length() * RING_R
		var ring := PackedVector2Array()
		for k in [p, q, -p, -q]:
			ring.append(cam.unproject_position(c + k * r))
		var z := cam.global_transform.affine_inverse() * (h + d * 0.5)
		bones.append({
			"name": f["name"], "z": z.z,
			"head": cam.unproject_position(h), "tail": cam.unproject_position(tl),
			"ring": ring, "col": _color(f["name"]),
		})
	# von hinten nach vorn: kleinere (negativere) z liegen weiter weg
	bones.sort_custom(func(a1, b1): return a1["z"] < b1["z"])
	queue_redraw()


func _color(n: String) -> Color:
	if n == "root":
		return COL_ROOT
	if n.begins_with("scarf") or n == "tail":
		return COL_SOFT
	if n.ends_with(".L"):
		return COL_L
	if n.ends_with(".R"):
		return COL_R
	return COL_MID


func _draw() -> void:
	if amount <= 0.001:
		return
	var a := amount
	for b in bones:
		var col: Color = b["col"]
		var hd: Vector2 = b["head"]
		var tl: Vector2 = b["tail"]
		var ring: PackedVector2Array = b["ring"]
		var pts := PackedVector2Array([hd, tl])
		pts.append_array(ring)
		var hull := Geometry2D.convex_hull(pts)   # geschlossen: letzter Punkt = erster
		var dark := col.darkened(0.55)
		if hull.size() >= 4:
			draw_colored_polygon(hull.slice(0, hull.size() - 1), Color(col, 0.42 * a))
			draw_polyline(hull, Color(dark, 0.95 * a), 2.2, true)
		# Kanten des Oktaeders: Ring, Kopf -> Ring, Ring -> Spitze
		for k in 4:
			var r0 := ring[k]
			var r1 := ring[(k + 1) % 4]
			draw_line(r0, r1, Color(col.lightened(0.35), 0.9 * a), 1.2, true)
			draw_line(hd, r0, Color(col.lightened(0.35), 0.9 * a), 1.2, true)
			draw_line(r0, tl, Color(col.lightened(0.15), 0.75 * a), 1.0, true)
		# Gelenkpunkte
		var rad := clampf(hd.distance_to(tl) * 0.07, 2.2, 4.5)
		for p in [hd, tl]:
			draw_circle(p, rad + 1.2, Color(dark, 0.95 * a), true, -1.0, true)
			draw_circle(p, rad, Color(col.lightened(0.5), a), true, -1.0, true)

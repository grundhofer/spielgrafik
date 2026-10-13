extends RefCounted
## Kleine Vektor-Bibliothek im Stil der Browser-Cartoonspiele (2000–2012).
## Alles ist Polygon2D: Füllungen (flach, linearer oder radialer Verlauf) und Konturen als
## gefüllte Bänder mit veränderlicher Breite – so wie das Pinselwerkzeug der damaligen
## Vektorprogramme Striche als Füllflächen speicherte (dick in der Mitte, spitze Enden).

const INK := Color("1a1320")          # Konturfarbe (fast schwarz, leicht violett)
const SHADOW_DIR := Vector2(0.45, 0.89)   # Licht von oben links: Schattenseite unten rechts

static var stats := {"fills": 0, "strokes": 0, "points": 0, "gradients": 0}


# ------------------------------------------------------------------ Formen

## Polygon mit gerundeten Ecken (quadratische Bézier je Ecke). r: Zahl oder Array je Punkt.
static func rpoly(pts: Array, r = 4.0, seg := 5) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := pts.size()
	for i in n:
		var p0: Vector2 = pts[(i - 1 + n) % n]
		var p1: Vector2 = pts[i]
		var p2: Vector2 = pts[(i + 1) % n]
		var ri: float = float(r[i]) if r is Array else float(r)
		if ri <= 0.0:
			out.append(p1)
			continue
		var d0 := p0 - p1
		var d2 := p2 - p1
		var rr := minf(ri, minf(d0.length(), d2.length()) * 0.5)
		var a := p1 + d0.normalized() * rr
		var b := p1 + d2.normalized() * rr
		for k in seg + 1:
			var t := float(k) / seg
			out.append(a.lerp(p1, t).lerp(p1.lerp(b, t), t))
	return out


## Glatte Kurve durch die Punkte (Catmull-Rom). Ein doppelt angegebener Punkt ergibt eine Ecke.
static func smooth(pts: Array, closed := true, seg := 8) -> PackedVector2Array:
	var out := PackedVector2Array()
	var n := pts.size()
	var m := n if closed else n - 1
	for i in m:
		var p1: Vector2 = pts[i]
		var p2: Vector2 = pts[(i + 1) % n]
		var p0: Vector2 = pts[(i - 1 + n) % n] if (closed or i > 0) else p1
		var p3: Vector2 = pts[(i + 2) % n] if (closed or i + 2 < n) else p2
		if p1.is_equal_approx(p2):
			continue
		for k in seg:
			out.append(p1.cubic_interpolate(p2, p0, p3, float(k) / seg))
	if not closed:
		out.append(pts[n - 1])
	return out


static func ellipse(c: Vector2, rx: float, ry: float, n := 32, rot := 0.0) -> PackedVector2Array:
	var out := PackedVector2Array()
	for i in n:
		var a := TAU * i / n
		out.append(c + Vector2(cos(a) * rx, sin(a) * ry).rotated(rot))
	return out


## Kapsel (Strecke a–b mit runden Enden), z. B. für Arme und Beine der Puppe.
static func capsule(a: Vector2, b: Vector2, ra: float, rb := -1.0, n := 10) -> PackedVector2Array:
	if rb < 0.0:
		rb = ra
	var d := (b - a).normalized()
	var ang := d.angle()
	var out := PackedVector2Array()
	for i in n + 1:
		var t := ang - PI / 2 + PI * i / n
		out.append(b + Vector2(cos(t), sin(t)) * rb)
	for i in n + 1:
		var t := ang + PI / 2 + PI * i / n
		out.append(a + Vector2(cos(t), sin(t)) * ra)
	return out


static func xform(pts: PackedVector2Array, t: Transform2D) -> PackedVector2Array:
	return t * pts


static func signed_area(pts: PackedVector2Array) -> float:
	var a := 0.0
	for i in pts.size():
		var p := pts[i]
		var q := pts[(i + 1) % pts.size()]
		a += p.x * q.y - q.x * p.y
	return a * 0.5


static func _dedupe(pts: PackedVector2Array, closed: bool) -> PackedVector2Array:
	var out := PackedVector2Array()
	for p in pts:
		if out.is_empty() or out[out.size() - 1].distance_to(p) > 0.05:
			out.append(p)
	if closed and out.size() > 2 and out[0].distance_to(out[out.size() - 1]) < 0.05:
		out.remove_at(out.size() - 1)
	return out


# ------------------------------------------------------------------ Füllungen

## paint: Color | {"lin": [[off, Color], …], "from": Vector2, "to": Vector2}
##              | {"rad": [[off, Color], …], "c": Vector2, "r": Vector2}
static func fill(parent: Node, poly: PackedVector2Array, paint, name := "") -> Polygon2D:
	var pg := Polygon2D.new()
	if name != "":
		pg.name = name
	pg.polygon = poly
	set_paint(pg, paint)
	parent.add_child(pg)
	stats.fills += 1
	stats.points += poly.size()
	return pg


static func set_paint(pg: Polygon2D, paint) -> void:
	var poly := pg.polygon
	if paint is Color:
		pg.color = paint
		pg.texture = null
		return
	pg.color = Color.WHITE
	var d: Dictionary = paint
	var g := Gradient.new()
	var stops: Array = d.get("lin", d.get("rad", []))
	var offs := PackedFloat32Array()
	var cols := PackedColorArray()
	for s in stops:
		offs.append(float(s[0]))
		cols.append(s[1])
	g.offsets = offs
	g.colors = cols
	var tx := GradientTexture2D.new()
	tx.gradient = g
	var uv := PackedVector2Array()
	if d.has("lin"):
		tx.width = 512
		tx.height = 4
		tx.fill_from = Vector2(0, 0.5)
		tx.fill_to = Vector2(1, 0.5)
		var a: Vector2 = d["from"]
		var b: Vector2 = d["to"]
		var dir := b - a
		for p in poly:
			uv.append(Vector2((p - a).dot(dir) / dir.length_squared() * 512.0, 2.0))
	else:
		tx.width = 128
		tx.height = 128
		tx.fill = GradientTexture2D.FILL_RADIAL
		tx.fill_from = Vector2(0.5, 0.5)
		tx.fill_to = Vector2(1.0, 0.5)
		var c: Vector2 = d["c"]
		var r: Vector2 = d["r"]
		for p in poly:
			var q := (p - c) / r
			uv.append((q * 0.5 + Vector2(0.5, 0.5)) * 128.0)
	pg.texture = tx
	pg.uv = uv
	stats.gradients += 1


# ------------------------------------------------------------------ Konturen (Pinselstriche)

## Band um eine Linie: Polygon2D mit einem Viereck je Abschnitt (robust auch bei engen Kurven,
## Überlappungen sind bei deckender Farbe unsichtbar).
static func ribbon_into(pg: Polygon2D, pts: PackedVector2Array, widths: PackedFloat32Array, closed: bool) -> void:
	var n := pts.size()
	var verts := PackedVector2Array()
	verts.resize(n * 2)
	for i in n:
		var prev: Vector2
		var next: Vector2
		if closed:
			prev = pts[(i - 1 + n) % n]
			next = pts[(i + 1) % n]
		else:
			prev = pts[maxi(i - 1, 0)]
			next = pts[mini(i + 1, n - 1)]
		var d1 := (pts[i] - prev).normalized() if (closed or i > 0) else (next - pts[i]).normalized()
		var d2 := (next - pts[i]).normalized() if (closed or i < n - 1) else d1
		var t := d1 + d2
		if t.length() < 1e-4:
			t = d1
		t = t.normalized()
		var nrm := Vector2(-t.y, t.x)
		var cosh := absf(nrm.dot(Vector2(-d1.y, d1.x)))
		var h := widths[i] * 0.5 / maxf(cosh, 0.5)
		verts[i] = pts[i] + nrm * h
		verts[n + i] = pts[i] - nrm * h
	var polys := []
	var segs := n if closed else n - 1
	for i in segs:
		var j := (i + 1) % n
		polys.append(PackedInt32Array([i, j, n + j, n + i]))
	pg.polygon = verts
	pg.polygons = polys


## Geschlossene Kontur. Breite folgt dem Licht: auf der Schattenseite (unten rechts) dick,
## auf der Lichtseite dünn (lo = Anteil der Breite dort). pinch: Stellen (0..1 entlang der
## Kontur), an denen der Strich fast absetzt – wie zwei Pinselstriche, die sich treffen.
static func outline_widths(pts: PackedVector2Array, w: float, lo := 0.45, pinch := []) -> PackedFloat32Array:
	var n := pts.size()
	var ccw := signed_area(pts) > 0.0
	var lens := PackedFloat32Array()
	lens.resize(n)
	var total := 0.0
	for i in n:
		lens[i] = total
		total += pts[i].distance_to(pts[(i + 1) % n])
	var ws := PackedFloat32Array()
	ws.resize(n)
	for i in n:
		var t := (pts[(i + 1) % n] - pts[(i - 1 + n) % n]).normalized()
		var nout := Vector2(t.y, -t.x) if ccw else Vector2(-t.y, t.x)
		var s := smoothstep(-0.35, 0.85, nout.dot(SHADOW_DIR))
		var k := lo + (1.0 - lo) * s
		var u := lens[i] / total
		for p in pinch:
			var du := absf(u - float(p))
			du = minf(du, 1.0 - du)
			k *= lerpf(0.12, 1.0, smoothstep(0.0, 0.07, du))
		ws[i] = w * k
	return ws


static func ink(parent: Node, poly: PackedVector2Array, w := 1.8, lo := 0.45, pinch := [], col := INK) -> Polygon2D:
	var pts := _dedupe(poly, true)
	var pg := Polygon2D.new()
	pg.color = col
	ribbon_into(pg, pts, outline_widths(pts, w, lo, pinch), true)
	parent.add_child(pg)
	stats.strokes += 1
	stats.points += pts.size() * 2
	return pg


## Offener Pinselstrich mit spitzen Enden (ta/tb = Anteil der Länge, über den er anschwillt/abschwillt).
static func stroke_widths(pts: PackedVector2Array, w: float, ta := 0.35, tb := 0.35, wmin := 0.0) -> PackedFloat32Array:
	var n := pts.size()
	var lens := PackedFloat32Array()
	lens.resize(n)
	var total := 0.0
	for i in n:
		lens[i] = total
		if i < n - 1:
			total += pts[i].distance_to(pts[i + 1])
	var ws := PackedFloat32Array()
	ws.resize(n)
	for i in n:
		var u := lens[i] / maxf(total, 0.001)
		var k := 1.0
		if ta > 0.0:
			k = minf(k, smoothstep(0.0, ta, u))
		if tb > 0.0:
			k = minf(k, smoothstep(0.0, tb, 1.0 - u))
		ws[i] = w * lerpf(wmin, 1.0, sqrt(k))
	return ws


static func stroke(parent: Node, pts_in: PackedVector2Array, w := 1.4, ta := 0.35, tb := 0.35, wmin := 0.0, col := INK) -> Polygon2D:
	var pts := _dedupe(pts_in, false)
	var pg := Polygon2D.new()
	pg.color = col
	ribbon_into(pg, pts, stroke_widths(pts, w, ta, tb, wmin), false)
	parent.add_child(pg)
	stats.strokes += 1
	stats.points += pts.size() * 2
	return pg


## Füllung plus Kontur in einer Gruppe.
static func shape(parent: Node, poly: PackedVector2Array, paint, w := 1.8, lo := 0.45, pinch := [], name := "") -> Polygon2D:
	var f := fill(parent, poly, paint, name)
	if w > 0.0:
		ink(parent, poly, w, lo, pinch)
	return f


static func add_glow(pg: CanvasItem) -> void:
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	pg.material = m


static func group(parent: Node, name: String, pos := Vector2.ZERO) -> Node2D:
	var g := Node2D.new()
	g.name = name
	g.position = pos
	parent.add_child(g)
	return g


# ------------------------------------------------------------------ Zusammenfassen (weniger Zeichenaufrufe)

static var bake_stats := {"meshes": 0, "polygons": 0, "triangles": 0, "failed": 0}


## Fasst alle unbewegten, einfarbigen Polygon2D unter root (in Zeichenreihenfolge) zu wenigen
## MeshInstance2D mit Eckpunktfarben zusammen: ein Zeichenaufruf je Folge statt je Form.
## Knoten in keep (animierte Teile), Polygon2D mit Verlauf oder Material und alle Nicht-Polygon2D-
## Knoten ohne Kinder bleiben eigene Knoten und werden in der richtigen Reihenfolge direkt unter root gehängt.
static func bake(root: Node2D, keep: Array = []) -> void:
	var seq := []           # Folge aus {"mesh": [Punkte, Farben]} oder {"node": Node, "xf": Transform2D}
	_collect(root, Transform2D.IDENTITY, keep, seq, true)
	var old := root.get_children()
	for c in old:
		root.remove_child(c)
	var run_pts := PackedVector2Array()
	var run_cols := PackedColorArray()
	for item in seq:
		if item.has("node"):
			_flush(root, run_pts, run_cols)
			run_pts = PackedVector2Array()
			run_cols = PackedColorArray()
			var n: Node = item["node"]
			if n.get_parent():
				n.get_parent().remove_child(n)
			if n is Node2D:
				(n as Node2D).transform = item["xf"]
			elif n is Control:
				(n as Control).position = item["xf"] * (n as Control).position
			root.add_child(n)
		else:
			run_pts.append_array(item["pts"])
			run_cols.append_array(item["cols"])
	_flush(root, run_pts, run_cols)
	for c in old:
		if is_instance_valid(c) and c.get_parent() == null:
			c.queue_free()


static func _collect(n: Node, xf: Transform2D, keep: Array, seq: Array, is_root: bool) -> void:
	for c in n.get_children():
		var cxf := xf
		if c is Node2D:
			cxf = xf * (c as Node2D).transform
		if c in keep:
			seq.append({"node": c, "xf": cxf})
		elif c is Polygon2D:
			var pg := c as Polygon2D
			if pg.texture != null or pg.material != null or not pg.visible or pg.get_child_count() > 0:
				seq.append({"node": c, "xf": cxf})
				continue
			var tri := _triangles(pg)
			if tri.is_empty():
				bake_stats.failed += 1
				continue
			var pts := PackedVector2Array()
			var cols := PackedColorArray()
			var col := pg.color * pg.modulate * pg.self_modulate
			for i in tri:
				pts.append(cxf * pg.polygon[i])
				cols.append(col)
			seq.append({"pts": pts, "cols": cols})
			bake_stats.polygons += 1
			bake_stats.triangles += tri.size() / 3
		elif c is Node2D and c.get_script() == null and (c as Node2D).modulate == Color.WHITE and c.get_child_count() > 0:
			_collect(c, cxf, keep, seq, false)
		else:
			seq.append({"node": c, "xf": cxf if c is Node2D else xf})


static func _triangles(pg: Polygon2D) -> PackedInt32Array:
	if pg.polygons.is_empty():
		return Geometry2D.triangulate_polygon(pg.polygon)
	var out := PackedInt32Array()
	for q in pg.polygons:
		var idx: PackedInt32Array = q
		for k in range(1, idx.size() - 1):
			out.append_array([idx[0], idx[k], idx[k + 1]])
	return out


static func _flush(root: Node2D, pts: PackedVector2Array, cols: PackedColorArray) -> void:
	if pts.is_empty():
		return
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = pts
	arrays[Mesh.ARRAY_COLOR] = cols
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mi := MeshInstance2D.new()
	mi.name = "Baked"
	mi.mesh = mesh
	root.add_child(mi)
	bake_stats.meshes += 1

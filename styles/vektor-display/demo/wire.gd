extends RefCounted
## Drahtgittermodelle wie auf einem Vektorautomaten: Eckpunktlisten, perspektivisch projiziert.
## "Feste" Körper (konvex) zeichnen nur Kanten von Flächen, die zur Kamera zeigen (Rückseitenentfernung),
## und verdecken dahinter liegende Linien mit ihrem Umriss. "Offene" Modelle sind reine Linienzüge.

# Kamera (fest): Lage, Neigung, vertikaler Bildwinkel, Bildgröße
var cam_pos := Vector3(0.0, 1.7, 8.0)
var pitch_deg := -7.0
var fov_deg := 48.0
var size := Vector2(1280, 720)
var f_px := 0.0
var fwd := Vector3()
var up := Vector3()


func setup() -> void:
	f_px = size.y * 0.5 / tan(deg_to_rad(fov_deg) * 0.5)
	var p := deg_to_rad(pitch_deg)
	fwd = Vector3(0.0, sin(p), -cos(p))
	up = Vector3(0.0, cos(p), sin(p))


## Kamerakoordinaten: x rechts, y oben, z Tiefe (positiv vor der Kamera)
func to_cam(w: Vector3) -> Vector3:
	var d := w - cam_pos
	return Vector3(d.x, d.dot(up), d.dot(fwd))


func project(w: Vector3) -> Vector2:
	var c := to_cam(w)
	var z := maxf(c.z, 0.05)
	return Vector2(size.x * 0.5 + f_px * c.x / z, size.y * 0.5 - f_px * c.y / z)


func depth(w: Vector3) -> float:
	return to_cam(w).z


## Pixel pro Meter in einer Tiefe (für flache Figuren in der Szene)
func px_per_m(z: float) -> float:
	return f_px / z


# ---------------------------------------------------------------------------
# Bausteine. Ein fester Körper: {verts, faces:[{i, hue, k, prio, decals:[[PackedVector3Array, hue, k, closed]]}]}
# ---------------------------------------------------------------------------

static func solid(verts: PackedVector3Array, faces: Array) -> Dictionary:
	# Windung jeder Fläche nach außen drehen (Schwerpunkt-Test, nur für konvexe Körper gültig)
	var c := Vector3()
	for v in verts:
		c += v
	c /= float(verts.size())
	for f in faces:
		var idx: PackedInt32Array = f.i
		var n := (verts[idx[1]] - verts[idx[0]]).cross(verts[idx[2]] - verts[idx[0]])
		var fc := Vector3()
		for k in idx:
			fc += verts[k]
		fc /= float(idx.size())
		if n.dot(fc - c) < 0.0:
			idx.reverse()
			f.i = idx
		if not f.has("decals"):
			f.decals = []
		if not f.has("prio"):
			f.prio = 0
	return {"verts": verts, "faces": faces}


static func face(i: Array, hue: Color, k: float, prio := 0, decals := []) -> Dictionary:
	return {"i": PackedInt32Array(i), "hue": hue, "k": k, "prio": prio, "decals": decals}


## Quader von a bis b; bottom=false lässt die Bodenfläche weg (steht auf etwas)
static func box(a: Vector3, b: Vector3, hue: Color, k: float, bottom := false) -> Dictionary:
	var v := PackedVector3Array([
		Vector3(a.x, a.y, a.z), Vector3(b.x, a.y, a.z), Vector3(b.x, a.y, b.z), Vector3(a.x, a.y, b.z),
		Vector3(a.x, b.y, a.z), Vector3(b.x, b.y, a.z), Vector3(b.x, b.y, b.z), Vector3(a.x, b.y, b.z)])
	var f := [
		face([4, 5, 6, 7], hue, k),        # oben
		face([0, 1, 5, 4], hue, k),        # hinten (z = a.z)
		face([3, 2, 6, 7], hue, k),        # vorn (z = b.z)
		face([0, 3, 7, 4], hue, k),        # links
		face([1, 2, 6, 5], hue, k)]        # rechts
	if bottom:
		f.append(face([0, 1, 2, 3], hue, k))
	return solid(v, f)


## Gestapelter Kegelstumpf um die y-Achse: rings = [[y, r], ...], bands = Farbe je Abschnitt [[hue, k, prio], ...]
static func lathe(rings: Array, n: int, bands: Array, top := true, phase := 0.0) -> Dictionary:
	var v := PackedVector3Array()
	for ring in rings:
		for j in n:
			var a := TAU * (float(j) + phase) / float(n)
			v.append(Vector3(cos(a) * ring[1], ring[0], sin(a) * ring[1]))
	var faces := []
	for r in rings.size() - 1:
		var b: Array = bands[mini(r, bands.size() - 1)]
		for j in n:
			var j2 := (j + 1) % n
			faces.append(face([r * n + j, r * n + j2, (r + 1) * n + j2, (r + 1) * n + j], b[0], b[1], b[2]))
	if top:
		var last := rings.size() - 1
		var b: Array = bands[mini(last - 1, bands.size() - 1)]
		var idx := []
		for j in n:
			idx.append(last * n + j)
		faces.append(face(idx, b[0], b[1], b[2]))
	return solid(v, faces)


# ---------------------------------------------------------------------------
# Projektion eines Körpers in Bildlinien
# ---------------------------------------------------------------------------

## Gibt {lines:[[PackedVector2Array, Color, closed, cap]], occ: PackedVector2Array, depth} zurück.
## xf: Lage in der Welt; cue(depth) liefert die Tiefenabschwächung.
func emit_solid(m: Dictionary, xf: Transform3D, cue: Callable, cap := 0.45) -> Dictionary:
	var verts: PackedVector3Array = m.verts
	var wv := PackedVector3Array()
	wv.resize(verts.size())
	var sv := PackedVector2Array()
	sv.resize(verts.size())
	var center := Vector3()
	for i in verts.size():
		wv[i] = xf * verts[i]
		sv[i] = project(wv[i])
		center += wv[i]
	center /= float(verts.size())
	var dz := depth(center)
	var c := cue.call(dz) as float
	var edges := {}
	var lines := []
	var hull_pts := PackedVector2Array()
	for f in m.faces:
		var idx: PackedInt32Array = f.i
		var n := (wv[idx[1]] - wv[idx[0]]).cross(wv[idx[2]] - wv[idx[0]])
		if n.dot(cam_pos - wv[idx[0]]) <= 0.0:
			continue
		for j in idx.size():
			var a := idx[j]
			var b := idx[(j + 1) % idx.size()]
			var key := mini(a, b) * 65536 + maxi(a, b)
			if not edges.has(key) or edges[key][2] < f.prio:
				edges[key] = [a, b, f.prio, f.hue, f.k]
			hull_pts.append(sv[a])
		for d in f.decals:
			var p := PackedVector2Array()
			for q in d[0]:
				p.append(project(xf * q))
			lines.append([p, d[1] * (d[2] * c), d[3], 0.6])
	for e in edges.values():
		lines.append([PackedVector2Array([sv[e[0]], sv[e[1]]]), (e[3] as Color) * ((e[4] as float) * c), false, cap])
	var occ := PackedVector2Array()
	if hull_pts.size() >= 3:
		occ = Geometry2D.convex_hull(hull_pts)
	return {"lines": lines, "occ": occ, "depth": dz}


## Offene Linienzüge: lines = [[PackedVector3Array, hue, k, closed], ...]
## Ergebnis-Linien: [PackedVector2Array, Farbe, closed, cap]
func emit_wire(lines3: Array, xf: Transform3D, cue: Callable, depth_override := -1.0, cap := 0.8) -> Dictionary:
	var center := Vector3()
	var count := 0
	var projected := []
	for l in lines3:
		var p := PackedVector2Array()
		for q in l[0]:
			var w: Vector3 = xf * q
			p.append(project(w))
			center += w
			count += 1
		projected.append(p)
	center /= float(maxi(count, 1))
	var dz := depth_override if depth_override > 0.0 else depth(center)
	var c := cue.call(dz) as float
	var lines := []
	for i in lines3.size():
		var l: Array = lines3[i]
		lines.append([projected[i], (l[1] as Color) * ((l[2] as float) * c), l[3], cap])
	return {"lines": lines, "occ": PackedVector2Array(), "depth": dz}


func project_poly(pts: PackedVector3Array, xf := Transform3D.IDENTITY) -> PackedVector2Array:
	var p := PackedVector2Array()
	for q in pts:
		p.append(project(xf * q))
	return p

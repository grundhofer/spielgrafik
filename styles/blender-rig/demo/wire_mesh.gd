class_name WireMesh
## Baut aus einem geskinnten ArrayMesh ein Mesh für den Drahtgitter-Shader (shaders/wire.gdshader).
##
## Jedes Dreieck bekommt eigene Eckpunkte mit baryzentrischen Koordinaten in COLOR; Knochen und Gewichte
## werden mitkopiert, damit das Gitter am selben Skin hängt und sich mit der Figur verformt.
## glTF speichert nur Dreiecke. Die Figur besteht in Blender aber fast nur aus Vierecken (Ring-Lofts).
## Deshalb werden Dreieckspaare gesucht, die zusammen ein fast rechtwinkliges, fast ebenes Viereck bilden;
## deren gemeinsame Kante ist die Diagonale und wird ausgeblendet (Komponente +1, erreicht nie 0).

const MAX_BEND := 0.94          # cos des Winkels zwischen den Flächennormalen (≈ 20°)
const MAX_CORNER_DEV := 38.0    # Grad: größte Abweichung einer Viereckecke von 90°


static func build(src: ArrayMesh) -> ArrayMesh:
	var pos := PackedVector3Array()
	var nrm := PackedVector3Array()
	var bones := PackedInt32Array()
	var weights := PackedFloat32Array()
	var cols := PackedColorArray()
	var stats := [0, 0]   # Dreiecke, ausgeblendete Diagonalen
	for s in src.get_surface_count():
		var a := src.surface_get_arrays(s)
		var v: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var n: PackedVector3Array = a[Mesh.ARRAY_NORMAL]
		var b: PackedInt32Array = a[Mesh.ARRAY_BONES]
		var w: PackedFloat32Array = a[Mesh.ARRAY_WEIGHTS]
		var idx: PackedInt32Array = a[Mesh.ARRAY_INDEX]
		if idx.is_empty():
			idx = PackedInt32Array(range(v.size()))
		var bpv := b.size() / v.size()       # Einflüsse je Punkt (4)
		var hidden := _diagonals(v, idx)
		var tri_count := idx.size() / 3
		stats[0] += tri_count
		for tri in tri_count:
			var hide: int = hidden.get(tri, -1)   # Ecke, deren Gegenkante ausgeblendet wird
			for c in 3:
				var vi := idx[tri * 3 + c]
				pos.append(v[vi])
				nrm.append(n[vi])
				for k in 4:
					bones.append(b[vi * bpv + k] if k < bpv else 0)
					weights.append(w[vi * bpv + k] if k < bpv else 0.0)
				var bc := Vector3.ZERO
				bc[c] = 1.0
				if hide >= 0:
					bc[hide] += 1.0
				cols.append(Color(bc.x, bc.y, bc.z, 1.0))
			if hide >= 0:
				stats[1] += 1
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = pos
	arrays[Mesh.ARRAY_NORMAL] = nrm
	arrays[Mesh.ARRAY_COLOR] = cols
	arrays[Mesh.ARRAY_BONES] = bones
	arrays[Mesh.ARRAY_WEIGHTS] = weights
	var out := ArrayMesh.new()
	out.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	out.set_meta("triangles", stats[0])
	out.set_meta("hidden_diagonals", stats[1])
	return out


## Dreieck -> Ecke (0..2), deren gegenüberliegende Kante die Diagonale eines Vierecks ist.
static func _diagonals(v: PackedVector3Array, idx: PackedInt32Array) -> Dictionary:
	# Punkte nach Lage zusammenfassen (UV- und Normalennähte teilen Punkte in glTF)
	var key_of := PackedInt32Array()
	key_of.resize(v.size())
	var keys := {}
	for i in v.size():
		var k := Vector3i(roundi(v[i].x * 10000.0), roundi(v[i].y * 10000.0), roundi(v[i].z * 10000.0))
		if not keys.has(k):
			keys[k] = keys.size()
		key_of[i] = keys[k]
	var tri_count := idx.size() / 3
	var edges := {}   # Vector2i(kleiner, größer) -> [Dreieck, Ecke gegenüber, ...]
	for tri in tri_count:
		for c in 3:
			var a := key_of[idx[tri * 3 + (c + 1) % 3]]
			var b := key_of[idx[tri * 3 + (c + 2) % 3]]
			var e := Vector2i(mini(a, b), maxi(a, b))
			if not edges.has(e):
				edges[e] = []
			edges[e].append_array([tri, c])
	var cands := []   # [Abweichung, Dreieck1, Ecke1, Dreieck2, Ecke2]
	for e in edges:
		var l: Array = edges[e]
		if l.size() != 4:
			continue
		var t1: int = l[0]
		var c1: int = l[1]
		var t2: int = l[2]
		var c2: int = l[3]
		var p0 := v[idx[t1 * 3 + c1]]             # gegenüber in Dreieck 1
		var pa := v[idx[t1 * 3 + (c1 + 1) % 3]]
		var pb := v[idx[t1 * 3 + (c1 + 2) % 3]]
		var p1 := v[idx[t2 * 3 + c2]]             # gegenüber in Dreieck 2
		var n1 := (pa - p0).cross(pb - p0)
		var n2 := (pb - p1).cross(pa - p1)
		if n1.length() < 1e-12 or n2.length() < 1e-12:
			continue
		if n1.normalized().dot(n2.normalized()) < MAX_BEND:
			continue
		# Viereck p0 -> pa -> p1 -> pb: alle vier Ecken nahe 90°?
		var quad := [p0, pa, p1, pb]
		var dev := 0.0
		for q in 4:
			var prev: Vector3 = quad[(q + 3) % 4] - quad[q]
			var next: Vector3 = quad[(q + 1) % 4] - quad[q]
			dev = maxf(dev, absf(rad_to_deg(prev.angle_to(next)) - 90.0))
		if dev <= MAX_CORNER_DEV:
			cands.append([dev, t1, c1, t2, c2])
	cands.sort_custom(func(x, y): return x[0] < y[0])
	var out := {}
	for c in cands:
		if out.has(c[1]) or out.has(c[3]):
			continue
		out[c[1]] = c[2]
		out[c[3]] = c[4]
	return out

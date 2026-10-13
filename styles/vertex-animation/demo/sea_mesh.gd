class_name SeaMesh
extends RefCounted
## Unterteiltes Meeresgitter für die Gerstner-Wellen (ersetzt `Sea` aus harbor.glb, das im Hafen nur
## 1,5-m-Zellen hat). Im Hafen gleichmäßige Zellen von STEP m, nach außen wachsen die Zellen je Schritt
## um GROWTH bis zum Rand von `Sea` (±700 m seitlich, 900 m nach hinten). Dort sind die Wellen ausgeblendet
## (waves.gd → fade), das grobe Gitter bleibt flach und trägt nur noch die Kräuselung in der Normale.

const STEP := 0.3
const GROWTH := 1.22
const FINE_X := Vector2(-22.0, 24.0)
const FINE_Z := Vector2(-40.0, 10.0)
const OUTER_X := Vector2(-700.0, 700.0)
const OUTER_Z := Vector2(-900.0, 40.0)


static func axis(fine: Vector2, outer: Vector2) -> PackedFloat32Array:
	var mid: Array[float] = []
	var n := int(round((fine.y - fine.x) / STEP))
	for i in n + 1:
		mid.append(fine.x + STEP * i)
	var right: Array[float] = []
	var s := STEP
	var x := fine.y
	while x < outer.y - 0.001:
		s *= GROWTH
		x = minf(x + s, outer.y)
		right.append(x)
	var left: Array[float] = []
	s = STEP
	x = fine.x
	while x > outer.x + 0.001:
		s *= GROWTH
		x = maxf(x - s, outer.x)
		left.append(x)
	left.reverse()
	return PackedFloat32Array(left + mid + right)


static func build() -> ArrayMesh:
	var xs := axis(FINE_X, OUTER_X)
	var zs := axis(FINE_Z, OUTER_Z)
	var nx := xs.size()
	var nz := zs.size()
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	verts.resize(nx * nz)
	normals.resize(nx * nz)
	for j in nz:
		for i in nx:
			verts[j * nx + i] = Vector3(xs[i], 0.0, zs[j])
			normals[j * nx + i] = Vector3.UP
	var idx := PackedInt32Array()
	idx.resize((nx - 1) * (nz - 1) * 6)
	var k := 0
	for j in nz - 1:
		for i in nx - 1:
			var a := j * nx + i
			var b := a + 1
			var c := a + nx
			var d := c + 1
			# Godot: Vorderseite im Uhrzeigersinn (von oben gesehen)
			idx[k] = a; idx[k + 1] = b; idx[k + 2] = c
			idx[k + 3] = b; idx[k + 4] = d; idx[k + 5] = c
			k += 6
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = verts
	arr[Mesh.ARRAY_NORMAL] = normals
	arr[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arr)
	mesh.custom_aabb = AABB(Vector3(OUTER_X.x, -1.0, OUTER_Z.x), Vector3(OUTER_X.y - OUTER_X.x, 2.0, OUTER_Z.y - OUTER_Z.x))
	return mesh

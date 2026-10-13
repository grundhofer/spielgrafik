extends RefCounted
## Verlet-Kette mit festem Zeitschritt: Abstands- und Knickbedingungen, quadratischer Luftwiderstand.
## Anheften und Kollisionen setzt der Aufrufer zwischen den Iterationen.

var p := PackedVector2Array()
var pp := PackedVector2Array()
var inv_m := PackedFloat32Array()
var drag := PackedFloat32Array()
var seg := 10.0
var min_fold := 0.55   # kleinster Abstand zwischen i-1 und i+1 als Anteil von 2*seg


func init_line(start: Vector2, dir: Vector2, n: int, seg_len: float) -> void:
	seg = seg_len
	p.resize(n); pp.resize(n); inv_m.resize(n); drag.resize(n)
	for i in n:
		p[i] = start + dir.normalized() * seg_len * i
		pp[i] = p[i]
		inv_m[i] = 1.0
		drag[i] = 1.0
	inv_m[0] = 0.0


func size() -> int:
	return p.size()


func integrate(dt: float, gravity: Vector2, air: Vector2, k: float, damp: float) -> void:
	for i in p.size():
		if inv_m[i] == 0.0:
			continue
		var vel: Vector2 = (p[i] - pp[i]) / dt
		var rel: Vector2 = vel - air
		var acc: Vector2 = gravity - rel * rel.length() * k * drag[i]
		var np: Vector2 = p[i] + (p[i] - pp[i]) * (1.0 - damp * dt) + acc * dt * dt
		pp[i] = p[i]
		p[i] = np


func solve(lengths_only := false) -> void:
	var n := p.size()
	for i in n - 1:
		var w: float = inv_m[i] + inv_m[i + 1]
		if w == 0.0:
			continue
		var d: Vector2 = p[i + 1] - p[i]
		var l := d.length()
		if l < 1e-6:
			continue
		var corr: Vector2 = d * ((l - seg) / (l * w))
		p[i] += corr * inv_m[i]
		p[i + 1] -= corr * inv_m[i + 1]
	if lengths_only:
		return
	var dmin := 2.0 * seg * min_fold
	for i in range(1, n - 1):
		var w2: float = inv_m[i - 1] + inv_m[i + 1]
		if w2 == 0.0:
			continue
		var d2: Vector2 = p[i + 1] - p[i - 1]
		var l2 := d2.length()
		if l2 >= dmin or l2 < 1e-6:
			continue
		var c2: Vector2 = d2 * ((l2 - dmin) / (l2 * w2))
		p[i - 1] += c2 * inv_m[i - 1]
		p[i + 1] -= c2 * inv_m[i + 1]


## Schiebt Glieder ab Index first aus einer Kapsel (Strecke a-b, Radius r).
func push_out_capsule(a: Vector2, b: Vector2, r: float, first: int, end := -1) -> void:
	var ab := b - a
	var ab2 := ab.length_squared()
	for i in range(first, p.size() if end < 0 else end):
		if inv_m[i] == 0.0:
			continue
		var u := clampf((p[i] - a).dot(ab) / ab2, 0.0, 1.0)
		var c := a + ab * u
		var d: Vector2 = p[i] - c
		var l := d.length()
		if l < r and l > 1e-6:
			p[i] = c + d * (r / l)


func length_total() -> float:
	var s := 0.0
	for i in p.size() - 1:
		s += p[i].distance_to(p[i + 1])
	return s

extends Node2D
## Möwen als Schwarm (Boids): Trennung, Ausrichtung, Zusammenhalt, ein langsam wandernder Zielpunkt über dem
## Wasser und weiche Ränder. Flügelschlag beim Steigen und bei wenig Tempo, Gleiten beim Sinken.

const N := 5
var pos := PackedVector2Array()
var vel := PackedVector2Array()
var flap_ph := PackedFloat32Array()
var flap_amt := PackedFloat32Array()
var size_k := PackedFloat32Array()
var t := 0.0
var region := Rect2(700, 60, 540, 210)


func setup() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	for i in N:
		pos.append(Vector2(rng.randf_range(820, 1080), rng.randf_range(110, 220)))
		vel.append(Vector2.from_angle(rng.randf_range(-PI, PI)) * 50.0)
		flap_ph.append(rng.randf_range(0, TAU))
		flap_amt.append(1.0)
		size_k.append(rng.randf_range(0.82, 1.08))


func attractor(tt: float) -> Vector2:
	return Vector2(960.0 + 210.0 * sin(0.19 * tt + 0.6), 160.0 + 55.0 * sin(0.33 * tt + 1.3))


func step(tt: float, dt: float) -> void:
	t = tt
	var goal := attractor(tt)
	for i in N:
		var sep := Vector2()
		var ali := Vector2()
		var coh := Vector2()
		var na := 0
		var nc := 0
		for j in N:
			if j == i:
				continue
			var d: Vector2 = pos[j] - pos[i]
			var l := d.length()
			if l < 48.0:
				sep -= d.normalized() * (48.0 - l)
			if l < 120.0:
				ali += vel[j]
				na += 1
			if l < 170.0:
				coh += pos[j]
				nc += 1
		var steer := sep * 2.2
		if na > 0:
			steer += (ali / na - vel[i]) * 0.45
		if nc > 0:
			steer += (coh / nc - pos[i]) * 0.18
		var to_g: Vector2 = goal - pos[i]
		steer += to_g.normalized() * minf(to_g.length(), 220.0) * 0.18
		var p: Vector2 = pos[i]
		if p.y < region.position.y:
			steer.y += (region.position.y - p.y) * 5.0
		if p.y > region.end.y:
			steer.y -= (p.y - region.end.y) * 5.0
		if p.x < region.position.x:
			steer.x += (region.position.x - p.x) * 5.0
		if p.x > region.end.x:
			steer.x -= (p.x - region.end.x) * 5.0
		steer = steer.limit_length(85.0)
		var v: Vector2 = vel[i] + steer * dt
		var sp := clampf(v.length(), 34.0, 78.0)
		v = v.normalized() * sp
		vel[i] = v
		pos[i] = p + v * dt
		var want := 1.0 if (v.y < -6.0 or sp < 46.0) else 0.18
		flap_amt[i] = move_toward(flap_amt[i], want, dt * 2.2)
		flap_ph[i] += dt * TAU * 3.4 * (0.55 + 0.45 * flap_amt[i])


func _draw() -> void:
	for i in N:
		var v: Vector2 = vel[i]
		var wv := sin(flap_ph[i]) * flap_amt[i] + 0.25 * (1.0 - flap_amt[i])
		var s := 10.5 * size_k[i]
		var elbow := -2.0 - 2.6 * wv
		var tip := 0.8 - 6.2 * wv
		var dirx := 1.0 if v.x >= 0.0 else -1.0
		var bank := clampf(v.y * 0.006, -0.3, 0.3) * dirx
		var raw := [Vector2(-s, tip), Vector2(-0.48 * s, elbow), Vector2(0, 0.8), Vector2(0.48 * s, elbow), Vector2(s, tip)]
		var pts := PackedVector2Array()
		for q in raw:
			pts.append(pos[i] + (q as Vector2).rotated(bank))
		draw_polyline(pts, Color(0.22, 0.19, 0.27, 0.9), 3.6, true)
		draw_polyline(pts, Color(0.93, 0.92, 0.95), 1.8, true)
		draw_circle(pos[i] + Vector2(0, 1.0), 1.9, Color(0.93, 0.92, 0.95))
		draw_circle(pos[i] + Vector2(2.3 * dirx, 0.4), 1.2, Color(0.93, 0.92, 0.95))

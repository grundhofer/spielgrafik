extends Node2D
## Sterne im oberen Himmel: feste Positionen (fester Seed), funkeln in ganzen Helligkeitsstufen.
## Größere Sterne bekommen beim Aufblitzen ein 1-px-Kreuz. Nur auf Himmelspixeln (Maske layers.png, Rot).

var t := 0.0
var stars: Array = []

func setup(sky_mask: Image) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 4711
	var tries := 0
	while stars.size() < 34 and tries < 2000:
		tries += 1
		var p := Vector2i(rng.randi_range(4, 635), rng.randi_range(2, 80))
		# nur dort, wo Himmel ist und es dunkel genug ist (keine Wolken)
		var c := sky_mask.get_pixelv(p)
		if c.r < 0.5:
			continue
		var ok := true
		for s in stars:
			if (s.p - p).length() < 9:
				ok = false
				break
		if ok:
			stars.append({"p": p, "big": rng.randf() < 0.18, "ph": rng.randf() * TAU, "sp": rng.randf_range(0.6, 1.6)})

func step(time: float) -> void:
	t = time
	queue_redraw()

func _draw() -> void:
	for s in stars:
		var v := 0.5 + 0.5 * sin(t * s.sp * 2.2 + s.ph)
		var lvl := floorf(v * 3.0) / 3.0      # 4 Stufen
		var a := 0.25 + 0.75 * lvl
		var col := Color(1.0, 0.95, 0.88, a)
		var p: Vector2 = Vector2(s.p)
		draw_rect(Rect2(p, Vector2.ONE), col)
		if s.big and lvl >= 0.99:
			var c2 := Color(0.85, 0.82, 1.0, 0.55)
			for o in [Vector2(1, 0), Vector2(-1, 0), Vector2(0, 1), Vector2(0, -1)]:
				draw_rect(Rect2(p + o, Vector2.ONE), c2)

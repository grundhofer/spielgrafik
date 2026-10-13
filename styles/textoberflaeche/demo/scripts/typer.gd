extends RefCounted
## Zeitplan für getippten Text: zu welcher Zeit welches Zeichen erscheint.
## Deterministisch (fester Seed), mit kleinen Pausen nach Satzzeichen wie beim Schreiben.


static func schedule(text: String, start: float, cps: float, jitter: float = 0.0, seed_v: int = 1) -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_v
	var times := PackedFloat32Array()
	var tt := start
	for i in text.length():
		times.append(tt)
		var c := text[i]
		var d := 1.0 / cps
		if jitter > 0.0:
			d *= 1.0 + rng.randf_range(-jitter, jitter)
		if c in ".!?":
			d += 0.28
		elif c in ",;:":
			d += 0.12
		tt += d
	return times


static func count_at(times: PackedFloat32Array, t: float) -> int:
	var n := 0
	for x in times:
		if x <= t:
			n += 1
		else:
			break
	return n


static func end_of(times: PackedFloat32Array) -> float:
	return times[times.size() - 1] if times.size() > 0 else 0.0

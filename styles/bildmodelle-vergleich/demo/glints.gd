extends Node2D
## Wasserglitzern der Schlussszene (320×180): kurze waagerechte Lichtstriche in den Spiegelungen von Abendrot
## und Leuchtfeuer und im offenen Wasser hinter den Booten. Jeder Strich hat feste Lage, Länge, Phase und Periode
## (Seed); er erscheint in ganzen Pixeln und in drei Helligkeitsstufen, ohne Unterpixel-Verschiebung.

# Bereiche in Szenenpixeln: [x0, x1, y0, y1, Anzahl, Farbe]
const AREAS := [
	[190, 204, 67, 96, 12, Color(1.0, 0.72, 0.38)],     # Spiegelung des Abendrots
	[289, 299, 73, 97, 7, Color(1.0, 0.86, 0.52)],      # Spiegelung des Leuchtfeuers
	[96, 286, 66, 76, 16, Color(0.70, 0.64, 0.92, 0.7)], # offenes Wasser vor dem Horizont
]

var tt := 0.0
var items: Array = []


func setup(rng: RandomNumberGenerator) -> void:
	for a in AREAS:
		for i in int(a[4]):
			var y := rng.randi_range(int(a[2]), int(a[3]))
			items.append({
				"x": rng.randi_range(int(a[0]), int(a[1]) - 2),
				"y": y,
				"len": rng.randi_range(2, 4),
				"period": rng.randf_range(0.9, 1.7),
				"phase": rng.randf(),
				"col": a[5],
			})


func _draw() -> void:
	for it in items:
		var p := fmod(tt / float(it["period"]) + float(it["phase"]), 1.0)
		if p > 0.42:
			continue
		# an – voll – ab in drei Stufen
		var lvl := 0.45 if p < 0.1 or p > 0.32 else 1.0
		var c: Color = it["col"]
		c.a *= lvl
		draw_rect(Rect2(int(it["x"]), int(it["y"]), int(it["len"]), 1), c)
